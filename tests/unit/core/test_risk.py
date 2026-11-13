from datetime import datetime, timedelta, timezone

from asta.core.risk import build_levels, outcome_for_signal
from asta.core.signal_model import SignalType
from tests.fixtures.market_data import make_candles

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_atr_levels_for_long():
    levels = build_levels(SignalType.LONG, 100.0, atr_value=2.0, params={"reward_ratio": 2.0})
    assert levels is not None
    assert levels.stop_loss == 97.0  # 1.5 ATR
    assert levels.take_profit == 106.0  # 2R
    assert levels.risk_reward == 2.0
    assert levels.risk_pct == 3.0
    assert levels.source == "atr"


def test_atr_levels_for_short():
    levels = build_levels(SignalType.SHORT, 100.0, atr_value=2.0)
    assert levels.stop_loss == 103.0
    assert levels.take_profit == 94.0
    assert levels.risk_reward == 2.0


def test_structural_stop_is_used_when_valid():
    levels = build_levels(SignalType.LONG, 100.0, atr_value=2.0, structural_stop=98.5)
    assert levels.stop_loss == 98.5
    assert levels.source == "structure"
    assert levels.take_profit == 103.0


def test_wrong_side_structural_stop_is_rejected():
    assert build_levels(SignalType.LONG, 100.0, atr_value=2.0, structural_stop=101.0) is None


def test_risk_bounds_reject_absurd_stops():
    # 20% away is beyond max_risk_pct
    assert build_levels(SignalType.LONG, 100.0, atr_value=2.0, structural_stop=80.0) is None


def test_expiry_uses_timeframe_and_max_bars():
    levels = build_levels(
        SignalType.LONG, 100.0, 2.0, params={"max_bars": 10}, last_timestamp=NOW, timeframe="1h"
    )
    assert levels.expires_at == NOW + timedelta(hours=10)


def test_outcome_hits_target_first():
    candles = make_candles([100, 101, 107], timeframe="1h")
    result = outcome_for_signal("long", 100.0, 98.0, 106.0, candles)
    assert result["status"] == "hit_tp"
    assert result["realized_r"] == 3.0  # 6 points of reward / 2 points of risk
    assert result["bars_held"] == 3


def test_outcome_hits_stop_first():
    candles = make_candles([100, 99, 97], timeframe="1h")
    result = outcome_for_signal("long", 100.0, 98.0, 106.0, candles)
    assert result["status"] == "hit_sl"
    assert result["realized_r"] == -1.0


def test_outcome_conservative_when_both_touched_in_one_candle():
    candles = make_candles([100, 100])
    candles[-1] = candles[-1].model_copy(update={"high": 110.0, "low": 90.0})
    result = outcome_for_signal("long", 100.0, 98.0, 106.0, candles)
    assert result["status"] == "hit_sl"


def test_outcome_expires_without_touch():
    candles = make_candles([100, 100.5, 100.2], timeframe="1h")
    result = outcome_for_signal(
        "long", 100.0, 98.0, 106.0, candles, expires_at=candles[-1].timestamp
    )
    assert result["status"] == "expired"
    assert result["realized_r"] == 0.0


def test_outcome_short_mirror():
    candles = make_candles([100, 99, 93], timeframe="1h")
    result = outcome_for_signal("short", 100.0, 102.0, 94.0, candles)
    assert result["status"] == "hit_tp"


def test_realized_r_uses_the_reward_multiple():
    candles = make_candles([100, 105])
    result = outcome_for_signal("long", 100.0, 98.0, 104.0, candles)  # 2:1
    assert result["status"] == "hit_tp"
    assert result["realized_r"] == 2.0
