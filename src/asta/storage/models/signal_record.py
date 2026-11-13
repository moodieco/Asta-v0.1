"""Row model for the ``signals`` table."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Union

from asta.core.signal_model import Signal
from asta.utils.time_utils import isoformat, parse_datetime, utcnow


@dataclass(frozen=True)
class SignalRecord:
    signal_id: str
    scanner_id: str
    scanner_name: str
    market: str
    symbol: str
    timeframe: str
    signal_type: str
    confidence: float
    reason: str
    price: Optional[float] = None
    strategy: str = ""
    indicators: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    recorded_at: str = ""
    # -- risk levels -------------------------------------------------------
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: Optional[float] = None
    risk_pct: Optional[float] = None
    atr: Optional[float] = None
    levels_source: str = ""
    expires_at: Optional[str] = None
    # -- outcome -----------------------------------------------------------
    status: str = "open"
    closed_at: Optional[str] = None
    realized_r: Optional[float] = None
    bars_held: Optional[int] = None
    source: str = "live"

    @classmethod
    def from_signal(cls, signal: Signal) -> "SignalRecord":
        return cls(
            signal_id=signal.signal_id,
            scanner_id=signal.scanner_id,
            scanner_name=signal.scanner_name,
            market=signal.market.value,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            signal_type=signal.signal_type.value,
            confidence=float(signal.confidence),
            reason=signal.reason,
            price=signal.price,
            strategy=signal.strategy or "",
            indicators=dict(signal.indicators),
            metadata=dict(signal.metadata),
            created_at=isoformat(signal.timestamp),
            recorded_at=isoformat(utcnow()),
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            risk_reward=signal.risk_reward,
            risk_pct=signal.risk_pct,
            atr=signal.atr,
            levels_source=signal.levels_source,
            expires_at=isoformat(signal.expires_at) if signal.expires_at else None,
            status=signal.status or "open",
            source=getattr(signal, "source", "live") or "live",
        )

    @classmethod
    def from_row(cls, row: Union[Dict[str, Any], Any]) -> "SignalRecord":
        data = dict(row)
        for key in ("indicators", "metadata"):
            raw = data.get(key)
            if isinstance(raw, str):
                try:
                    data[key] = json.loads(raw)
                except json.JSONDecodeError:
                    data[key] = {}
        known = {key: data.get(key) for key in cls.__dataclass_fields__ if key in data}
        return cls(**known)

    @staticmethod
    def column_names() -> list:
        return list(SignalRecord.__dataclass_fields__)

    def as_row(self) -> list:
        values = []
        for name in self.column_names():
            value = getattr(self, name)
            if name in ("indicators", "metadata"):
                value = json.dumps(value, default=str)
            values.append(value)
        return values

    @property
    def timestamp(self) -> Optional[datetime]:
        return parse_datetime(self.created_at) if self.created_at else None

    def to_dict(self) -> Dict[str, Any]:
        payload = {}
        for name in self.column_names():
            value = getattr(self, name)
            if name in ("indicators", "metadata"):
                value = dict(value)
            payload[name] = value
        payload["timestamp"] = self.created_at
        return payload
