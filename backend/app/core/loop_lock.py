"""Per-event-loop locks, safe under Celery prefork.

A module-level ``asyncio.Lock()`` binds to the first event loop that awaits it.
Under Celery prefork every task runs a fresh event loop, so the second task in a
process would raise "bound to a different event loop". Scoping the lock to the
running loop keeps genuine serialization for concurrent coroutines (the
``asyncio.gather`` format branches) while never leaking across loops.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Dict

_locks: "Dict[asyncio.AbstractEventLoop, asyncio.Lock]" = {}
_guard = threading.Lock()
_MAX_TRACKED_LOOPS = 16


def loop_lock() -> asyncio.Lock:
    """Return an ``asyncio.Lock`` scoped to the currently running event loop."""
    loop = asyncio.get_running_loop()
    with _guard:
        lock = _locks.get(loop)
        if lock is None:
            if len(_locks) >= _MAX_TRACKED_LOOPS:
                for tracked in [x for x, _ in _locks.items() if not x.is_running()]:
                    _locks.pop(tracked, None)
            lock = asyncio.Lock()
            _locks[loop] = lock
    return lock
