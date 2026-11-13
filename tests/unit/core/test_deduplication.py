from datetime import datetime, timezone

from asta.core.deduplication import DeduplicationStore
from asta.core.signal_model import Market, Signal, SignalType
from asta.storage.cache import TTLCache


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_signal(signal_type=SignalType.LONG, symbol="BTCUSDT", timeframe="1h"):
    return Signal(
        scanner_id="CXS001_RSI_DIVERGENCE",
        scanner_name="RSI Divergence",
        market=Market.CRYPTO,
        symbol=symbol,
        timeframe=timeframe,
        signal_type=signal_type,
        reason="divergence between price pivots and RSI",
        confidence=0.7,
        timestamp=datetime.now(timezone.utc),
    )


def test_first_signal_is_new_second_is_duplicate():
    store = DeduplicationStore(window_seconds=3600, cache=TTLCache(3600, clock=FakeClock()))
    signal = make_signal()
    assert store.is_duplicate(signal) is False
    is_new, remaining = store.check_and_register(signal)
    assert is_new is True and remaining is None
    is_new, remaining = store.check_and_register(signal)
    assert is_new is False and remaining > 0
    assert store.size() == 1


def test_different_direction_is_not_a_duplicate():
    store = DeduplicationStore(window_seconds=3600, cache=TTLCache(3600, clock=FakeClock()))
    store.check_and_register(make_signal(SignalType.LONG))
    assert store.check_and_register(make_signal(SignalType.SHORT))[0] is True


def test_window_expires():
    clock = FakeClock()
    store = DeduplicationStore(window_seconds=3600, cache=TTLCache(3600, clock=clock))
    signal = make_signal()
    store.check_and_register(signal)
    clock.now += 3599
    assert store.is_duplicate(signal) is True
    clock.now += 2
    assert store.is_duplicate(signal) is False


def test_window_scales_with_timeframe_and_is_capped():
    store = DeduplicationStore(window_seconds=3600)
    assert store.window_for("1m") == 120.0
    assert store.window_for("15m") == 1800.0
    assert store.window_for("4h") == 3600.0  # capped by max window


def test_release_allows_retry():
    store = DeduplicationStore(3600, TTLCache(3600, clock=FakeClock()))
    signal = make_signal()
    store.check_and_register(signal)
    store.release(signal)
    assert store.check_and_register(signal)[0] is True
