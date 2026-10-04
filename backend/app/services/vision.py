"""Shared Vision helper — multimodal (image + text) calls via Cloudflare AI Gateway.

Used by the verifier and the template/brand authoring agents. Vision calls
are serialized among themselves (a lock + min-interval knob) so the pipeline
paces the expensive vision path without serializing the whole pipeline.

Transport is the Gateway compat endpoint with ``image_url`` parts (verified
live through the ``tasbir-vision`` route). No direct provider calls.
"""

from __future__ import annotations

import asyncio
import base64
import logging

from app.core.loop_lock import loop_lock
from app.services.llm import (
    DEFAULT_MODEL,
    _compat_post,
    _message_text,
    gateway_route_for_role,
)

log = logging.getLogger(__name__)

_vision_last = 0.0


async def call_vision_llm(
    system_prompt: str,
    user_prompt: str,
    image_bytes: bytes,
    temperature: float = 0.3,
    max_tokens: int = 1200,
    model: str | None = None,
    fallback_models: list[str] | None = None,
) -> str:
    """Call a multimodal LLM with an image + text prompt — via the Gateway.

    Tries the ``tasbir-vision`` dynamic route first, then ``model`` and each
    fallback as ``google-ai-studio/{model}``. Raises when all fail (fail-loud:
    callers decide whether to auto-pass, never this helper).
    Callers with a DB-backed agent config pass ``prompt_cfg.model`` and
    ``prompt_cfg.fallback_models`` so the Agents UI routing drives vision too.
    """
    from app.services.llm import gateway_model_name
    from app.services.settings import get_runtime_setting

    min_interval = float(
        await get_runtime_setting("vision.min_interval_seconds", 5.0)
    )

    models = [m for m in ([model or DEFAULT_MODEL] + list(fallback_models or [])) if m]
    if not models:
        models = [DEFAULT_MODEL]
    targets = [gateway_route_for_role("verifier")]
    for m in models:
        name = gateway_model_name(m)
        if name not in targets:
            targets.append(name)

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        ]},
    ]

    last_error: Exception | None = None
    for target in targets:
        try:
            global _vision_last
            loop = asyncio.get_event_loop()
            async with loop_lock():
                elapsed = loop.time() - _vision_last
                if elapsed < min_interval:
                    await asyncio.sleep(min_interval - elapsed)
                _vision_last = loop.time()
                data, served = await _compat_post({
                    "model": target,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                })
            text = _message_text(data["choices"][0]["message"])
            if not text:
                raise RuntimeError("Gateway returned empty completion")
            log.info("[vision] %s served by %s", target, served or "?")
            return text
        except Exception as e:  # noqa: BLE001
            last_error = e
            log.warning("[vision] %s failed (%s) — trying next", target, e)

    raise last_error or RuntimeError("Vision LLM call failed")
