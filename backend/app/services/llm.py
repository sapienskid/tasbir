"""LLM service — 100% of generation traffic goes through Cloudflare AI Gateway.

Transport is the Gateway compat endpoint (OpenAI chat shape), verified live:
- plain chat → ``model: dynamic/tasbir-{tier}`` or ``google-ai-studio/{model}``
- tools → same endpoint with a ``tools`` array; ``tool_calls`` come back on
  the assistant message (verified through both a route and a direct model)
- vision → same endpoint with ``image_url`` parts (verified through a route)

There are no direct provider calls, no LangChain, no OpenRouter fallback.
The Gateway holds the Google AI Studio key server-side (BYOK) — nothing
calls `googleapis.com` directly, and this module never even sends the key. If every Gateway attempt fails,
the call raises and the pipeline records the failure (fail-loud, no silent
direct fallback that would bypass quotas, logging, and caching).

Model selection + per-role routing live in ``services.models``
(MODEL_ROUTES) with DB-backed per-agent overrides; every entry point below
walks route → model chain when the Gateway errors.
"""

from __future__ import annotations

import json
import logging
import re

from app.config import get_settings

log = logging.getLogger(__name__)

# Catch-all default when a role has no MODEL_ROUTES entry and no DB row.
# gemini-3.1-flash-lite is the reliable free text-out model.
DEFAULT_MODEL = "gemini-3.1-flash-lite"

# Hard per-call timeout so a stalled model request becomes an exception instead
# of hanging the pipeline forever. Generous (180s) because the free-tier models
# legitimately take 25-90s under load; the model chain handles the rest.
LLM_TIMEOUT = 180.0

# Loop guard for call_llm_tool_loop: if the model calls the same tool with the
# same args this many times, force a final answer instead of looping forever.
MAX_REPEAT_TOOL = 3

# The ONLY network endpoint this module talks to: Cloudflare AI Gateway,
# OpenAI-compatible shape. (The unified ``api.cloudflare.com/.../ai/v1``
# path was probed live: ``google-ai-studio/`` 404s there and ``google/``
# bills Gateway credits (402) — so compat is the single path.)
_COMPAT_PATH = "https://gateway.ai.cloudflare.com/v1/{account}/{gateway}/compat/chat/completions"

# Route responses wrap reasoning in <thought> blocks (Gemma) — strip them so
# agents never see chain-of-thought preamble as content.
_THOUGHT_RE = re.compile(r"<thought>.*?</thought>\s*", re.DOTALL)


def gateway_configured() -> bool:
    """True when Cloudflare Gateway credentials are present."""
    settings = get_settings()
    return bool(settings.resolved_cf_account_id and settings.resolved_cf_token)


def gateway_route_for_role(agent_role: str) -> str:
    """Dynamic route name for an agent tier (server-side failover).

    Tiers mirror the pipeline's latency/quality needs; the actual
    primary → fallback chains live in the Gateway UI (versioned, no deploy).
    """
    from app.services.models import GATEWAY_TIERS

    for tier, roles in GATEWAY_TIERS.items():
        if agent_role in roles:
            return f"dynamic/tasbir-{tier}"
    return "dynamic/tasbir-fast"


def gateway_model_name(model: str, for_api_path: bool = False) -> str:
    """Map a bare model id to its Gateway provider-qualified name.

    The Google slug is ``google-ai-studio/{model}`` — the ``google/`` slug
    returns ``400 Model not found`` even for models the account can serve
    (verified live). ``for_api_path`` is kept for symmetry; both paths use
    the same slug now.

    Pass-through for already-qualified (``provider/model``) and
    ``dynamic/`` route names.
    """
    if "/" in model or model.startswith("dynamic/"):
        return model
    return f"google-ai-studio/{model}"


def _compat_url_and_headers() -> tuple[str, dict]:
    settings = get_settings()
    if not gateway_configured():
        raise RuntimeError("Cloudflare AI Gateway not configured")
    url = _COMPAT_PATH.format(
        account=settings.resolved_cf_account_id,
        gateway=settings.cf_gateway_id or "tasbir",
    )
    return url, {
        "cf-aig-authorization": f"Bearer {settings.resolved_cf_token}",
        "Content-Type": "application/json",
    }


