from datetime import datetime, timezone

from asta.core.signal_model import Market, Signal, SignalType
from asta.integrations.discord.channel_config import ChannelConfig
from asta.integrations.discord.client import DeliveryResult, DiscordWebhookClient
from asta.integrations.discord.discord_router import DiscordRouter

WEBHOOK = "https://discord.com/api/webhooks/123/abc"


class FakeClient(DiscordWebhookClient):
    def __init__(self, result=None):
        super().__init__(max_attempts=1)
        self.sent = []
        self._result = result or DeliveryResult(ok=True, status_code=204)

    def post(self, webhook_url, payload):
        self.sent.append((webhook_url, payload))
        return self._result


def make_signal(market=Market.CRYPTO):
    return Signal(
        scanner_id="CXS002_VOLUME_SPIKE",
        scanner_name="Volume Spike",
        market=market,
        symbol="BTCUSDT",
        timeframe="15m",
        signal_type=SignalType.LONG,
        reason="Volume spike 5.2x the 20-bar average on a bullish candle.",
        confidence=0.8,
        price=42000.0,
        timestamp=datetime.now(timezone.utc),
    )


def test_routes_signal_to_market_webhook():
    client = FakeClient()
    router = DiscordRouter(ChannelConfig.from_dict({"crypto": WEBHOOK}), client=client)
    result = router.route(make_signal())
    assert result.ok is True
    assert client.sent and client.sent[0][0] == WEBHOOK
    assert client.sent[0][1]["embeds"][0]["title"].startswith("🟢 LONG")


def test_dry_run_never_posts():
    client = FakeClient()
    router = DiscordRouter(ChannelConfig.from_dict({"crypto": WEBHOOK}), client=client, dry_run=True)
    result = router.route(make_signal())
    assert result.ok is True and result.dry_run is True
    assert client.sent == []


def test_missing_webhook_returns_actionable_error():
    router = DiscordRouter(ChannelConfig.from_dict({"forex": WEBHOOK}), client=FakeClient())
    result = router.route(make_signal(Market.CRYPTO))
    assert result.ok is False
    assert "DISCORD_WEBHOOK_CRYPTO" in result.error


def test_channel_config_reads_env_and_masks_secrets():
    config = ChannelConfig.from_env(
        {"DISCORD_WEBHOOK_FOREX": WEBHOOK, "DISCORD_WEBHOOK_CRYPTO": "", "DISCORD_WEBHOOK_STOCK": "https://discord.com/api/webhooks/9/zzz"}
    )
    assert config.webhook_for(Market.FOREX) == WEBHOOK
    assert config.webhook_for(Market.CRYPTO) is None
    assert config.configured_markets() == [Market.FOREX, Market.STOCK]
    assert WEBHOOK not in config.masked()["forex"]
    assert config.masked()["forex"].endswith("/abc")
