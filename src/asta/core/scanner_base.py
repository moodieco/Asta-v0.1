"""Scanner contract shared by every market.

A scanner:
  * owns an id, a name, a market, a timeframe and tunable params,
  * receives a :class:`ScanContext` (candles already fetched),
  * returns zero or more :class:`Signal` objects.

Scanners never touch Discord, storage or the network.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from asta.core.signal_model import Market, ScanContext, Signal, SignalType
from asta.utils.exceptions import ConfigurationError, ScannerError
from asta.utils.logger import get_logger
from asta.utils.time_utils import normalize_timeframe, utcnow


class ScannerConfig(BaseModel):
    """Static scanner configuration, loaded from ``config.yaml``."""

    id: str
    name: str
    market: Market
    timeframe: str = "1h"
    enabled: bool = True
    symbols: List[str] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    source_path: Optional[str] = None

    @field_validator("timeframe")
    @classmethod
    def _valid_timeframe(cls, value: str) -> str:
        return normalize_timeframe(value)

    @field_validator("symbols")
    @classmethod
    def _upper(cls, value: List[str]) -> List[str]:
        return [str(symbol).strip().upper() for symbol in value if str(symbol).strip()]

    def with_overrides(self, overrides: Dict[str, Any]) -> "ScannerConfig":
        """Return a copy with per-field overrides (symbols merge is replace)."""
        if not overrides:
            return self
        data = self.model_dump()
        params = dict(data.get("params") or {})
        params.update(overrides.get("params") or {})
        data.update({key: value for key, value in overrides.items() if key != "params"})
        data["params"] = params
        return ScannerConfig(**data)


class ScannerBase(ABC):
    """Base class for all scanners."""

    #: Unique id, e.g. ``FXS001_RSI_DIVERGENCE``.
    id: str = ""
    #: Human readable name, e.g. ``RSI Divergence``.
    name: str = ""
    #: Market this scanner belongs to.
    market: Market
    #: Timeframe applied when the config does not override it.
    default_timeframe: str = "1h"
    #: Default tunables, merged with ``ScannerConfig.params``.
    default_params: Dict[str, Any] = {}
    #: Strategy label used in notifications.
    strategy: str = ""
    #: Minimum candles required before evaluating.
    min_candles: int = 50

    def __init__(self, config: Optional[ScannerConfig] = None):
        if config is None:
            if not self.id or self.market is None:  # type: ignore[truthy-function]
                raise ConfigurationError("scanner {} needs an id and a market".format(type(self).__name__))
            config = ScannerConfig(
                id=self.id,
                name=self.name or self.id,
                market=self.market,
                timeframe=self.default_timeframe,
                params=dict(self.default_params),
            )
        if config.market != self.market:
            raise ConfigurationError(
                "scanner {} is registered as {} but configured as {}".format(
                    config.id, self.market.value, config.market.value
                )
            )
        self.config = config
        self.params: Dict[str, Any] = {**self.default_params, **dict(config.params)}
        self.logger = get_logger("asta.scanner.{}".format(config.id))

    # -- properties -------------------------------------------------------
    @property
    def timeframe(self) -> str:
        return self.config.timeframe

    @property
    def symbols(self) -> List[str]:
        return list(self.config.symbols)

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled)

    def param(self, key: str, default: Any = None) -> Any:
        return self.params.get(key, default)

    def describe(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "market": self.market.value,
            "strategy": self.strategy,
            "timeframe": self.timeframe,
            "enabled": self.enabled,
            "symbols": self.symbols,
            "params": dict(self.params),
        }

    # -- evaluation -------------------------------------------------------
    @abstractmethod
    def evaluate(self, context: ScanContext) -> List[Signal]:
        """Return candidate signals for one symbol. May return ``[]``."""

    def scan(self, context: ScanContext) -> List[Signal]:
        """Validate the context, run :meth:`evaluate`, normalise failures."""
        if context.market != self.market:
            raise ScannerError(
                "market mismatch: scanner {} got {} context".format(
                    self.id, context.market.value
                ),
                scanner_id=self.id,
            )
        context = context.model_copy(update={"scanner_id": self.id})
        context.require(self.min_candles)
        try:
            signals = list(self.evaluate(context))
        except ScannerError:
            raise
        except Exception as exc:  # noqa: BLE001 - wrap unknown scanner bugs
            raise ScannerError(
                "scanner failed on {}: {}".format(context.symbol, exc),
                scanner_id=self.id,
                symbol=context.symbol,
            ) from exc
        for signal in signals:
            if signal.scanner_id != self.id:
                raise ScannerError(
                    "scanner {} produced a signal for scanner {}".format(self.id, signal.scanner_id)
                )
        return signals

    # -- helpers ----------------------------------------------------------
    def signals_from(self, context: ScanContext, results: List[Any]) -> List[Signal]:
        """Convert strategy results into signals owned by this scanner."""
        signals: List[Signal] = []
        for result in results:
            signals.append(
                self.build_signal(
                    context,
                    signal_type=result.signal_type,
                    reason=result.reason,
                    confidence=result.confidence,
                    indicators=result.indicators,
                    metadata=result.metadata,
                    price=result.price,
                )
            )
        return signals

    def build_signal(
        self,
        context: ScanContext,
        signal_type: SignalType,
        reason: str,
        confidence: float,
        indicators: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        price: Optional[float] = None,
    ) -> Signal:
        return Signal(
            scanner_id=self.id,
            scanner_name=self.name or self.id,
            market=self.market,
            symbol=context.symbol.upper(),
            timeframe=context.timeframe,
            signal_type=signal_type,
            reason=reason,
            confidence=round(min(max(confidence, 0.0), 1.0), 3),
            price=price if price is not None else context.price,
            timestamp=context.now or utcnow(),
            strategy=self.strategy or self.name,
            indicators={k: float(v) for k, v in (indicators or {}).items()},
            metadata=dict(metadata or {}),
        )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return "<{} {} [{}] {}>".format(
            type(self).__name__, self.id, self.market.value, self.timeframe
        )
