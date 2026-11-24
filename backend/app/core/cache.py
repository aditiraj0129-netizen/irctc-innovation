"""A tiny in-process cache with expiry (TTL) and a size cap.

Proportional to the current product: one process, a handful of journeys. When the app runs as several
processes, swap this for a shared cache (e.g. Redis) behind the same get/put interface.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Hashable


class TTLCache:
    def __init__(self, ttl_seconds: float = 5.0, max_items: int = 512, clock=time.monotonic):
        self.ttl, self.max, self.clock = ttl_seconds, max_items, clock
        self._d: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = self.misses = 0

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            item = self._d.get(key)
            if item is None or self.clock() - item[0] > self.ttl:
                self._d.pop(key, None)
                self.misses += 1
                return None
            self._d.move_to_end(key)
            self.hits += 1
            return item[1]

    def put(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._d[key] = (self.clock(), value)
            self._d.move_to_end(key)
            while len(self._d) > self.max:
                self._d.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()
