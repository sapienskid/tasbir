"""Keyed asyncio locks that clean up after themselves.

``KeyedLocks.hold(key)`` serializes coroutines that share a key (e.g. one
(task, format) pair) without letting the lock table grow without bound: an
entry lives only while somebody holds or awaits it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Hashable
from contextlib import asynccontextmanager


class KeyedLocks:
    def __init__(self) -> None:
        # key -> [lock, holders + waiters]
        self._locks: dict[Hashable, list] = {}

    @asynccontextmanager
    async def hold(self, key: Hashable) -> AsyncIterator[None]:
        entry = self._locks.get(key)
        if entry is None:
            entry = self._locks[key] = [asyncio.Lock(), 0]
        entry[1] += 1
        try:
            async with entry[0]:
                yield
        finally:
            entry[1] -= 1
            if entry[1] == 0 and self._locks.get(key) is entry:
                del self._locks[key]

    def __len__(self) -> int:
        return len(self._locks)
