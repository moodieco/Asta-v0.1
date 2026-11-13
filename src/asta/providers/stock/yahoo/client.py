"""Yahoo Finance chart REST client."""

from __future__ import annotations

from typing import Any, Dict, Optional

from asta.providers.base import BaseHttpClient

DEFAULT_BASE_URL = "https://query1.finance.yahoo.com"

INTERVALS: Dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "1d": "1d",
    "1w": "1wk",
}

#: Yahoo caps history per interval; keep requests inside those windows.
RANGES: Dict[str, str] = {
    "1m": "7d",
    "5m": "1mo",
    "15m": "1mo",
    "30m": "1mo",
    "1h": "3mo",
    "1d": "2y",
    "1w": "5y",
}


class YahooClient(BaseHttpClient):
    def __init__(self, settings: Optional[Dict[str, Any]] = None, client=None):
        settings = dict(settings or {})
        super().__init__(
            base_url=str(settings.get("base_url") or DEFAULT_BASE_URL),
            timeout=float(settings.get("timeout_seconds", 20)),
            max_attempts=int(settings.get("max_attempts", 3)),
            backoff_seconds=float(settings.get("backoff_seconds", 0.5)),
            headers={"Accept": "application/json"},
            client=client,
        )

    def chart(self, ticker: str, interval: str, price_range: str) -> Dict[str, Any]:
        payload = self.request_json(
            "/v8/finance/chart/{}".format(ticker),
            params={
                "interval": interval,
                "range": price_range,
                "includePrePost": "false",
                "events": "div,split",
            },
        )
        if not isinstance(payload, dict):
            raise ValueError("unexpected chart payload")
        return payload
