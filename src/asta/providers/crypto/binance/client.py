"""Binance REST client: public endpoints, no API key required."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from asta.providers.base import BaseHttpClient

INTERVALS: Dict[str, str] = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "12h": "12h",
    "1d": "1d",
    "1w": "1w",
}

DEFAULT_BASE_URL = "https://api.binance.com"
DEFAULT_STREAM_URL = "wss://stream.binance.com:9443"


class BinanceClient(BaseHttpClient):
    def __init__(self, settings: Optional[Dict[str, Any]] = None, client=None):
        settings = dict(settings or {})
        super().__init__(
            base_url=str(settings.get("base_url") or DEFAULT_BASE_URL),
            timeout=float(settings.get("timeout_seconds", 15)),
            max_attempts=int(settings.get("max_attempts", 3)),
            backoff_seconds=float(settings.get("backoff_seconds", 0.5)),
            client=client,
        )

    def klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 200,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[List[Any]]:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": max(1, min(int(limit), 1000)),
        }
        if start_time is not None:
            params["startTime"] = int(start_time)
        if end_time is not None:
            params["endTime"] = int(end_time)
        payload = self.request_json("/api/v3/klines", params=params)
        if not isinstance(payload, list) or not payload:
            raise ValueError("unexpected klines payload")
        return payload

    def ping(self) -> bool:
        try:
            self.request_json("/api/v3/ping")
            return True
        except Exception:  # noqa: BLE001 - health probe
            return False

    @staticmethod
    def stream_url(
        symbols: List[str], interval: str = "1m", base: str = DEFAULT_STREAM_URL
    ) -> str:
        streams = "/".join(
            "{}@kline_{}".format(symbol.strip().lower(), interval) for symbol in symbols
        )
        return "{}/stream?streams={}".format(base.rstrip("/"), streams)
