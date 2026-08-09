"""O4: process-local TTL cache for memory read results.

``read_bucket`` is a high-frequency teaching read (ReadMemoryTool / Memory
page); re-reading the same bucket files every call is wasteful. We cache
the assembled result in-process for 30s. Leaf module so both
:mod:`deeptutor.services.memory.store` (the read path) and the
consolidator write paths can invalidate without a store↔consolidator import
cycle.
"""

from __future__ import annotations

import time as _time
from typing import Callable

_READ_CACHE_TTL_S = 30.0
_read_cache: dict[tuple, tuple[float, str]] = {}


def cached_read(key: tuple, producer: Callable[[], str]) -> str:
    """Return ``producer()`` result, cached for ``_READ_CACHE_TTL_S``."""
    now = _time.monotonic()
    hit = _read_cache.get(key)
    if hit is not None and now - hit[0] < _READ_CACHE_TTL_S:
        return hit[1]
    value = producer()
    _read_cache[key] = (now, value)
    return value


def invalidate() -> None:
    """Drop all cached read results after any memory write.

    Read memory is a high-frequency teaching op, so a write must be visible
    to the very next read — otherwise the cache would hide new memories for
    up to ``_READ_CACHE_TTL_S``.
    """
    _read_cache.clear()
