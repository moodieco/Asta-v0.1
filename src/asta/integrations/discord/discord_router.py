"""Routes signals to the webhook of their market channel."""

from __future__ import annotations

from typing import List, Optional

from asta.core.signal_model import Signal
from asta.integrations.discord.channel_config import ChannelConfig
from asta.integrations.discord.client import DeliveryResult, DiscordWebhookClient
from asta.integrations.discord.embed_builder import build_payload
from asta.utils.logger import get_logger


class DiscordRouter:
    def __init__(
        self,
        channels: ChannelConfig,
        client: Optional[DiscordWebhookClient] = None,
        dry_run: bool = False,
    ):
        self.channels = channels
        self.client = client or DiscordWebhookClient()
        self.dry_run = bool(dry_run)
        self.logger = get_logger("asta.discord.router")

    def route(self, signal: Signal) -> DeliveryResult:
        webhook = self.channels.webhook_for(signal.market)
        payload = build_payload(signal)

        if self.dry_run:
            self.logger.info(
                "DRY RUN alert",
                extra={
                    "market": signal.market.value,
                    "title": payload["embeds"][0]["title"],
                    "webhook_configured": bool(webhook),
                },
            )
            return DeliveryResult(ok=True, dry_run=True)

        if not webhook:
            return DeliveryResult(
                ok=False,
                error="no webhook configured for {} (set {})".format(
                    signal.market.value, "DISCORD_WEBHOOK_" + signal.market.value.upper()
                ),
            )

        result = self.client.post(webhook, payload)
        self.logger.info(
            "alert delivered",
            extra={
                "market": signal.market.value,
                "symbol": signal.symbol,
                "status": result.status_code,
            },
        )
        return result

    def route_sample(self, signal: Signal) -> DeliveryResult:
        webhook = self.channels.webhook_for(signal.market)
        payload = build_payload(signal, sample=True)
        if self.dry_run:
            return DeliveryResult(ok=True, dry_run=True)
        if not webhook:
            return DeliveryResult(ok=False, error="no webhook configured for {}".format(signal.market.value))
        return self.client.post(webhook, payload)

    def route_many(self, signals: List[Signal]) -> List[DeliveryResult]:
        return [self.route(signal) for signal in signals]

    def configured_markets(self) -> List[str]:
        return [market.value for market in self.channels.configured_markets()]
