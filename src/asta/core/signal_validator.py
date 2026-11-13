"""Central validation gate: every candidate signal passes through here."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

from asta.core.signal_model import Signal
from asta.utils.time_utils import normalize_timeframe, utcnow


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


@dataclass
class ValidationResult:
    signal_id: str
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def reason(self) -> str:
        return "; ".join("{}: {}".format(issue.code, issue.message) for issue in self.issues)


class SignalValidator:
    """Cheap, deterministic sanity checks - not strategy logic."""

    def __init__(
        self,
        min_confidence: float = 0.35,
        max_age_seconds: int = 3600,
        max_future_skew_seconds: int = 120,
        min_reason_length: int = 10,
    ):
        self.min_confidence = float(min_confidence)
        self.max_age_seconds = int(max_age_seconds)
        self.max_future_skew_seconds = int(max_future_skew_seconds)
        self.min_reason_length = int(min_reason_length)

    def validate(self, signal: Signal, now=None) -> ValidationResult:
        now = now or utcnow()
        result = ValidationResult(signal_id=signal.signal_id)

        def issue(code: str, message: str) -> None:
            result.issues.append(ValidationIssue(code, message))

        if not signal.scanner_id:
            issue("missing_scanner", "scanner_id is required")
        if not signal.symbol or not signal.symbol.strip():
            issue("missing_symbol", "symbol is required")

        try:
            normalize_timeframe(signal.timeframe)
        except ValueError:
            issue("bad_timeframe", "unsupported timeframe {!r}".format(signal.timeframe))

        if not math.isfinite(signal.confidence):
            issue("bad_confidence", "confidence is not finite")
        elif signal.confidence < self.min_confidence:
            issue(
                "low_confidence",
                "{} < min {}".format(round(signal.confidence, 3), self.min_confidence),
            )
        elif signal.confidence > 1.0:
            issue("bad_confidence", "confidence {} > 1.0".format(signal.confidence))

        if len((signal.reason or "").strip()) < self.min_reason_length:
            issue("weak_reason", "reason is too short to be auditable")

        if signal.price is not None and (not math.isfinite(signal.price) or signal.price <= 0):
            issue("bad_price", "price must be a positive number")

        age = (now - signal.timestamp).total_seconds()
        if age > self.max_age_seconds:
            issue("stale_signal", "signal is {:.0f}s old (max {})".format(age, self.max_age_seconds))
        elif age < -self.max_future_skew_seconds:
            issue("future_signal", "signal timestamp is {:.0f}s in the future".format(-age))

        for name, value in (signal.indicators or {}).items():
            if not math.isfinite(value):
                issue("bad_indicator", "indicator {} is not finite".format(name))
                break

        return result
