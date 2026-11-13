from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from asta.core.signal_model import Candle, Market, ScanContext, Signal, SignalType
from asta.utils.exceptions import InsufficientDataError
from tests.helpers import make_candles


def test_candle_normalises_naive_timestamps():
    candle = Candle(timestamp=datetime(2025, 1, 1, 12, 0), open=1, high=2, low=0.5, close=1.5)
    assert candle.timestamp.tzinfo == timezone.utc
    assert candle.is_bullish is True
    assert candle.range == pytest.approx(1.5)


def test_scan_context_accessors_and_tail():
    context = ScanContext(
        market=Market.CRYPTO,
        symbol="btcusdt",
        timeframe="1h",
        candles=make_candles([1, 2, 3, 4, 5], volumes=[10, 20, 30, 40, 50]),
    )
    assert context.closes == [1, 2, 3, 4, 5]
    assert context.price == 5
    assert context.volumes[-1] == 50
    assert len(context.tail(2)) == 2
    assert context.last.close == 5


def test_scan_context_rejects_unsorted_candles():
    candles = make_candles([1, 2, 3])
    with pytest.raises(ValidationError):
        ScanContext(
            market=Market.CRYPTO,
            symbol="BTCUSDT",
            timeframe="1h",
            candles=[candles[2], candles[1], candles[0]],
        )


def test_scan_context_require_raises_insufficient_data():
    context = ScanContext(
        market=Market.FOREX, symbol="EUR_USD", timeframe="1h", candles=make_candles([1, 2, 3])
    )
    with pytest.raises(InsufficientDataError):
        context.require(10)


def test_signal_dedup_key_is_stable_and_direction_aware():
    base = dict(
        scanner_id="CXS001_RSI_DIVERGENCE",
        scanner_name="RSI Divergence",
        market=Market.CRYPTO,
        symbol="btcusdt",
        timeframe="1h",
        reason="divergence detected on the last pivot",
        confidence=0.7,
    )
    long_signal = Signal(signal_type=SignalType.LONG, **base)
    short_signal = Signal(signal_type=SignalType.SHORT, **base)
    assert long_signal.dedup_key == "crypto:CXS001_RSI_DIVERGENCE:BTCUSDT:1h:long"
    assert long_signal.dedup_key != short_signal.dedup_key
    assert long_signal.signal_id != short_signal.signal_id
    assert long_signal.to_dict()["market"] == "crypto"


def test_signal_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        Signal(
            scanner_id="X",
            scanner_name="X",
            market=Market.STOCK,
            symbol="AAPL",
            timeframe="1d",
            signal_type=SignalType.LONG,
            reason="whatever reason",
            confidence=1.4,
        )


def test_signal_age_seconds_is_positive():
    signal = Signal(
        scanner_id="X",
        scanner_name="X",
        market=Market.STOCK,
        symbol="AAPL",
        timeframe="1d",
        signal_type=SignalType.LONG,
        reason="whatever reason",
        confidence=0.5,
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    assert 290 < signal.age_seconds < 320
