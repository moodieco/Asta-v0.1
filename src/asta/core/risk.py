"""Risk levels for a signal: entry, stop loss, take profit, R:R, expiry.

Strategies may supply a *structural* stop (pivot low, breakout level, swing low).
When they do not, the stop is ATR based. Take profit always comes from the
reward multiple unless the strategy provides an explicit target.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from asta.core.signal_model import SignalType
from asta.utils.time_utils import timeframe_to_seconds

DEFAULT_RISK_PARAMS: Dict[str, Any] = {
    "atr_period": 14,
    "atr_stop_multiplier": 1.5,
    "reward_ratio": 2.0,
    "min_risk_pct": 0.10,
    "max_risk_pct": 5.0,
    "max_bars": 48,
    "stop_buffer_pct": 0.001,
}


@dataclass(frozen=True)
class RiskLevels:
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    risk_pct: float
    atr: Optional[float]
    source: str  # "structure" | "atr"
    expires_at: Optional[datetime] = None


def risk_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = dict(DEFAULT_RISK_PARAMS)
    for key in DEFAULT_RISK_PARAMS:
        if overrides and key in overrides and overrides[key] is not None:
            params[key] = overrides[key]
    return params


def build_levels(
    signal_type: SignalType,
    entry: Optional[float],
    atr_value: Optional[float],
    params: Optional[Dict[str, Any]] = None,
    structural_stop: Optional[float] = None,
    take_profit: Optional[float] = None,
    last_timestamp: Optional[datetime] = None,
    timeframe: str = "",
) -> Optional[RiskLevels]:
    """Return validated levels, or ``None`` when the geometry is unusable."""
    if not entry or entry <= 0:
        return None
    config = risk_params(params)
    is_long = signal_type is SignalType.LONG
    direction = 1.0 if is_long else -1.0

    source = "structure"
    stop = structural_stop
    if stop is None:
        if not atr_value or atr_value <= 0:
            return None
        source = "atr"
        distance = float(atr_value) * float(config["atr_stop_multiplier"])
        stop = entry - direction * distance

    # a structural stop must sit on the correct side of the entry
    if is_long and stop >= entry:
        return None
    if not is_long and stop <= entry:
        return None

    risk_distance = abs(entry - float(stop))
    if risk_distance <= 0:
        return None
    risk_pct = risk_distance / entry * 100.0
    if risk_pct < float(config["min_risk_pct"]) or risk_pct > float(config["max_risk_pct"]):
        return None

    target = take_profit
    if target is None:
        target = entry + direction * risk_distance * float(config["reward_ratio"])
    if is_long and target <= entry:
        return None
    if not is_long and target >= entry:
        return None

    reward_distance = abs(float(target) - entry)
    risk_reward = round(reward_distance / risk_distance, 2)

    expires_at = None
    if last_timestamp is not None and timeframe:
        try:
            seconds = timeframe_to_seconds(timeframe) * int(config["max_bars"])
            expires_at = last_timestamp + timedelta(seconds=seconds)
        except ValueError:
            expires_at = None

    return RiskLevels(
        entry=float(entry),
        stop_loss=round(float(stop), 8),
        take_profit=round(float(target), 8),
        risk_reward=risk_reward,
        risk_pct=round(risk_pct, 3),
        atr=round(float(atr_value), 8) if atr_value else None,
        source=source,
        expires_at=expires_at,
    )


def outcome_for_signal(
    signal_type: str,
    entry: float,
    stop_loss: Optional[float],
    take_profit: Optional[float],
    candles,
    expires_at: Optional[datetime] = None,
    conservative: bool = True,
) -> Dict[str, Any]:
    """Walk candles after the signal and report which level was hit first.

    When one candle touches both levels, ``conservative=True`` assumes the stop
    was hit (no free lunch on intrabar ordering).
    """
    status = "open"
    closed_at = None
    realized_r = None
    bars_held = 0
    is_long = signal_type == "long"
    risk_distance = abs(entry - stop_loss) if stop_loss is not None else 0.0
    reward_multiple = (
        abs(take_profit - entry) / risk_distance
        if take_profit is not None and risk_distance > 0
        else 1.0
    )

    for index, candle in enumerate(candles):
        bars_held = index + 1
        hit_stop = stop_loss is not None and (
            (is_long and candle.low <= stop_loss) or (not is_long and candle.high >= stop_loss)
        )
        hit_target = take_profit is not None and (
            (is_long and candle.high >= take_profit) or (not is_long and candle.low <= take_profit)
        )
        if hit_stop and hit_target:
            if conservative:
                status, closed_at, realized_r = "hit_sl", candle.timestamp, -1.0
            else:
                status, closed_at, realized_r = "hit_tp", candle.timestamp, round(reward_multiple, 2)
            break
        if hit_stop:
            status, closed_at, realized_r = "hit_sl", candle.timestamp, -1.0
            break
        if hit_target:
            status, closed_at, realized_r = "hit_tp", candle.timestamp, round(reward_multiple, 2)
            break

    if status == "open" and expires_at is not None and candles:
        last = candles[-1].timestamp
        if last >= expires_at:
            status, closed_at, realized_r = "expired", expires_at, 0.0

    return {
        "status": status,
        "closed_at": closed_at.isoformat() if closed_at else None,
        "realized_r": realized_r,
        "bars_held": bars_held,
    }