async def _compat_post(payload: dict) -> tuple[dict, str | None]:
    """POST one OpenAI-shaped payload to the Gateway compat endpoint.

    Returns ``(response_json, served_model)`` where the served model comes
    from the ``cf-aig-model`` header when present. Raises on HTTP errors.
    """
    import httpx

    url, headers = _compat_url_and_headers()
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post(url, headers=headers, json=payload)
        try:
            resp.raise_for_status()
        except Exception:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if not isinstance(data, dict) or not data.get("choices"):
            raise RuntimeError("Gateway returned empty completion")
        return data, resp.headers.get("cf-aig-model")


def _strip_thought(text: str) -> str:
    """Remove <thought> reasoning wrappers route models prepend."""
    return _THOUGHT_RE.sub("", text or "").strip()


def _message_text(message: dict) -> str:
    """Extract plain text from an OpenAI assistant message (str or parts)."""
    content = message.get("content")
    if isinstance(content, str):
        return _strip_thought(content)
    if isinstance(content, list):
        texts = []
        for b in content:
            if isinstance(b, str):
                texts.append(b)
            elif isinstance(b, dict):
                if b.get("type") == "text":
                    texts.append(b.get("text", ""))
                elif "text" in b and isinstance(b["text"], str):
                    texts.append(b["text"])
        return _strip_thought("".join(texts))
    return _strip_thought(str(content or ""))


def _parse_tool_calls(message: dict) -> list[dict]:
    """Normalize OpenAI tool_calls → [{id, name, args}].

    Provider extras (e.g. ``extra_content.google.thought_signature``) are
    dropped — only the standard fields are echoed back on later turns.
    Unparseable ``arguments`` degrade to ``{}`` instead of crashing the loop.
    """
    out: list[dict] = []
    for call in message.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        fn = call.get("function") or {}
        name = fn.get("name") or ""
        raw_args = fn.get("arguments") or {}
        if isinstance(raw_args, dict):
            args = raw_args
        elif isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args or "{}")
                args = parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, ValueError):
                args = {}
        else:
            args = {}
        if not name:
            continue
        out.append({
            "id": call.get("id") or "",
            "name": name,
            "args": args,
        })
    return out


def _assistant_echo(content: str | None, calls: list[dict]) -> dict:
    """Rebuild a clean assistant message for the next loop turn."""
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": c["id"],
                "type": "function",
                "function": {"name": c["name"], "arguments": json.dumps(c["args"])},
            }
            for c in calls
        ],
    }


async def _attempt_targets(
    agent_role: str, models: list[str], skip_route: bool = False
) -> list[str]:
    """Ordered Gateway model names: dynamic route first, then each model."""
    _ = agent_role  # routing is by tier map, kept explicit for readability
    targets: list[str] = []
    if not skip_route:
        targets.append(gateway_route_for_role(agent_role))
    for m in models:
        name = gateway_model_name(m)
        if name not in targets:
            targets.append(name)
    return targets


