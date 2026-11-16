"""Asia range breakout (ICT AMD shape), shared implementation.

Accumulation = the Asian session range (default 19:00-00:00 New York),
manipulation = one side getting taken, distribution = the run through the other
side. The classic retail version of this setup is a stop order at each edge with
the opposite edge as the stop; ASTA has no order management, so the break itself
is the signal:

    range window  19:00-00:00 NY   -> high / low of that session
    trigger       first candle that *closes* through an edge (the losing side is
                  never alerted, which is the practical OCO)
    stop          the opposite edge
    cutoff        13:30 NY by default - no new breaks after that

``require_sweep`` is the stricter ICT variant: only take a break when price
already raided the opposite edge first (stop hunt), otherwise skip it.

Session times are evaluated in ``America/New_York`` so DST is handled by the
tz database instead of a hardcoded UTC offset.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from datetime import time as dtime
from typing import List, Tuple
from zoneinfo import ZoneInfo

from asta.core.indicators import atr
from asta.core.signal_model import Candle, ScanContext, SignalType
from asta.core.strategy import Strategy, StrategyResult

NY = ZoneInfo("America/New_York")


def parse_hhmm(value: str) -> dtime:
    """Parse ``"19:00"`` into :class:`datetime.time`."""
    raw = str(value).strip()
    hour, _, minute = raw.partition(":")
    return dtime(int(hour), int(minute or 0))


def ny_time(timestamp: datetime) -> datetime:
    return timestamp.astimezone(NY)


def session_window(day: datetime, start: dtime, end: dtime) -> Tuple[datetime, datetime]:
    """The most recent completed session window, as aware NY datetimes.

    ``end`` is exclusive and normally 00:00, so the window belongs to the
    previous calendar day (19:00 -> 00:00 crosses midnight).
    """
    end_date: date = day.date()
    end_at = datetime.combine(end_date, end, tzinfo=NY)
    start_date = end_date if start < end else end_date - timedelta(days=1)
    start_at = datetime.combine(start_date, start, tzinfo=NY)
    return start_at, end_at


class AsiaRangeBreakoutStrategy(Strategy):
    name = "Asia Range Breakout"
    default_params = {
        # session window in New York time; end is exclusive
        "session_start": "19:00",
        "session_end": "00:00",
        # no new breaks after this NY time (the strategy's own time exit)
        "cutoff": "13:30",
        "buffer_pct": 0.0,
        "min_range_atr": 0.35,
        "max_range_atr": 3.0,
        "max_distance_atr": 1.5,
        "require_sweep": False,
        "atr_period": 14,
        "reward_ratio": 2.0,
        "min_confidence": 0.55,
        "min_candles": 40,
    }

    # -- session helpers --------------------------------------------------
    def _window(self, now: datetime) -> Tuple[datetime, datetime]:
        return session_window(
            now,
            parse_hhmm(self.param("session_start")),
            parse_hhmm(self.param("session_end")),
        )

    def _range(self, candles: List[Candle], start: datetime, end: datetime):
        window = [c for c in candles if start <= c.timestamp < end]
        if len(window) < 2:
            return None
        return max(c.high for c in window), min(c.low for c in window), len(window)

    # -- evaluation -------------------------------------------------------
    def evaluate(self, context: ScanContext) -> List[StrategyResult]:
        context.require(int(self.param("min_candles")))
        now = ny_time(context.now)
        if now.time() >= parse_hhmm(self.param("cutoff")):
            return []  # past the time exit, no new pending orders

        start, end = self._window(now)
        current = self._range(context.candles, start, end)
        if current is None:
            return []
        high, low, bars = current
        if high <= low:
            return []

        atr_value = atr(context.candles, int(self.param("atr_period")))
        if not atr_value or atr_value <= 0:
            return []
        range_atr = (high - low) / atr_value
        if not float(self.param("min_range_atr")) <= range_atr <= float(self.param("max_range_atr")):
            return []  # holiday tape / news-blown range, skip

        # only candles after the window belongs to the breakout leg
        after = [c for c in context.candles if c.timestamp >= end]
        if len(after) < 2:
            return []
        previous, last = after[-2], after[-1]
        if last.timestamp < end:
            return []

        buffer_pct = float(self.param("buffer_pct"))
        # OCO: the first close outside the range takes the trade, the other side
        # is cancelled. A later re-break of the same range is not a new setup.
        if any(c.close > high or c.close < low for c in after[:-1]):
            return []
        long_break = previous.close <= high and last.close > high * (1.0 + buffer_pct)
        short_break = previous.close >= low and last.close < low * (1.0 - buffer_pct)
        if not (long_break or short_break):
            return []

        is_long = bool(long_break)
        distance_atr = abs(last.close - (high if is_long else low)) / atr_value
        if distance_atr > float(self.param("max_distance_atr")):
            return []  # gapped straight through the level - chasing

        swept = self._swept(after[:-1], low=low, high=high, is_long=is_long)
        if self.param("require_sweep") and not swept:
            return []

        confidence = 0.55
        confidence += 0.05 if swept else 0.0
        confidence += 0.05 if range_atr <= 1.2 else 0.0
        if confidence < float(self.param("min_confidence")):
            return []

        level = high if is_long else low
        opposite = low if is_long else high
        side = "high" if is_long else "low"
        reason = (
            "Asia range {:.5f}-{:.5f} ({:.2f} ATR, {} bars) broken to the {}: "
            "close {:.5f} through the {} {:.5f}{}."
        ).format(
            low,
            high,
            range_atr,
            bars,
            "upside" if is_long else "downside",
            last.close,
            side,
            level,
            ", after sweeping the opposite edge" if swept else "",
        )

        return [
            StrategyResult(
                signal_type=SignalType.LONG if is_long else SignalType.SHORT,
                confidence=round(min(confidence, 1.0), 3),
                reason=reason,
                indicators={
                    "range_high": round(high, 6),
                    "range_low": round(low, 6),
                    "range_atr": round(range_atr, 3),
                    "atr": round(float(atr_value), 6),
                    "distance_atr": round(distance_atr, 3),
                },
                metadata={
                    "session_start": start.isoformat(),
                    "session_end": end.isoformat(),
                    "session_bars": bars,
                    "swept_opposite": swept,
                    "entry_style": "stop",
                    "exit_style": "time",
                },
                price=level,
                stop_loss=opposite,
            )
        ]

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _swept(candles: List[Candle], low: float, high: float, is_long: bool) -> bool:
        """Did price raid the opposite edge before this break (stop hunt)?"""
        if is_long:
            return any(c.low < low for c in candles)
        return any(c.high > high for c in candles)
