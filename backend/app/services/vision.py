"""Shared Gemini Vision helper — multimodal (image + text) LLM calls.

Used by the verifier and the template/brand authoring agents. Vision calls
are serialized among themselves (a lock + min-interval knob) so the pipeline
paces the expensive vision path without serializing the whole pipeline.
"""

from __future__ import annotations

import asyncio
import base64
import logging

from app.config import get_settings
from app.core.loop_lock import loop_lock
from app.services.llm import DEFAULT_MODEL, LLM_TIMEOUT

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
    """Call a multimodal LLM with an image + text prompt.

    ``model`` is the primary; ``fallback_models`` are tried on timeout/504/429.
    Callers with a DB-backed agent config pass ``prompt_cfg.model`` and
    ``prompt_cfg.fallback_models`` so the Agents UI routing drives vision too.
    """
    from app.services.settings import get_runtime_setting

    min_interval = float(
        await get_runtime_setting("vision.min_interval_seconds", 5.0)
    )
    settings = get_settings()
    api_key = settings.gemini_api_key

    if not api_key:
        log.warning("[vision] No Gemini API key — raising (no silent auto-pass)")
        raise RuntimeError("Gemini API key not configured for visual analysis")

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    models = [m for m in ([model or DEFAULT_MODEL] + list(fallback_models or [])) if m]
    if not models:
        models = [DEFAULT_MODEL]

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=[
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
            },
            {"type": "text", "text": user_prompt},
        ]),
    ]

    last_error: Exception | None = None
    for mdl in models:
        llm = ChatGoogleGenerativeAI(
            model=mdl,
            google_api_key=api_key,
            max_output_tokens=max_tokens,
        )
        try:
            global _vision_last
            loop = asyncio.get_event_loop()
            async with loop_lock():
                elapsed = loop.time() - _vision_last
                if elapsed < min_interval:
                    await asyncio.sleep(min_interval - elapsed)
                _vision_last = loop.time()
                response = await asyncio.wait_for(
                    llm.ainvoke(messages),
                    timeout=LLM_TIMEOUT,
                )
            return _content_text(response)
        except Exception as e:  # noqa: BLE001
            last_error = e
            log.warning("[vision] model %s failed (%s) — trying next", mdl, e)

    raise last_error or RuntimeError("Vision LLM call failed")


def _content_text(response) -> str:
    content = response.content or ""
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                texts.append(block["text"])
            elif isinstance(block, str):
                texts.append(block)
        content = "\n".join(texts)
    return content
