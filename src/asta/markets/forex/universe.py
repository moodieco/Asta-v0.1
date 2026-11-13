"""Forex pair universe helpers (OANDA instrument naming)."""

from __future__ import annotations

from typing import Iterable, List, Optional

DEFAULT_SYMBOLS: List[str] = [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
]

MAJORS = {"EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD"}


def normalize(symbol: str) -> str:
    """``EURUSD`` / ``eur/usd`` -> ``EUR_USD``."""
    raw = str(symbol).strip().upper().replace("/", "_").replace("-", "_")
    if "_" in raw:
        return raw
    if len(raw) == 6:
        return "{}_{}".format(raw[:3], raw[3:])
    return raw


def base_currency(symbol: str) -> str:
    return normalize(symbol).split("_")[0]


def quote_currency(symbol: str) -> str:
    parts = normalize(symbol).split("_")
    return parts[1] if len(parts) > 1 else ""


def is_major(symbol: str) -> bool:
    return normalize(symbol) in MAJORS


def is_jpy_pair(symbol: str) -> bool:
    return quote_currency(symbol) == "JPY"


def symbols(configured: Optional[Iterable[str]] = None) -> List[str]:
    values = [normalize(item) for item in (configured or []) if str(item).strip()]
    return values or list(DEFAULT_SYMBOLS)
