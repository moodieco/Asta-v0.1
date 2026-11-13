"""Row model for the ``signals`` table."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Union

from asta.core.signal_model import Signal
from asta.utils.time_utils import isoformat, utcnow


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
        return cls(**{key: data.get(key) for key in cls.__dataclass_fields__})

    @property
    def timestamp(self) -> Optional[datetime]:
        from asta.utils.time_utils import parse_datetime

        return parse_datetime(self.created_at) if self.created_at else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "scanner_id": self.scanner_id,
            "scanner_name": self.scanner_name,
            "market": self.market,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "signal_type": self.signal_type,
            "confidence": self.confidence,
            "price": self.price,
            "reason": self.reason,
            "strategy": self.strategy,
            "indicators": dict(self.indicators),
            "metadata": dict(self.metadata),
            "timestamp": self.created_at,
            "recorded_at": self.recorded_at,
        }
