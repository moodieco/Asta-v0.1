from datetime import datetime, timedelta, timezone

from asta.core.signal_model import Market, Signal, SignalType
from asta.core.signal_validator import SignalValidator


def make_signal(**overrides):
    data = dict(
        scanner_id="FXS001_RSI_DIVERGENCE",
        scanner_name="RSI Divergence",
        market=Market.FOREX,
        symbol="EUR_USD",
        timeframe="1h",
        signal_type=SignalType.LONG,
        reason="bullish RSI divergence on the second pivot",
        confidence=0.7,
        price=1.0923,
        timestamp=datetime.now(timezone.utc),
        indicators={"rsi": 38.2},
    )
    data.update(overrides)
    return Signal(**data)


def test_valid_signal_passes():
    result = SignalValidator().validate(make_signal())
    assert result.valid is True
    assert result.reason == ""


def test_low_confidence_is_rejected():
    result = SignalValidator(min_confidence=0.6).validate(make_signal(confidence=0.4))
    assert result.valid is False
    assert "low_confidence" in result.reason


def test_stale_signal_is_rejected():
    stale = make_signal(timestamp=datetime.now(timezone.utc) - timedelta(hours=5))
    result = SignalValidator(max_age_seconds=3600).validate(stale)
    assert result.valid is False
    assert "stale_signal" in result.reason


def test_future_signal_is_rejected():
    future = make_signal(timestamp=datetime.now(timezone.utc) + timedelta(minutes=10))
    result = SignalValidator(max_future_skew_seconds=60).validate(future)
    assert result.valid is False
    assert "future_signal" in result.reason


def test_non_positive_price_is_rejected():
    result = SignalValidator().validate(make_signal(price=0.0))
    assert result.valid is False
    assert "bad_price" in result.reason


def test_short_reason_is_rejected():
    result = SignalValidator(min_reason_length=20).validate(make_signal(reason="too short"))
    assert result.valid is False
    assert "weak_reason" in result.reason


def test_naive_timestamp_gets_utc():
    signal = make_signal(timestamp=datetime.now(timezone.utc).replace(tzinfo=None))
    assert signal.timestamp.tzinfo is not None
    assert SignalValidator().validate(signal).valid is True
