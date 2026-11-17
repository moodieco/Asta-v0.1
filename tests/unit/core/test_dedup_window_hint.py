"""Per-signal dedup window (``metadata["dedup_window_seconds"]``).

A session screener must alert once per symbol per day; a 5m scanner would
otherwise re-alert every two candles because ``window_for`` follows the
timeframe.
"""

from asta.core.deduplication import DeduplicationStore, dedup_window_hint
from asta.core.signal_model import Market, Signal, SignalType

KEY_METADATA = {"dedup_window_seconds": 25_200}


def make_signal(metadata=None, timeframe="5m", symbol="BBCA.JK"):
    return Signal(
        scanner_id="STS003_IDX_LIQUIDITY",
        scanner_name="BPJS SCANNER",
        market=Market.STOCK,
        symbol=symbol,
        timeframe=timeframe,
        signal_type=SignalType.LONG,
        reason="liquid and up on the day",
        confidence=0.6,
        price=1010.0,
        metadata=dict(metadata or {}),
    )


def test_hint_is_none_without_metadata():
    assert dedup_window_hint(None) is None
    assert dedup_window_hint({}) is None
    assert dedup_window_hint("nope") is None


def test_hint_parses_and_rejects_junk():
    assert dedup_window_hint(KEY_METADATA) == 25_200
    assert dedup_window_hint({"dedup_window_seconds": "3600"}) == 3600
    assert dedup_window_hint({"dedup_window_seconds": "abc"}) is None
    assert dedup_window_hint({"dedup_window_seconds": 0}) is None
    assert dedup_window_hint({"dedup_window_seconds": None}) is None


def test_session_window_outlives_the_timeframe_window():
    store = DeduplicationStore(window_seconds=3600)
    signal = make_signal(KEY_METADATA)

    # a 5m bar would normally dedup for 10 minutes only
    assert store.window_for("5m") == 600.0

    assert store.check_and_register(signal)[0] is True
    remaining = store.cache.ttl(signal.dedup_key)
    assert remaining is not None and remaining > 3600

    again = make_signal(KEY_METADATA)
    is_new, still_blocked = store.check_and_register(again)
    assert is_new is False
    assert still_blocked is not None and still_blocked > 3600


def test_scanner_without_the_hint_keeps_the_timeframe_window():
    store = DeduplicationStore(window_seconds=3600)
    signal = make_signal()

    assert store.check_and_register(signal)[0] is True
    remaining = store.cache.ttl(signal.dedup_key)
    assert remaining is not None and remaining <= 600
