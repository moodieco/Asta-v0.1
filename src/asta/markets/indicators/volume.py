"""Volume indicators and spike detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from asta.core.signal_model import Candle


def volume_sma(volumes: Sequence[float], period: int = 20, exclude_last: bool = False) -> Optional[float]:
    period = int(period)
    if period <= 0:
        return None
    window = list(volumes[:-1] if exclude_last else volumes)
    if len(window) < period:
        return None
    return sum(float(v) for v in window[-period:]) / period


def volume_ratio(volumes: Sequence[float], period: int = 20) -> Optional[float]:
    """Last candle volume divided by the average of the previous ``period``."""
    average = volume_sma(volumes, period, exclude_last=True)
    if not average:
        return None
    return float(volumes[-1]) / average


@dataclass(frozen=True)
class VolumeSpike:
    ratio: float
    direction: str  # "up" | "down"
    body_ratio: float


def detect_volume_spike(
    candles: Sequence[Candle],
    period: int = 20,
    multiplier: float = 2.5,
) -> Optional[VolumeSpike]:
    """Detect an unusually large volume bar and infer direction from the body."""
    if len(candles) < period + 1:
        return None
    ratio = volume_ratio([c.volume for c in candles], period)
    if ratio is None or ratio < multiplier:
        return None
    last = candles[-1]
    body_ratio = last.body / last.range if last.range > 0 else 0.0
    if body_ratio < 0.3:  # doji with huge volume = indecision, not a signal
        return None
    return VolumeSpike(ratio=ratio, direction="up" if last.is_bullish else "down", body_ratio=body_ratio)
