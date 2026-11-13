"""OANDA pricing helpers (last mid price, spread)."""

from __future__ import annotations

from typing import Dict, Optional

from asta.providers.forex.oanda.client import OandaClient
from asta.utils.exceptions import ProviderError


class OandaPricing:
    def __init__(self, client: OandaClient):
        self.client = client

    def _mid(self, instrument: str) -> Dict[str, float]:
        price = self.client.pricing(instrument)[0]
        bids = (price.get("bids") or [{}])[0]
        asks = (price.get("asks") or [{}])[0]
        try:
            bid = float(bids["price"])
            ask = float(asks["price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("malformed pricing payload", instrument=instrument) from exc
        return {"bid": bid, "ask": ask, "mid": (bid + ask) / 2.0}

    def current_price(self, instrument: str) -> Optional[float]:
        return self._mid(instrument)["mid"]

    def spread(self, instrument: str) -> float:
        quote = self._mid(instrument)
        return round(quote["ask"] - quote["bid"], 6)
