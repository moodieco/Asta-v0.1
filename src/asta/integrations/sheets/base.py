"""Row contract shared by every spreadsheet driver."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

HEADER: List[str] = [
    "recorded_at",
    "timestamp",
    "market",
    "scanner_id",
    "symbol",
    "timeframe",
    "signal_type",
    "confidence",
    "entry",
    "stop_loss",
    "take_profit",
    "risk_reward",
    "risk_pct",
    "atr",
    "levels_source",
    "expires_at",
    "status",
    "realized_r",
    "bars_held",
    "strategy",
    "reason",
    "indicators",
    "signal_id",
    "source",
]


def _number(value: Any) -> Any:
    if value is None or value == "":
        return ""
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _format_indicators(indicators: Any) -> str:
    if not indicators:
        return ""
    if isinstance(indicators, str):
        return indicators
    return ", ".join("{}={}".format(key, value) for key, value in indicators.items())


def signal_to_row(record: Dict[str, Any]) -> List[Any]:
    """Map a stored signal dict to one spreadsheet row (header order)."""
    price = record.get("price")
    confidence = record.get("confidence")
    return [
        record.get("recorded_at", ""),
        record.get("timestamp", ""),
        record.get("market", ""),
        record.get("scanner_id", ""),
        record.get("symbol", ""),
        record.get("timeframe", ""),
        record.get("signal_type", ""),
        round(float(confidence), 4) if confidence is not None else "",
        float(price) if price is not None else "",
        _number(record.get("stop_loss")),
        _number(record.get("take_profit")),
        _number(record.get("risk_reward")),
        _number(record.get("risk_pct")),
        _number(record.get("atr")),
        record.get("levels_source", ""),
        record.get("expires_at") or "",
        record.get("status", ""),
        _number(record.get("realized_r")),
        _number(record.get("bars_held")),
        record.get("strategy", ""),
        record.get("reason", ""),
        _format_indicators(record.get("indicators")),
        record.get("signal_id", ""),
        record.get("source", "live"),
    ]


class SheetWriter(ABC):
    """Minimal writer contract: prepare the target, then append rows."""

    name: str = ""

    @abstractmethod
    def ensure_ready(self) -> None:
        """Create the file/sheet and header row if missing."""

    @abstractmethod
    def append_rows(self, rows: List[List[Any]]) -> int:
        """Append rows, returning how many were written."""

    def replace_all(self, rows: List[List[Any]]) -> int:
        """Rewrite the whole target (header changes, outcome updates)."""
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - optional hooks
        return None
