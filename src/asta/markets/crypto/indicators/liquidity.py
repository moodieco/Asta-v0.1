"""Liquidity helpers specific to crypto volume."""

from __future__ import annotations

from typing import Optional, Sequence


def relative_volume_percentile(volumes: Sequence[float], window: int = 100) -> Optional[float]:
    """Percentile rank (0-100) of the last volume inside the trailing window."""
    window = int(window)
    if window <= 1 or len(volumes) < 2:
        return None
    history = [float(value) for value in volumes[-window:]]
    last = history[-1]
    below = sum(1 for value in history[:-1] if value <= last)
    return round(below / (len(history) - 1) * 100.0, 2)


def is_liquid_volume(
    volumes: Sequence[float], window: int = 100, min_percentile: float = 60.0
) -> bool:
    percentile = relative_volume_percentile(volumes, window)
    return percentile is not None and percentile >= min_percentile
