"""Signal deduplication.

A signal is a duplicate when the same scanner produced the same direction for
the same symbol/timeframe inside the dedup window. The window defaults to two
candles of the scanner timeframe, bounded by a configured maximum.
"""

from __future__ import annotations

from typing import Optional, Tuple

from asta.core.signal_model import Signal
from asta.storage.cache import TTLCache
from asta.utils.logger import get_logger
from asta.utils.time_utils import timeframe_to_seconds


class DeduplicationStore:
    def __init__(self, window_seconds: int = 3600, cache: Optional[TTLCache] = None):
        self.max_window_seconds = int(window_seconds)
        self.cache = cache if cache is not None else TTLCache(default_ttl=window_seconds)
        self.logger = get_logger("asta.dedup")

    def window_for(self, timeframe: str, factor: float = 2.0) -> float:
        try:
            candle_window = timeframe_to_seconds(timeframe) * factor
        except ValueError:
            candle_window = float(self.max_window_seconds)
        return float(min(candle_window, self.max_window_seconds))

    def is_duplicate(self, signal: Signal) -> bool:
        return self.cache.get(signal.dedup_key) is not None

    def register(self, signal: Signal, window_seconds: Optional[float] = None) -> None:
        window = window_seconds if window_seconds is not None else self.window_for(signal.timeframe)
        self.cache.set(signal.dedup_key, signal.signal_id, ttl=window)

    def check_and_register(self, signal: Signal) -> Tuple[bool, Optional[float]]:
        """Return ``(is_new, remaining_ttl_of_existing)`` and claim the key."""
        remaining = self.cache.ttl(signal.dedup_key)
        if remaining is not None:
            return False, remaining
        self.register(signal)
        return True, None

    def release(self, signal: Signal) -> None:
        """Undo a claim (used when validation later fails)."""
        self.cache.delete(signal.dedup_key)

    def purge(self) -> int:
        return self.cache.purge()

    def size(self) -> int:
        return len(self.cache)

    def clear(self) -> None:
        self.cache.clear()
