from datetime import datetime, timezone

from asta.core.signal_model import Market, Signal, SignalType
from asta.integrations.discord.embed_builder import (
    LONG_COLOR,
    SHORT_COLOR,
    TEST_COLOR,
    build_payload,
    build_signal_embed,
    build_test_embed,
    build_test_payload,
    format_price,
)


def make_signal(signal_type=SignalType.LONG, market=Market.CRYPTO, price=42123.456):
    return Signal(
        scanner_id="CXS002_VOLUME_SPIKE",
        scanner_name="Volume Spike",
        market=market,
        symbol="BTCUSDT",
        timeframe="15m",
        signal_type=signal_type,
        reason="Volume spike 5.2x the 20-bar average on a bullish candle.",
        confidence=0.88,
        price=price,
        timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        strategy="Volume Spike",
        indicators={"volume_ratio": 5.2, "body_ratio": 0.98},
    )


def test_embed_contains_required_signal_fields():
    embed = build_signal_embed(make_signal())
    names = [field["name"] for field in embed["fields"]]
    assert embed["title"] == "🟢 LONG · BTCUSDT · 15M"
    assert embed["color"] == LONG_COLOR
    assert "Market" in names and "Scanner" in names and "Timeframe" not in names
    assert "Confidence" in names and "Price" in names
    market_field = next(field for field in embed["fields"] if field["name"] == "Market")
    assert "Crypto" in market_field["value"]
    assert embed["footer"]["text"].startswith("ASTA V0.1")
    assert embed["timestamp"].endswith("Z")


def test_short_signal_uses_red_and_price_formatting():
    embed = build_signal_embed(make_signal(signal_type=SignalType.SHORT, price=0.000123))
    assert embed["color"] == SHORT_COLOR
    price_field = next(field for field in embed["fields"] if field["name"] == "Price")
    assert price_field["value"] == "0.00012300"


def test_format_price_buckets():
    assert format_price(42123.456) == "42,123.46"
    assert format_price(1.23456) == "1.2346"
    assert format_price(0.123456) == "0.12346"
    assert format_price(0.00123456) == "0.00123456"


def test_payload_wraps_single_embed():
    payload = build_payload(make_signal())
    assert payload["username"] == "ASTA"
    assert len(payload["embeds"]) == 1
    assert payload["embeds"][0]["description"].startswith("Volume spike")


def test_reason_is_truncated_to_discord_limit():
    signal = make_signal()
    long_reason = "x" * 5000
    signal = signal.model_copy(update={"reason": long_reason})
    assert len(build_signal_embed(signal)["description"]) == 4096


def test_test_alert_is_clearly_labelled():
    embed = build_test_embed(Market.CRYPTO)
    assert embed["title"] == "🧪 ASTA TEST ALERT · Crypto"
    assert embed["color"] == TEST_COLOR
    assert "No trading signal" in embed["description"]
    assert embed["fields"][1]["value"] == "#crypto-signals"
    payload = build_test_payload(Market.STOCK)
    assert payload["embeds"][0]["title"].endswith("Stock")


def test_sample_signal_is_labelled_sample():
    embed = build_signal_embed(make_signal(), sample=True)
    assert embed["title"].startswith("🧪 SAMPLE · 🟢 LONG")
    assert embed["footer"]["text"].startswith("SAMPLE ALERT")
