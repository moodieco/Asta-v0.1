"""Signal deduplication.

A signal is a duplicate when the same scanner produced the same direction for
the same symbol/timeframe inside the dedup window. The window defaults to two
candles of the scanner timeframe, bounded by a configured maximum.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Tuple

from asta.core.signal_model import Signal
from asta.storage.cache import TTLCache
from asta.utils.logger import get_logger
from asta.utils.time_utils import parse_datetime, timeframe_to_seconds, utcnow


def dedup_window_hint(metadata) -> Optional[float]:
    """Per-signal dedup window carried in ``metadata`` (opt-in, per scanner).

    A session screener alerts once per symbol per day; a 5m candle scanner would
    otherwise re-alert every two candles. Unparseable or non-positive values
    fall back to the timeframe-derived window.
    """
    if not isinstance(metadata, dict):
        return None
    raw = metadata.get("dedup_window_seconds")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


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
        window = window_seconds
        if window is None:
            window = dedup_window_hint(getattr(signal, "metadata", None))
        if window is None:
            window = self.window_for(signal.timeframe)
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

    def warm_from_history(
        self, records: Iterable[Dict[str, Any]], now: Optional[datetime] = None
    ) -> int:
        """Re-claim keys for signals still inside their dedup window.

        The in-memory cache dies with the process, so without this a restart would
        re-alert the same setup (observed on a 15m volume spike).
        """
        now = now or utcnow()
        warmed = 0
        for record in records:
            try:
                key = "{}:{}:{}:{}:{}".format(
                    record["market"],
                    record["scanner_id"],
                    str(record["symbol"]).upper(),
                    record["timeframe"],
                    record["signal_type"],
                )
                timestamp = parse_datetime(str(record["timestamp"]))
            except (KeyError, TypeError, ValueError):
                continue
            window = dedup_window_hint(record.get("metadata")) or self.window_for(
                str(record.get("timeframe", ""))
            )
            remaining = window - (now - timestamp).total_seconds()
            if remaining > 0:
                self.cache.set(key, record.get("signal_id", "warm"), ttl=remaining)
                warmed += 1
        if warmed:
            self.logger.info("dedup cache warmed from history", extra={"keys": warmed})
        return warmed

    def purge(self) -> int:
        return self.cache.purge()

    def size(self) -> int:
        return len(self.cache)

    def clear(self) -> None:
        self.cache.clear()
