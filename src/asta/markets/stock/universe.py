"""Stock ticker universe helpers."""

from __future__ import annotations

from typing import Iterable, List

DEFAULT_SYMBOLS: List[str] = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META"]


def normalize(symbol: str) -> str:
    """``$aapl`` -> ``AAPL``; keeps class suffixes (``BRK-B``)."""
    return str(symbol).strip().upper().lstrip("$")


def symbols(configured: Iterable[str] = None) -> List[str]:
    values = [normalize(item) for item in (configured or []) if str(item).strip()]
    return values or list(DEFAULT_SYMBOLS)