async def call_llm(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    model_override: str | None = None,
) -> str:
    """Call the LLM with system + user prompt — always via the Gateway.

    Tries the role's dynamic route first (server-side failover), then each
    model in the agent's chain as ``google-ai-studio/{model}``. An explicit
    ``model_override`` pins the chain to that model (still via the Gateway —
    overrides no longer bypass it). Raises when every attempt fails.
    """
    from app.services.agents import get_agent_config

    cfg = await get_agent_config(agent_role)
    models = [m for m in ([cfg.model] + list(cfg.fallback_models or [])) if m]
    if not models:
        models = [DEFAULT_MODEL]
    if model_override:
        models = [model_override] + [m for m in models if m != model_override]

    # Free-tier budget: reserve against the primary before spending it. Gemma
    # is capped at 16K tokens/min, so a long article can blow the whole
    # minute's budget on one call — this waits for the window instead of
    # letting the provider 429 mid-pipeline.
    from app.services.model_quota import estimate_tokens, reserve

    est = estimate_tokens(system_prompt) + estimate_tokens(user_prompt) + max_tokens
    if not await reserve(models[0], est, max_wait=45.0):
        log.warning(
            "[LLM] quota reservation failed for %s (%s, ~%d tokens) — trying anyway",
            models[0], agent_role, est,
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    last_error: Exception | None = None
    for target in await _attempt_targets(agent_role, models, skip_route=bool(model_override)):
        try:
            data, served = await _compat_post({
                "model": target,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            })
            text = _message_text(data["choices"][0]["message"])
            if not text:
                raise RuntimeError("Gateway returned empty completion")
            log.info("[LLM] %s served by %s (%s)", target, served or "?", agent_role)
            return text
        except Exception as e:  # noqa: BLE001
            last_error = e
            log.warning("[LLM] %s failed for %r (%s) — trying next", target, agent_role, e)
    raise last_error or RuntimeError("LLM call failed")


async def call_llm_for_tool(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    tool: dict,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> dict:
    """Call the LLM with one function-calling tool bound — via the Gateway.

    Walks the same route → model chain as :func:`call_llm`. Returns the
    first tool call's ``args`` dict. Raises if no attempt yields a tool call.
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
    """Call the LLM with function-calling tools bound — via the Gateway.

    Returns ``(tool_name, args)`` for the first tool call. Raises if no
    attempt yields a tool call.
    """
    from app.services.agents import get_agent_config

    cfg = await get_agent_config(agent_role)
    models = [m for m in ([cfg.model] + list(cfg.fallback_models or [])) if m]
    if not models:
        models = [DEFAULT_MODEL]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    last_error: Exception | None = None
    for target in await _attempt_targets(agent_role, models):
        try:
            data, served = await _compat_post({
                "model": target,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": temperature,
                "max_tokens": max_tokens,
            })
            calls = _parse_tool_calls(data["choices"][0]["message"])
            if not calls:
                raise RuntimeError("model returned no tool call")
            log.info("[llm] tool %r args=%r (%s served by %s)",
                     calls[0]["name"], calls[0]["args"], target, served or "?")
            return calls[0]["name"], dict(calls[0]["args"])
        except Exception as e:  # noqa: BLE001
            last_error = e
            log.warning("[LLM] %s tool call failed for %r (%s) — trying next",
                        target, agent_role, e)
    raise last_error or RuntimeError("LLM tool call failed")


async def call_llm_tool_loop(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[dict],
    handlers: dict,
    max_turns: int = 4,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Multi-turn function-calling loop — via the Gateway.

    Each ``name -> async (args) -> str`` entry in ``handlers`` executes a tool
    and returns the result text fed back to the model as a ``tool`` message.
    The loop runs until the model stops calling tools (its final text is
    returned) or ``max_turns`` is exhausted. The whole loop runs against one
    Gateway target; transport errors fail over to the next target with a
    fresh message list (handlers are read-only searches or pure renders, so
    re-running them is safe). Returns "" if no target produced an answer.

    Loop guard: a same-tool-same-input counter (circuit breaker) — after
    ``MAX_REPEAT_TOOL`` identical calls the tools are dropped and one final
    text-only call runs.
    """
    from collections import Counter

    from app.services.agents import get_agent_config

    cfg = await get_agent_config(agent_role)
    models = [m for m in ([cfg.model] + list(cfg.fallback_models or [])) if m]
    if not models:
        models = [DEFAULT_MODEL]

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    last_error: Exception | None = None

    for target in await _attempt_targets(agent_role, models):
        messages = [dict(m) for m in base_messages]
        try:
            call_counts: Counter[str] = Counter()
            for _turn in range(max_turns):
                data, _served = await _compat_post({
                    "model": target,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                })
                assistant = data["choices"][0]["message"]
                calls = _parse_tool_calls(assistant)
                text = _message_text(assistant)
                if not calls:
                    return text or ""
                messages.append(_assistant_echo(text or None, calls))
                for call in calls:
                    name = call["name"]
                    args = call["args"]
                    handler = handlers.get(name)
                    if handler is None:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": f"Unknown tool: {name}",
                        })
                        continue
                    result = await handler(args)
                    log.info("[llm] tool %r args=%r (%s)", name, args, target)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result or "ok",
                    })
                    # Circuit breaker: the same tool called repeatedly with the
                    # same input is a loop, not progress. Drop the tools and
                    # force the final answer as plain text.
                    key = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
                    call_counts[key] += 1
                    if call_counts[key] >= MAX_REPEAT_TOOL:
                        log.warning(
                            "[llm] tool %r called %d times identically — forcing final answer",
                            name, call_counts[key],
                        )
                        messages.append({
                            "role": "system",
                            "content": (
                                "You keep calling the same tool with the same input. "
                                "STOP calling tools now. Output your final answer as "
                                "plain text (the JSON plan) immediately."
                            ),
                        })
                        forced, _ = await _compat_post({
                            "model": target,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        })
                        return _message_text(forced["choices"][0]["message"])
            log.warning("[LLM] tool loop exceeded %d turns (%s)", max_turns, agent_role)
            return ""
        except Exception as e:  # noqa: BLE001
            last_error = e
            log.warning("[LLM] %s tool loop failed for %r (%s) — trying next",
                        target, agent_role, e)

    if last_error:
        log.warning("[LLM] tool loop exhausted all targets for %s", agent_role)
    return ""
