"""Shared Gemini Vision helper — multimodal (image + text) LLM calls.

Used by the verifier and the template/brand authoring agents. Serializes
vision calls and spaces them out to respect the free-tier rate limit.
"""

from __future__ import annotations

import asyncio
import base64
import logging

from app.config import get_settings
from app.services.llm import DEFAULT_MODEL

log = logging.getLogger(__name__)

_VISION_LOCK = asyncio.Lock()
_VISION_LAST_CALL = 0.0
_VISION_MIN_INTERVAL = 5.0  # seconds between vision LLM calls


async def call_vision_llm(
    system_prompt: str,
    user_prompt: str,
    image_bytes: bytes,
    temperature: float = 0.3,
    max_tokens: int = 1200,
    model: str | None = None,
) -> str:
    """Call a multimodal LLM with an image + text prompt.

    ``model`` is optional — callers with a DB-backed agent config pass
    ``prompt_cfg.model`` so the Agents UI model selection actually drives the
    vision call. Defaults to the shared route default.
    """
    from app.services.settings import get_runtime_setting

    min_interval = float(
        await get_runtime_setting("vision.min_interval_seconds", _VISION_MIN_INTERVAL)
    )
    settings = get_settings()
    api_key = settings.gemini_api_key

    if not api_key:
        log.warning("[vision] No Gemini API key — raising (no silent auto-pass)")
        raise RuntimeError("Gemini API key not configured for visual analysis")

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=model or DEFAULT_MODEL,
            google_api_key=api_key,
            max_output_tokens=max_tokens,
        )

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

        global _VISION_LAST_CALL
        loop = asyncio.get_event_loop()
        async with _VISION_LOCK:
            elapsed = loop.time() - _VISION_LAST_CALL
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            _VISION_LAST_CALL = loop.time()
            response = await llm.ainvoke(messages)

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

    except Exception as e:
        log.error("[vision] Vision LLM call failed: %s", e)
        raise
