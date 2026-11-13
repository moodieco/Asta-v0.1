"""Crypto symbol universe helpers."""

from __future__ import annotations

from typing import Iterable, List, Optional

DEFAULT_SYMBOLS: List[str] = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
]

QUOTE_ASSETS = ("USDT", "USDC", "BUSD", "FDUSD", "BTC", "ETH", "BNB")


def normalize(symbol: str) -> str:
    """``btc/usdt`` -> ``BTCUSDT``."""
    raw = str(symbol).strip().upper()
    for separator in ("/", "-", "_", " "):
        raw = raw.replace(separator, "")
    return raw


def base_asset(symbol: str) -> str:
    ticker = normalize(symbol)
    for quote in QUOTE_ASSETS:
        if ticker.endswith(quote) and len(ticker) > len(quote):
            return ticker[: -len(quote)]
    return ticker


def quote_asset(symbol: str) -> Optional[str]:
    ticker = normalize(symbol)
    for quote in QUOTE_ASSETS:
        if ticker.endswith(quote) and len(ticker) > len(quote):
            return quote
    return None


def is_major(symbol: str) -> bool:
    return normalize(symbol) in DEFAULT_SYMBOLS


def symbols(configured: Optional[Iterable[str]] = None) -> List[str]:
    values = [normalize(item) for item in (configured or []) if str(item).strip()]
    return values or list(DEFAULT_SYMBOLS)
