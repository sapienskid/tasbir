"""LLM service — Google Gemini via LangChain ChatGoogleGenerativeAI.

All agents use this service. Provides both a high-level LangChain
integration (with tool binding support) and a simple call_llm() helper.
"""

import asyncio
from collections.abc import AsyncIterator

from httpx import HTTPStatusError
from app.config import get_settings

MODEL_ROUTES = {
    "strategist": "gemini-3.5-flash-lite",
    "copywriter": "gemini-3.5-flash-lite",
    "designer": "gemini-3.5-flash-lite",
    "verifier": "gemini-3.5-flash-lite",
    "template_vision": "gemini-3.5-flash-lite",
    "template_author": "gemini-3.5-flash-lite",
    "brand_vision": "gemini-3.5-flash-lite",
    "brand_tokens": "gemini-3.5-flash-lite",
    "brand_campaigns": "gemini-3.5-flash-lite",
}


def get_llm(agent_role: str = "strategist", temperature: float = 0.7, max_tokens: int | None = None):
    """Get a LangChain ChatGoogleGenerativeAI instance for the given role.

    Supports tool binding via .bind_tools() on the returned instance.
    Uses Gemini 2.0 Flash for most agents (free tier).
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = get_settings()
    model = MODEL_ROUTES.get(agent_role, "gemini-2.0-flash")
    api_key = settings.gemini_api_key or None

    return ChatGoogleGenerativeAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=0,
    )


async def call_llm_with_retry(llm, messages, max_retries=5, agent_role: str = ""):
    """Call an LLM with retry on 429 rate limit errors (exponential backoff & retry delay parsing).

    Falls back to OpenRouter if Gemini fails and a key is configured.
    """
    import re
    import logging
    log = logging.getLogger(__name__)

    last_error = None
    for attempt in range(max_retries):
        try:
            return await llm.ainvoke(messages)
        except Exception as e:
            err_str = str(e)
            is_429 = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota exceeded" in err_str
            if is_429 and attempt < max_retries - 1:
                match = re.search(r'(?:retry(?:Delay)?\s*[:in]\s*)(\d+)(?:\.\d+)?s', err_str, re.IGNORECASE)
                if match:
                    wait = int(match.group(1)) + 2
                else:
                    wait = (2 ** (attempt + 2)) + 5
                log.warning(f"[LLM RateLimit] Received 429 / RESOURCE_EXHAUSTED. Retrying attempt {attempt+1}/{max_retries} in {wait}s...")
                last_error = e
                await asyncio.sleep(wait)
                continue
            last_error = e
            break

    # Fallback to OpenRouter when Gemini fails and OpenRouter key is configured
    settings = get_settings()
    if settings.openrouter_api_key:
        log.warning("[LLM] Gemini failed, falling back to OpenRouter")
        last_msg = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
        sys_msg = messages[0].content if len(messages) > 0 and hasattr(messages[0], "content") else ""
        try:
            text = await _call_openrouter(
                api_key=settings.openrouter_api_key,
                model=MODEL_ROUTES.get(agent_role, "gemini-2.0-flash"),
                system_prompt=sys_msg,
                user_prompt=last_msg,
                temperature=0.7,
                max_tokens=4096,
            )
            from langchain_core.messages import AIMessage
            return AIMessage(content=text)
        except Exception as or_err:
            log.error("[LLM] OpenRouter fallback also failed: %s", or_err)

    raise last_error or RuntimeError("LLM call failed")


async def call_llm(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """Simple helper — calls LLM with system + user prompt and returns text.

    Uses LangChain's ChatGoogleGenerativeAI under the hood.
    Retries on 429 (rate limit) with exponential backoff.
    Falls back to OpenRouter if Gemini fails and a key is configured.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm(agent_role=agent_role, temperature=temperature, max_tokens=max_tokens)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    try:
        response = await call_llm_with_retry(llm, messages)
        if isinstance(response.content, str):
            return response.content
        if isinstance(response.content, list):
            texts = []
            for b in response.content:
                if isinstance(b, str):
                    texts.append(b)
                elif isinstance(b, dict) and b.get("type") == "text":
                    texts.append(b.get("text", ""))
            return "".join(texts)
        return str(response.content)
    except Exception as gemini_error:
        settings = get_settings()
        if settings.openrouter_api_key:
            return await _call_openrouter(
                api_key=settings.openrouter_api_key,
                model=MODEL_ROUTES.get(agent_role, "gemini-2.0-flash"),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        raise gemini_error


async def call_llm_stream(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> AsyncIterator[str]:
    """Stream response from LLM. Yields text chunks as they arrive."""
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm(agent_role=agent_role, temperature=temperature, max_tokens=max_tokens)

    try:
        async for chunk in llm.astream([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]):
            if not chunk.content:
                continue
            if isinstance(chunk.content, str):
                yield chunk.content
            elif isinstance(chunk.content, list):
                for block in chunk.content:
                    if isinstance(block, str):
                        yield block
                    elif isinstance(block, dict) and block.get("type") == "text":
                        yield block.get("text", "")
    except Exception as gemini_error:
        settings = get_settings()
        if settings.openrouter_api_key:
            async for chunk in _call_openrouter_stream(
                api_key=settings.openrouter_api_key,
                model=MODEL_ROUTES.get(agent_role, "gemini-2.0-flash"),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk
        else:
            raise gemini_error


async def _call_openrouter(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    import openai

    client = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def _call_openrouter_stream(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    import openai

    client = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    stream = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
