"""Maps a market to its Discord webhook.

The env var name per market comes from ``config/discord.yaml`` so renaming a
channel never requires code changes; secrets stay in the environment.
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
    labels: Dict[str, str] = Field(default_factory=dict)
    env_keys: Dict[str, str] = Field(default_factory=lambda: dict(ENV_KEYS))

    @classmethod
    def from_env(
        cls,
        env: Optional[Dict[str, str]] = None,
        channels: Optional[Dict[str, object]] = None,
    ) -> "ChannelConfig":
        """Build from environment; ``channels`` may carry ``env``/``label`` per market."""
        env = dict(os.environ if env is None else env)
        env_keys = dict(ENV_KEYS)
        labels: Dict[str, str] = {}
        for market, settings in (channels or {}).items():
            env_keys[market] = getattr(settings, "env", None) or ENV_KEYS.get(
                market, "DISCORD_WEBHOOK_{}".format(str(market).upper())
            )
            label = getattr(settings, "label", "")
            if label:
                labels[market] = label
        webhooks = {
            market: env[key].strip()
            for market, key in env_keys.items()
            if env.get(key, "").strip() and market in {m.value for m in Market}
        }
        return cls(webhooks=webhooks, labels=labels, env_keys=env_keys)

    @classmethod
    def from_dict(cls, mapping: Dict[str, str]) -> "ChannelConfig":
        return cls(webhooks={k: v for k, v in mapping.items() if v})

    def webhook_for(self, market: Market) -> Optional[str]:
        return self.webhooks.get(market.value) or None

    def label_for(self, market: Market) -> str:
        return self.labels.get(market.value) or "#{}-signals".format(market.value)

    def has(self, market: Market) -> bool:
        return bool(self.webhook_for(market))

    def configured_markets(self) -> List[Market]:
        return [market for market in Market if self.has(market)]

    def masked(self) -> Dict[str, str]:
        masked: Dict[str, str] = {}
        for market, url in self.webhooks.items():
            masked[market] = "{}...{}".format(url[:8], url[-4:]) if len(url) > 12 else "***"
        return masked

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return "ChannelConfig({})".format(self.masked())
