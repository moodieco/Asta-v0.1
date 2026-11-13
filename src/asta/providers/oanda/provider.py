"""OANDA v20 candles provider (practice or live account)."""

from __future__ import annotations

from typing import Any, Dict, List

from asta.core.signal_model import Candle, Market
from asta.providers.base import MarketDataProvider
from asta.utils.exceptions import ProviderError
from asta.utils.time_utils import parse_datetime

GRANULARITY: Dict[str, str] = {
    "1m": "M1",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "4h": "H4",
    "1d": "D",
    "1w": "W",
}


class OandaProvider(MarketDataProvider):
    market = Market.FOREX
    name = "oanda"
    default_base_url = "https://api-fxpractice.oanda.com"
    health_symbol = "EUR_USD"

    def __init__(self, settings: Dict[str, Any] = None, client=None):
        super().__init__(settings, client=client)
        self.api_token = str(self.settings.get("api_token") or "").strip()
        self.account_id = str(self.settings.get("account_id") or "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_token and self.base_url)

    def normalize_symbol(self, symbol: str) -> str:
        raw = str(symbol).strip().upper().replace("/", "_").replace("-", "_")
        if "_" in raw:
            return raw
        if len(raw) == 6:
            return "{}_{}".format(raw[:3], raw[3:])
        if len(raw) == 7 and raw[3] in "_-":
            return raw[:3] + "_" + raw[4:]
        return raw

    def _headers(self) -> Dict[str, str]:
        if not self.api_token:
            raise ProviderError(
                "OANDA api token is not configured (set OANDA_API_TOKEN)", provider=self.name
            )
        return {"Authorization": "Bearer {}".format(self.api_token), "Accept-Datetime-Format": "RFC3339"}

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        tf = self.validate_timeframe(timeframe)
        granularity = GRANULARITY.get(tf)
        if granularity is None:
            raise ProviderError(
                "oanda does not support timeframe {!r}".format(timeframe), provider=self.name
            )
        instrument = self.normalize_symbol(symbol)
        payload = self._request_json(
            "{}/v3/instruments/{}/candles".format(self.base_url, instrument),
            params={
                "granularity": granularity,
                "count": max(2, min(int(limit), 5000)),
                "price": "M",
            },
            headers=self._headers(),
        )
        if not isinstance(payload, dict) or "candles" not in payload:
            raise ProviderError(
                "unexpected candles payload", provider=self.name, symbol=instrument
            )
        candles: List[Candle] = []
        for row in payload["candles"]:
            if not row.get("complete", True):
                continue
            mid = row.get("mid") or {}
            try:
                candles.append(
                    Candle(
                        timestamp=parse_datetime(row["time"]),
                        open=float(mid["o"]),
                        high=float(mid["h"]),
                        low=float(mid["l"]),
                        close=float(mid["c"]),
                        volume=float(row.get("volume", 0) or 0),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ProviderError(
                    "malformed candle row", provider=self.name, symbol=instrument, error=str(exc)
                ) from exc
        return candles
