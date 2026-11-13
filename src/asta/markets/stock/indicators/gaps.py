"""Overnight gap helpers for daily stock bars."""

from __future__ import annotations

from typing import Optional, Sequence

from asta.core.signal_model import Candle


def overnight_gap_pct(candles: Sequence[Candle]) -> Optional[float]:
    """(today's open - yesterday's close) / yesterday's close * 100."""
    if len(candles) < 2:
        return None
    previous_close = candles[-2].close
    if not previous_close:
        return None
    return (candles[-1].open - previous_close) / previous_close * 100.0


def is_gap_up(candles: Sequence[Candle], threshold_pct: float = 1.0) -> bool:
    gap = overnight_gap_pct(candles)
    return gap is not None and gap >= threshold_pct


def is_gap_down(candles: Sequence[Candle], threshold_pct: float = 1.0) -> bool:
    gap = overnight_gap_pct(candles)
    return gap is not None and gap <= -threshold_pct
