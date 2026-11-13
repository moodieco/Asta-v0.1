from asta.core.signal_model import Market, SignalType
from tests.fixtures.market_data import (
    make_context,
    stock_breakout_closes,
    stock_ema_trend_closes,
)


def test_sts001_detects_trend_aligned_ema_cross(scanners):
    scanner = scanners["STS001_EMA_TREND"]
    context = make_context(Market.STOCK, stock_ema_trend_closes(), symbol="AAPL", timeframe="1d")

    signals = scanner.scan(context)
    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type is SignalType.LONG
    assert signal.timeframe == "1d"
    assert signal.metadata["trend_aligned"] is True
    assert signal.indicators["trend_distance_pct"] > 0


def test_sts001_rejects_cross_against_the_long_trend(scanners):
    scanner = scanners["STS001_EMA_TREND"]
    # Sharp V bottom: the fast EMA crosses up while price is still far below EMA200.
    closes = [200.0] * 220 + [190.0] * 10 + [196.0] * 12
    context = make_context(Market.STOCK, closes, symbol="MSFT", timeframe="1d")
    assert scanner.scan(context) == []


def test_sts002_detects_daily_breakout(scanners):
    scanner = scanners["STS002_BREAKOUT_TREND"]
    closes = stock_breakout_closes()
    volumes = [1000.0] * (len(closes) - 1) + [1800.0]
    context = make_context(Market.STOCK, closes, volumes=volumes, symbol="NVDA", timeframe="1d")

    signals = scanner.scan(context)
    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type is SignalType.LONG
    assert signal.indicators["volume_ratio"] == 1.8
    assert signal.timeframe == "1d"


def test_sts002_ignores_range_bound_price(scanners):
    scanner = scanners["STS002_BREAKOUT_TREND"]
    closes = [100 + (0.4 if index % 2 else -0.4) for index in range(120)]
    context = make_context(Market.STOCK, closes, symbol="AAPL", timeframe="1d")
    assert scanner.scan(context) == []
