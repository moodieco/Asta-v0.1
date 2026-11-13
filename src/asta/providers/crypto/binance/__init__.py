"""Binance spot market data (REST candles, optional websocket stream)."""

from asta.providers.crypto.binance.candles import BinanceProvider
from asta.providers.crypto.binance.client import INTERVALS, BinanceClient
from asta.providers.crypto.binance.websocket import KlineEvent, parse_kline_message, stream_klines

__all__ = [
    "INTERVALS",
    "BinanceClient",
    "BinanceProvider",
    "KlineEvent",
    "parse_kline_message",
    "stream_klines",
]
