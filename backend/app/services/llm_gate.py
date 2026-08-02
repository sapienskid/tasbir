"""Global serialized LLM pace gate.

Every LLM call (text + vision) routes through this single async gate so the
pipeline never bursts past the provider's per-minute limits. A global
``asyncio.Lock`` serializes calls within the process (one worker → one gate),
and the minimum interval between ANY two LLM calls is a runtime-setting knob
(``llm.min_interval_seconds``) editable in the Studio without a restart.
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)

_lock = asyncio.Lock()
_last_call = 0.0


async def llm_gate() -> None:
    """Pace+serialize one LLM call. Call right before hitting the provider."""
    from app.services.settings import get_runtime_setting

    min_interval = float(await get_runtime_setting("llm.min_interval_seconds", 4.0))
    global _last_call
    loop = asyncio.get_event_loop()
    async with _lock:
        now = loop.time()
        wait = min_interval - (now - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = loop.time()
