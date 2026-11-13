"""OANDA v20 REST client (practice or live account)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from asta.providers.base import BaseHttpClient
from asta.utils.exceptions import ProviderError

DEFAULT_BASE_URL = "https://api-fxpractice.oanda.com"


class OandaClient(BaseHttpClient):
    def __init__(self, settings: Optional[Dict[str, Any]] = None, client=None):
        settings = dict(settings or {})
        super().__init__(
            base_url=str(settings.get("base_url") or DEFAULT_BASE_URL),
            timeout=float(settings.get("timeout_seconds", 15)),
            max_attempts=int(settings.get("max_attempts", 3)),
            backoff_seconds=float(settings.get("backoff_seconds", 0.5)),
            client=client,
        )
        self.api_token = str(settings.get("api_token") or "").strip()
        self.account_id = str(settings.get("account_id") or "").strip()

    @property
    def auth_headers(self) -> Dict[str, str]:
        if not self.api_token:
            raise ProviderError(
                "OANDA api token is not configured (set OANDA_API_TOKEN)"
            )
        return {
            "Authorization": "Bearer {}".format(self.api_token),
            "Accept-Datetime-Format": "RFC3339",
        }

    def candles(self, instrument: str, granularity: str, count: int) -> List[Dict[str, Any]]:
        payload = self.request_json(
            "/v3/instruments/{}/candles".format(instrument),
            params={"granularity": granularity, "count": count, "price": "M"},
            headers=self.auth_headers,
        )
        if not isinstance(payload, dict) or "candles" not in payload:
            raise ProviderError("unexpected candles payload", instrument=instrument)
        return payload["candles"]

    def pricing(self, instrument: str) -> List[Dict[str, Any]]:
        payload = self.request_json(
            "/v3/accounts/{}/pricing".format(self.account_id or "default"),
            params={"instruments": instrument},
            headers=self.auth_headers,
        )
        prices = (payload or {}).get("prices") or []
        if not prices:
            raise ProviderError("no pricing returned", instrument=instrument)
        return prices
