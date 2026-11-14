from asta.core.signal_model import Market, SignalType
from tests.fixtures.market_data import (
    bullish_divergence_closes,
    ema_bullish_cross_closes,
    make_context,
    uptrend_closes,
)


def test_fxs001_detects_bullish_divergence(scanners):
    scanner = scanners["FXS001_RSI_DIVERGENCE"]
    context = make_context(Market.FOREX, bullish_divergence_closes(), symbol="EUR_USD")
    signals = scanner.scan(context)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type is SignalType.LONG
    assert signal.market is Market.FOREX
    assert signal.scanner_id == "FXS001_RSI_DIVERGENCE"
    assert signal.timeframe == "1h"
    assert signal.confidence >= 0.55
    assert "bullish RSI divergence" in signal.reason
    assert signal.indicators["rsi_delta"] > 0
    assert signal.price > 0


def test_fxs001_stays_quiet_without_divergence(scanners):
    scanner = scanners["FXS001_RSI_DIVERGENCE"]
    context = make_context(Market.FOREX, uptrend_closes(200, 1.05, 0.0004), symbol="EUR_USD")
    assert scanner.scan(context) == []


def test_fxs002_detects_ema_cross(scanners):
    scanner = scanners["FXS002_EMA_CROSSOVER"]
    context = make_context(Market.FOREX, ema_bullish_cross_closes(), symbol="GBP_USD")
    signals = scanner.scan(context)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type is SignalType.LONG
    assert signal.indicators["ema_fast"] > signal.indicators["ema_slow"]
    assert "EMA20 crossed above EMA50" in signal.reason
    assert 0.5 <= signal.confidence <= 0.95


def test_fxs002_stays_quiet_in_a_flat_market(scanners):
    scanner = scanners["FXS002_EMA_CROSSOVER"]
    context = make_context(Market.FOREX, [1.1000] * 260, symbol="EUR_USD")
    assert scanner.scan(context) == []


def test_forex_scanners_reject_crypto_context(scanners):
    import pytest

    from asta.utils.exceptions import ScannerError

    scanner = scanners["FXS001_RSI_DIVERGENCE"]
    context = make_context(Market.CRYPTO, bullish_divergence_closes(), symbol="BTCUSDT")
    with pytest.raises(ScannerError):
        scanner.scan(context)


def test_divergence_signals_have_sane_levels(scanners):
    scanner = scanners["FXS001_RSI_DIVERGENCE"]
    context = make_context(Market.FOREX, bullish_divergence_closes(), symbol="EUR_USD")
    for signal in scanner.scan(context):
        assert signal.stop_loss is not None
        assert signal.take_profit is not None
        if signal.signal_type is SignalType.LONG:
            assert signal.stop_loss < signal.price < signal.take_profit
        else:
            assert signal.take_profit < signal.price < signal.stop_loss
