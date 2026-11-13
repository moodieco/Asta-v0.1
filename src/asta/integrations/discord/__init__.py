"""Discord webhook alerting: channel routing, embeds, delivery."""

from asta.integrations.discord.alert_manager import AlertManager
from asta.integrations.discord.channel_config import ChannelConfig
from asta.integrations.discord.client import DeliveryResult, DiscordWebhookClient
from asta.integrations.discord.discord_router import DiscordRouter
from asta.integrations.discord.embed_builder import build_payload, build_signal_embed

__all__ = [
    "AlertManager",
    "ChannelConfig",
    "DeliveryResult",
    "DiscordRouter",
    "DiscordWebhookClient",
    "build_payload",
    "build_signal_embed",
]
