"""Thread-safe in-memory TTL cache (dedup + provider memoisation)."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple


class TTLCache:
    def __init__(self, default_ttl: float = 3600.0, clock: Optional[Callable[[], float]] = None):
        self.default_ttl = float(default_ttl)
        self._clock = clock or time.monotonic
        self._data: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.RLock()

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expires = self._clock() + (self.default_ttl if ttl is None else float(ttl))
        with self._lock:
            self._data[key] = (value, expires)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return default
            value, expires = entry
            if expires <= self._clock():
                self._data.pop(key, None)
                return default
            return value

    def ttl(self, key: str) -> Optional[float]:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            _, expires = entry
            remaining = expires - self._clock()
            if remaining <= 0:
                self._data.pop(key, None)
                return None
            return remaining

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._data.pop(key, None) is not None

    def purge(self) -> int:
        now = self._clock()
        with self._lock:
            stale = [key for key, (_, expires) in self._data.items() if expires <= now]
            for key in stale:
                self._data.pop(key, None)
            return len(stale)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def keys(self):
        self.purge()
        with self._lock:
            return list(self._data)

    def __len__(self) -> int:
        self.purge()
        with self._lock:
            return len(self._data)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None
