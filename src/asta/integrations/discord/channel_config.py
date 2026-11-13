"""Maps a market to its Discord webhook.

V0.1 uses one webhook per channel (#forex-signals, #crypto-signals, #stock-signals)
configured through environment variables so no secret ever lands in git.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from asta.core.signal_model import Market

ENV_KEYS: Dict[str, str] = {
    "forex": "DISCORD_WEBHOOK_FOREX",
    "crypto": "DISCORD_WEBHOOK_CRYPTO",
    "stock": "DISCORD_WEBHOOK_STOCK",
}


class ChannelConfig(BaseModel):
    webhooks: Dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "ChannelConfig":
        env = dict(os.environ if env is None else env)
        webhooks = {
            market: env[key].strip()
            for market, key in ENV_KEYS.items()
            if env.get(key, "").strip()
        }
        return cls(webhooks=webhooks)

    @classmethod
    def from_dict(cls, mapping: Dict[str, str]) -> "ChannelConfig":
        return cls(webhooks={k: v for k, v in mapping.items() if v})

    def webhook_for(self, market: Market) -> Optional[str]:
        return self.webhooks.get(market.value) or None

    def has(self, market: Market) -> bool:
        return bool(self.webhook_for(market))

    def configured_markets(self) -> List[Market]:
        return [market for market in Market if self.has(market)]

    def masked(self) -> Dict[str, str]:
        masked: Dict[str, str] = {}
        for market, url in self.webhooks.items():
            if len(url) <= 12:
                masked[market] = "***"
            else:
                masked[market] = "{}...{}".format(url[:8], url[-4:])
        return masked

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return "ChannelConfig({})".format(self.masked())
