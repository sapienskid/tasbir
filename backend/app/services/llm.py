"""LLM service — Google Gemini via LangChain ChatGoogleGenerativeAI.

All agents use this service. Provides both a high-level LangChain
integration (with tool binding support) and a simple call_llm() helper.
"""

import asyncio
from collections.abc import AsyncIterator

from app.config import get_settings

# Single source of truth for the default model. All MODEL_ROUTES entries and
# the vision path fall back to this when no DB agent row provides a model.
# Parallelism/pacing is per-path (copywriter semaphore, vision lock) — see the
# runtime-settings knobs.
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Hard per-call timeout so a stalled model request becomes an exception instead
# of hanging the pipeline forever (then the OpenRouter fallback or node-level
# fallbacks kick in).
LLM_TIMEOUT = 90.0

MODEL_ROUTES = {
    "strategist": DEFAULT_MODEL,
    "planner": DEFAULT_MODEL,
    "copywriter": DEFAULT_MODEL,
    "designer": DEFAULT_MODEL,
    "verifier": DEFAULT_MODEL,
    "template_vision": DEFAULT_MODEL,
    "template_author": DEFAULT_MODEL,
    "brand_vision": DEFAULT_MODEL,
    "brand_tokens": DEFAULT_MODEL,
    "brand_campaigns": DEFAULT_MODEL,
    "editor_chat": DEFAULT_MODEL,
}


def _model_for(agent_role: str) -> str:
    """Resolve the model for a role — DB agent row first, MODEL_ROUTES fallback."""
    from app.services.agents import resolve_model

    return resolve_model(agent_role)


def get_llm(agent_role: str = "strategist", temperature: float = 0.7, max_tokens: int | None = None):
    """Get a LangChain ChatGoogleGenerativeAI instance for the given role.

    Supports tool binding via .bind_tools() on the returned instance.
    Uses Gemini 2.0 Flash for most agents (free tier).
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = get_settings()
    model = _model_for(agent_role)
    api_key = settings.gemini_api_key or None

    return ChatGoogleGenerativeAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=0,
    )


async def call_llm_with_retry(llm, messages, max_retries=3, agent_role: str = ""):
    """Call an LLM with retry on 429 rate limit errors (server retryDelay).

    Raises on final failure — the OpenRouter fallback lives in ``call_llm``
    (single fallback point, so agent temperature/max_tokens are honored).
    Retries are capped (default 3) so a heavily throttled key fails forward
    instead of sitting in backoff for minutes (the "stalled pipeline" symptom).
    """
    import logging
    import re
    log = logging.getLogger(__name__)

    last_error = None
    for attempt in range(max_retries):
        try:
            return await asyncio.wait_for(
                llm.ainvoke(messages), timeout=LLM_TIMEOUT
            )
        except asyncio.TimeoutError:
            log.warning(
                "[LLM] Call timed out after %.0fs — no more retries", LLM_TIMEOUT
            )
            raise
        except Exception as e:
            err_str = str(e)
            is_429 = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota exceeded" in err_str
            if is_429 and attempt < max_retries - 1:
                match = re.search(r'(?:retry(?:Delay)?\s*[:in]\s*)(\d+)(?:\.\d+)?s', err_str, re.IGNORECASE)
                wait = (int(match.group(1)) + 2) if match else (2 ** (attempt + 2)) + 5
                log.warning(
                    f"[LLM RateLimit] 429 / RESOURCE_EXHAUSTED. "
                    f"Retrying attempt {attempt + 1}/{max_retries} in {wait}s..."
                )
                last_error = e
                await asyncio.sleep(wait)
                continue
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
                model=_model_for(agent_role),
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
                model=_model_for(agent_role),
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
