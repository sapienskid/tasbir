"""LLM service — Google Gemini/Genma via LangChain ChatGoogleGenerativeAI.

All agents use this service. Provides both a high-level LangChain
integration (with tool binding support) and a simple call_llm() helper.
Model selection + per-role routing live in ``services.models`` (MODEL_ROUTES)
with DB-backed per-agent overrides; ``call_llm`` walks the primary → fallback
chain when a model times out / 504s / is rate-limited.
"""

import asyncio
from collections.abc import AsyncIterator

from app.config import get_settings

# Catch-all default when a role has no MODEL_ROUTES entry and no DB row.
# gemini-3.1-flash-lite is the reliable free text-out model.
DEFAULT_MODEL = "gemini-3.1-flash-lite"

# Hard per-call timeout so a stalled model request becomes an exception instead
# of hanging the pipeline forever. Generous (180s) because the free-tier models
# legitimately take 25-90s under load; the fallback chain handles models that
# exceed it.
LLM_TIMEOUT = 180.0


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
            is_retryable = (
                "429" in err_str
                or "RESOURCE_EXHAUSTED" in err_str
                or "Quota exceeded" in err_str
                or "504" in err_str
                or "DEADLINE_EXCEEDED" in err_str
            )
            if is_retryable and attempt < max_retries - 1:
                match = re.search(r'(?:retry(?:Delay)?\s*[:in]\s*)(\d+)(?:\.\d+)?s', err_str, re.IGNORECASE)
                wait = (int(match.group(1)) + 2) if match else (2 ** (attempt + 2)) + 5
                log.warning(
                    f"[LLM] 429/504. Retrying attempt {attempt + 1}/{max_retries} in {wait}s..."
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
    """Call the LLM with system + user prompt; walk the fallback model chain.

    Uses LangChain's ChatGoogleGenerativeAI under the hood. Tries the agent's
    primary model first, then its fallback_models on timeout/504/429. If
    Gemini+fallbacks all fail and an OpenRouter key is configured, falls back
    to OpenRouter.
    """
    import logging

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    log = logging.getLogger(__name__)

    from app.services.agents import get_agent_config

    cfg = await get_agent_config(agent_role)
    models = [m for m in ([cfg.model] + list(cfg.fallback_models or [])) if m]
    if not models:
        models = [DEFAULT_MODEL]

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    last_error: Exception | None = None
    for model in models:
        llm = ChatGoogleGenerativeAI(
            model=model,
            api_key=get_settings().gemini_api_key or None,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=0,
        )
        try:
            response = await call_llm_with_retry(llm, messages)
            return _response_text(response)
        except Exception as e:  # noqa: BLE001
            last_error = e
            log.warning(
                "[LLM] model %s failed for %r (%s) — trying next", model, agent_role, e
            )

    # All primary+fallback models failed → OpenRouter if configured.
    settings = get_settings()
    if settings.openrouter_api_key:
        try:
            return await _call_openrouter(
                api_key=settings.openrouter_api_key,
                model=models[0],
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as or_err:  # noqa: BLE001
            log.error("[LLM] OpenRouter fallback also failed: %s", or_err)
    raise last_error or RuntimeError("LLM call failed")


async def call_llm_for_tool(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    tool: dict,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> dict:
    """Call the LLM with one function-calling tool bound; return the args dict.

    Walks the same per-agent fallback model chain as :func:`call_llm`. The
    model is expected to emit a single ``generate_illustration``-style tool
    call; its ``args`` are returned. Raises if no tool call comes back.
    """
    _, args = await call_llm_for_tools(
        agent_role=agent_role,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tools=[tool],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return args


async def call_llm_for_tools(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> tuple[str, dict]:
    """Call the LLM with one or more function-calling tools bound.

    Walks the same per-agent fallback model chain as :func:`call_llm`. The
    model is expected to emit a single tool call. Returns ``(tool_name, args)``.
    Raises if no tool call comes back.
    """
    import logging

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    log = logging.getLogger(__name__)

    from app.services.agents import get_agent_config

    cfg = await get_agent_config(agent_role)
    models = [m for m in ([cfg.model] + list(cfg.fallback_models or [])) if m]
    if not models:
        models = [DEFAULT_MODEL]

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    last_error: Exception | None = None
    for model in models:
        llm = ChatGoogleGenerativeAI(
            model=model,
            api_key=get_settings().gemini_api_key or None,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=0,
        )
        try:
            bound = llm.bind_tools(tools)
            response = await call_llm_with_retry(bound, messages)
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                raise RuntimeError("model returned no tool call")
            args = tool_calls[0].get("args")
            if not isinstance(args, dict):
                raise RuntimeError(f"unexpected tool args: {args!r}")
            name = tool_calls[0].get("name") or tools[0]["function"]["name"]
            log.info("[llm] tool %r args=%r (model %s)", name, args, model)
            return (name, dict(args))
        except Exception as e:  # noqa: BLE001
            last_error = e
            log.warning(
                "[LLM] model %s tool call failed for %r (%s) — trying next", model, agent_role, e
            )

    log.warning("[LLM] tool-calling has no OpenRouter fallback; skipping (agent %s)", agent_role)
    raise last_error or RuntimeError("LLM tool call failed")


def _response_text(response) -> str:
    """Extract text from a LangChain AIMessage content (str or blocks)."""
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
