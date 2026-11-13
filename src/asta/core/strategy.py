"""Strategy contract.

A strategy is the pure part of a scanner: it reads candles and returns
candidate results. The scanner adds identity (id, market, timeframe) and turns
results into :class:`Signal` objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from asta.core.signal_model import ScanContext, SignalType


@dataclass
class StrategyResult:
    signal_type: SignalType
    confidence: float
    reason: str
    indicators: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    price: Optional[float] = None
    #: Structural levels from the setup (pivot low, breakout level). When absent
    #: the scanner falls back to ATR-based levels.
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class Strategy(ABC):
    """Market-agnostic strategy base with dict-style params."""

    name: str = ""
    default_params: Dict[str, Any] = {}

    def __init__(self, **params: Any):
        merged: Dict[str, Any] = dict(self.default_params)
        merged.update({key: value for key, value in params.items() if value is not None})
        self.params = merged

    def param(self, key: str, default: Any = None) -> Any:
        return self.params.get(key, default)

    @property
    def min_candles(self) -> int:
        return int(self.param("min_candles", 60))

    @abstractmethod
    def evaluate(self, context: ScanContext) -> List[StrategyResult]:
        """Return zero or more candidate results for the given context."""
