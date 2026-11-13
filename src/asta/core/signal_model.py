"""ASTA data models: candles, scan context and the signal contract.

Every scanner produces :class:`Signal` objects and nothing else. Scanners never
talk to Discord, never write to storage - the signal pipeline does that.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from asta.utils.exceptions import InsufficientDataError
from asta.utils.time_utils import ensure_utc, utcnow


class Market(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"
    STOCK = "stock"

    @property
    def label(self) -> str:
        return {"forex": "Forex", "crypto": "Crypto", "stock": "Stock"}[self.value]


class SignalType(str, Enum):
    LONG = "long"
    SHORT = "short"

    @property
    def emoji(self) -> str:
        return "🟢" if self is SignalType.LONG else "🔴"

    @property
    def label(self) -> str:
        return self.value.upper()


class Candle(BaseModel):
    """A single OHLCV bar, always UTC and always closed."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @field_validator("timestamp")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return max(self.high - self.low, 0.0)

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3.0


class ScanContext(BaseModel):
    """Everything a scanner is allowed to look at for one symbol."""

    market: Market
    symbol: str
    timeframe: str
    candles: List[Candle] = Field(default_factory=list)
    scanner_id: str = ""
    now: datetime = Field(default_factory=utcnow)
    extra: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("now")
    @classmethod
    def _aware_now(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def _ordered(self) -> "ScanContext":
        if not self.candles:
            raise ValueError("ScanContext requires at least one candle")
        if any(
            self.candles[i].timestamp > self.candles[i + 1].timestamp
            for i in range(len(self.candles) - 1)
        ):
            raise ValueError("candles must be sorted oldest -> newest")
        return self

    # -- convenience accessors -------------------------------------------
    @property
    def closes(self) -> List[float]:
        return [c.close for c in self.candles]

    @property
    def opens(self) -> List[float]:
        return [c.open for c in self.candles]

    @property
    def highs(self) -> List[float]:
        return [c.high for c in self.candles]

    @property
    def lows(self) -> List[float]:
        return [c.low for c in self.candles]

    @property
    def volumes(self) -> List[float]:
        return [c.volume for c in self.candles]

    @property
    def last(self) -> Candle:
        return self.candles[-1]

    @property
    def price(self) -> float:
        return self.candles[-1].close

    @property
    def last_timestamp(self) -> datetime:
        return self.candles[-1].timestamp

    def tail(self, count: int) -> List[Candle]:
        return self.candles[-count:] if count > 0 else []

    def require(self, minimum: int) -> None:
        if len(self.candles) < minimum:
            raise InsufficientDataError(
                "needs {} candles, got {}".format(minimum, len(self.candles)),
                symbol=self.symbol,
                timeframe=self.timeframe,
            )


class Signal(BaseModel):
    """A trade candidate produced by one scanner for one symbol."""

    scanner_id: str
    scanner_name: str
    market: Market
    symbol: str
    timeframe: str
    signal_type: SignalType
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    price: Optional[float] = None
    timestamp: datetime = Field(default_factory=utcnow)
    strategy: str = ""
    indicators: Dict[str, float] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # -- risk levels (filled by the scanner, optional but recommended) -----
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: Optional[float] = None
    risk_pct: Optional[float] = None
    atr: Optional[float] = None
    levels_source: str = ""
    expires_at: Optional[datetime] = None
    status: str = "open"
    #: "live" for scheduler scans, "backfill" for historical replay
    source: str = "live"

    @field_validator("expires_at")
    @classmethod
    def _aware_expiry(cls, value):
        return ensure_utc(value) if value is not None else None

    @property
    def entry_price(self) -> Optional[float]:
        return self.price

    @field_validator("timestamp")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @property
    def dedup_key(self) -> str:
        return "{}:{}:{}:{}:{}".format(
            self.market.value,
            self.scanner_id,
            self.symbol.upper(),
            self.timeframe,
            self.signal_type.value,
        )

    @property
    def signal_id(self) -> str:
        raw = "{}:{}".format(self.dedup_key, self.timestamp.isoformat())
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    @property
    def age_seconds(self) -> float:
        return (utcnow() - self.timestamp).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    def summary(self) -> str:
        return "{} {} {} {} ({:.0%})".format(
            self.signal_type.label,
            self.market.value,
            self.symbol,
            self.timeframe,
            self.confidence,
        )
