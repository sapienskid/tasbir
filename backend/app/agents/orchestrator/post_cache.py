"""Per-post cache shared across parallel per-format branches.

Each format branch deep-copies the base state, so caches stored in ``state``
are invisible to sibling branches running under ``asyncio.gather``. This
module keeps a small process-wide, task-keyed cache so LLM media-director calls
(e.g. one illustration or photo search per post) run once even when several
formats race for them.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Awaitable, Callable, TypeVar

from app.core.loop_lock import loop_lock

log = logging.getLogger(__name__)

T = TypeVar("T")

_cache: "OrderedDict[str, dict[str, object]]" = OrderedDict()
_MAX_ENTRIES = 64


async def post_cached(task_id: str, key: str, loader: Callable[[], Awaitable[T]]) -> T | None:
    """Return the cached value for (task_id, key), computing it once via loader."""
    if not task_id:
        return await loader()

    async with loop_lock():
        entry = _cache.setdefault(task_id, {})
        if key in entry:
            return entry[key]  # type: ignore[return-value]
        if len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)
        value = await loader()
        entry[key] = value
        return value  # type: ignore[return-value]


def post_cache_clear(task_id: str) -> None:
    """Drop a task's cached media (called when the task completes/fails)."""
    if task_id in _cache:
        del _cache[task_id]
