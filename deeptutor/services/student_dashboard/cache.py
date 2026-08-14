from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
import threading
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class DashboardCacheKey:
    profile_id: str
    view: str
    profile_data_version: int
    learning_data_version: str
    task_version: int


class StudentDashboardCache:
    """Small process-local LRU for rebuildable student dashboard projections."""

    def __init__(self, max_entries: int = 64) -> None:
        self.max_entries = max(1, int(max_entries))
        self._items: OrderedDict[DashboardCacheKey, dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()

    def get_or_build(
        self,
        key: DashboardCacheKey,
        builder: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            cached = self._items.get(key)
            if cached is not None:
                self._items.move_to_end(key)
                return deepcopy(cached)

        value = builder()
        with self._lock:
            # A newer version for the same profile/view makes older projections
            # unreachable. Drop them immediately instead of waiting for LRU.
            stale = [
                item_key
                for item_key in self._items
                if item_key.profile_id == key.profile_id and item_key.view == key.view
            ]
            for item_key in stale:
                self._items.pop(item_key, None)
            self._items[key] = deepcopy(value)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)
        return deepcopy(value)

    def invalidate_profile(self, profile_id: str) -> int:
        with self._lock:
            keys = [key for key in self._items if key.profile_id == profile_id]
            for key in keys:
                self._items.pop(key, None)
            return len(keys)


dashboard_cache = StudentDashboardCache()


__all__ = ["DashboardCacheKey", "StudentDashboardCache", "dashboard_cache"]
