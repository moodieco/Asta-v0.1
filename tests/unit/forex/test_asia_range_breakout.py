"""Asia range breakout: session window in NY time, break trigger, time cutoff.

Candles are built in UTC. In November New York is UTC-5, so 19:00 NY is 00:00Z
and 00:00 NY is 05:00Z - the range window spans 00:00Z..05:00Z. Fixtures carry
plain history before the window so ATR(14) has something real to chew on.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from asta.core.scanner_base import ScannerConfig
from asta.core.signal_model import Candle, Market, ScanContext, SignalType
from asta.markets.forex.scanners.FXS003_ASIA_RANGE_BREAKOUT.scanner import (
    AsiaRangeBreakoutScanner,
)
from asta.markets.strategies.asia_range_breakout import (
    AsiaRangeBreakoutStrategy,
    parse_hhmm,
    session_window,
)
from asta.markets.strategies.forex_asia_range_breakout import ForexAsiaRangeBreakoutStrategy
from asta.utils.exceptions import ScannerError

UTC = timezone.utc
# session window: 2026-11-14 00:00Z (= 13 Nov 19:00 NY) -> 05:00Z (= 14 Nov 00:00 NY)
WINDOW_START = datetime(2026, 11, 14, 0, 0, tzinfo=UTC)
WINDOW_END = datetime(2026, 11, 14, 5, 0, tzinfo=UTC)
SCAN_AT = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)  # 10:00 NY, inside the trading window
HISTORY_BARS = 35


def candle(ts: datetime, o: float, h: float, lo: float, c: float) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=lo, close=c, volume=100.0)


def quiet(ts: datetime, price: float = 150.00, spread: float = 0.08) -> Candle:
    return candle(ts, price, price + spread, price - spread, price + 0.01)


def history(count: int = HISTORY_BARS, end: datetime = WINDOW_START) -> list:
    start = end - timedelta(hours=count)
    return [quiet(start + timedelta(hours=i)) for i in range(count)]


def session_range(high: float = 150.20, low: float = 149.90) -> list:
    return [
        candle(WINDOW_START, 150.00, 150.10, 149.95, 150.05),
        candle(WINDOW_START + timedelta(hours=1), 150.05, high, 150.00, 150.10),
        candle(WINDOW_START + timedelta(hours=2), 150.10, 150.12, 149.98, 150.02),
        candle(WINDOW_START + timedelta(hours=3), 150.02, 150.08, low, 150.00),
        candle(WINDOW_START + timedelta(hours=4), 150.00, 150.06, 149.96, 150.04),
    ]


def inside_bar() -> Candle:
    return candle(WINDOW_END, 150.04, 150.18, 150.01, 150.10)


def break_up() -> Candle:
    return candle(WINDOW_END + timedelta(hours=1), 150.10, 150.40, 150.08, 150.35)


def break_down() -> Candle:
    return candle(WINDOW_END + timedelta(hours=1), 150.10, 150.12, 149.70, 149.75)


def context(candles, now: datetime = SCAN_AT) -> ScanContext:
    return ScanContext(market=Market.FOREX, symbol="USD_JPY", timeframe="1h", candles=candles, now=now)


def strategy(**params) -> ForexAsiaRangeBreakoutStrategy:
    return ForexAsiaRangeBreakoutStrategy(**params)


# -- session maths --------------------------------------------------------
def test_session_window_crosses_midnight() -> None:
    start, end = session_window(
        datetime(2026, 11, 14, 10, 0), parse_hhmm("19:00"), parse_hhmm("00:00")
    )
    assert start.astimezone(UTC) == WINDOW_START
    assert end.astimezone(UTC) == WINDOW_END


def test_breakout_up_uses_range_levels() -> None:
    candles = history() + session_range() + [inside_bar(), break_up()]

    results = strategy().evaluate(context(candles))
    assert len(results) == 1
    result = results[0]
    assert result.signal_type is SignalType.LONG
    assert result.price == pytest.approx(150.20)      # entry = range high (stop order level)
    assert result.stop_loss == pytest.approx(149.90)  # stop = opposite edge
    assert result.indicators["range_high"] == pytest.approx(150.20)
    assert result.metadata["entry_style"] == "stop"
    assert "broken to the upside" in result.reason


def test_breakout_down_mirrors_levels() -> None:
    candles = history() + session_range() + [inside_bar(), break_down()]

    results = strategy().evaluate(context(candles))
    assert len(results) == 1
    assert results[0].signal_type is SignalType.SHORT
    assert results[0].price == pytest.approx(149.90)
    assert results[0].stop_loss == pytest.approx(150.20)


def test_no_signal_after_cutoff() -> None:
    """13:30 NY = 18:30Z: the trade gets closed, not opened."""
    candles = history() + session_range() + [inside_bar(), break_up()]
    late = datetime(2026, 11, 14, 18, 45, tzinfo=UTC)  # 13:45 NY
    assert strategy().evaluate(context(candles, now=late)) == []


def test_no_signal_when_range_is_too_tight() -> None:
    candles = history() + session_range(high=150.02, low=149.98) + [inside_bar(), break_up()]
    assert strategy().evaluate(context(candles)) == []


def test_break_is_signalled_once() -> None:
    third = candle(WINDOW_END + timedelta(hours=2), 150.35, 150.60, 150.30, 150.55)
    candles = history() + session_range() + [inside_bar(), break_up(), third]
    # the previous candle already closed above the high -> no repeat alert
    assert strategy().evaluate(context(candles)) == []


def test_no_signal_without_a_closed_range() -> None:
    """Candles that never cover the session window (feed gap) - stay quiet."""
    start = WINDOW_END + timedelta(hours=5)  # 10:00Z, well after the window
    candles = [quiet(start + timedelta(hours=i)) for i in range(HISTORY_BARS + 5)]
    assert strategy().evaluate(context(candles)) == []


def test_require_sweep_filters_first_break() -> None:
    plain = history() + session_range() + [inside_bar(), break_up()]
    assert strategy(require_sweep=True).evaluate(context(plain)) == []

    sweep = candle(WINDOW_END, 150.04, 150.10, 149.80, 150.06)  # raided below the low
    swept = history() + session_range() + [sweep, break_up()]
    results = strategy(require_sweep=True).evaluate(context(swept))
    assert len(results) == 1
    assert results[0].metadata["swept_opposite"] is True
    assert results[0].confidence > 0.55


# -- scanner contract -----------------------------------------------------
def test_scanner_emits_signal_with_stop_and_target() -> None:
    """The validator requires entry + SL + TP together; check the real wiring."""
    config = ScannerConfig(
        id="FXS003_ASIA_RANGE_BREAKOUT",
        name="Asia Range Breakout",
        market=Market.FOREX,
        timeframe="1h",
    )
    scanner = AsiaRangeBreakoutScanner(config)
    candles = history() + session_range() + [inside_bar(), break_up()]

    signals = scanner.scan(context(candles))
    assert len(signals) == 1
    signal = signals[0]
    assert signal.scanner_id == "FXS003_ASIA_RANGE_BREAKOUT"
    assert signal.strategy == "Asia Range Breakout"
    assert signal.stop_loss is not None and signal.take_profit is not None
    assert signal.price is not None
    assert signal.take_profit > signal.price > signal.stop_loss  # long geometry
    assert signal.risk_reward == pytest.approx(2.0, abs=0.05)
    assert signal.levels_source == "structure"
    assert signal.expires_at is not None


def test_scanner_rejects_foreign_market_context() -> None:
    config = ScannerConfig(
        id="FXS003_ASIA_RANGE_BREAKOUT",
        name="Asia Range Breakout",
        market=Market.FOREX,
        timeframe="1h",
    )
    scanner = AsiaRangeBreakoutScanner(config)
    crypto = ScanContext(
        market=Market.CRYPTO,
        symbol="BTCUSDT",
        timeframe="1h",
        candles=[quiet(WINDOW_START + timedelta(hours=i)) for i in range(40)],
    )
    with pytest.raises(ScannerError):
        scanner.scan(crypto)


def test_base_strategy_is_market_agnostic() -> None:
    """Nothing in the shared implementation assumes forex."""
    candles = history() + session_range() + [inside_bar(), break_up()]
    results = AsiaRangeBreakoutStrategy().evaluate(context(candles))
    assert len(results) == 1
    assert results[0].metadata["session_start"].startswith("2026-11-13T19:00")


def test_rebreak_of_the_same_range_is_not_a_new_setup() -> None:
    """OCO: once a side breaks, the opposite order is cancelled for the session."""
    back_inside = candle(WINDOW_END + timedelta(hours=2), 150.35, 150.40, 150.05, 150.10)
    rebreak = candle(WINDOW_END + timedelta(hours=3), 150.10, 150.50, 150.08, 150.45)
    candles = history() + session_range() + [inside_bar(), break_up(), back_inside, rebreak]
    assert strategy().evaluate(context(candles)) == []
