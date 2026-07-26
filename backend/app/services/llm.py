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
    "visual_director": "gemini-3.5-flash-lite",
    "designer": "gemma-4-31b-it",
    "illustrator": "gemini-3.5-flash-lite",
    "quality_check": "gemma-4-31b-it",
    "token_generator": "gemma-4-31b-it",
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
    )


async def call_llm_with_retry(llm, messages, max_retries=4):
    """Call an LLM with retry on 429 rate limit errors (exponential backoff)."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return await llm.ainvoke(messages)
        except HTTPStatusError as e:
            if e.response.status_code == 429:
                wait = 2 ** attempt + 1
                last_error = e
                await asyncio.sleep(wait)
                continue
            raise
        except Exception as e:
            last_error = e
            break
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
