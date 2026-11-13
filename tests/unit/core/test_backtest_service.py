
from asta.core.risk import outcome_for_signal
from asta.core.signal_model import Market, Signal, SignalType
from asta.core.signal_validator import SignalValidator
from asta.services.backtest_service import ReplayStats, backfill_scanner, replay_scanner
from asta.storage.database import Database
from asta.storage.repositories.signal_repository import SignalRepository
from tests.fixtures.market_data import make_candles


class AlwaysLongScanner:
    """Minimal scanner double: fires on every evaluated candle."""

    id = "CXS998_ALWAYS"
    name = "Always"
    market = Market.CRYPTO
    timeframe = "1h"
    min_candles = 10
    enabled = True
    strategy = "test"
    default_params = {"atr_period": 14, "reward_ratio": 2.0, "max_bars": 3}

    def scan(self, context):
        price = context.price
        return [
            Signal(
                scanner_id=self.id,
                scanner_name=self.name,
                market=self.market,
                symbol=context.symbol,
                timeframe=context.timeframe,
                signal_type=SignalType.LONG,
                reason="always fires in this test scanner",
                confidence=0.8,
                price=price,
                timestamp=context.now,
                stop_loss=price * 0.99,
                take_profit=price * 1.02,
                risk_reward=2.0,
                risk_pct=1.0,
                expires_at=context.now,
            )
        ]


def test_replay_dedupes_within_window():
    candles = make_candles([100 + index * 0.05 for index in range(40)], timeframe="1h")
    scanner = AlwaysLongScanner()
    signals = replay_scanner(scanner, "BTCUSDT", candles, SignalValidator(min_confidence=0.3))
    # 40 candles, 10-bar warmup, 2-candle (2h) cooldown -> about half the bars fire
    assert 10 <= len(signals) <= 20
    gaps = [
        (signals[i].timestamp - signals[i - 1].timestamp).total_seconds()
        for i in range(1, len(signals))
    ]
    assert all(gap >= 7200 for gap in gaps)
    assert all(signal.source == "backfill" for signal in signals)


def test_backfill_saves_and_scores_outcomes(tmp_path):
    repository = SignalRepository(Database(tmp_path / "asta.db"))
    # rising series: targets are hit, so most signals should close as hit_tp
    candles = make_candles([100 + index * 0.5 for index in range(40)], timeframe="1h")
    scanner = AlwaysLongScanner()

    stats = backfill_scanner(
        scanner,
        "BTCUSDT",
        candles,
        repository,
        SignalValidator(min_confidence=0.3),
        source="backfill",
    )

    assert isinstance(stats, ReplayStats)
    assert stats.saved == stats.raw > 0
    assert repository.count() == stats.saved
    rows = repository.recent(5)
    assert all(row["source"] == "backfill" for row in rows)
    assert all(row["stop_loss"] is not None for row in rows)
    assert any(row["status"] == "hit_tp" for row in repository.recent(50))
    assert repository.outcome_stats()


def test_backfill_is_idempotent(tmp_path):
    repository = SignalRepository(Database(tmp_path / "asta.db"))
    candles = make_candles([100 + index * 0.5 for index in range(30)], timeframe="1h")
    scanner = AlwaysLongScanner()
    validator = SignalValidator(min_confidence=0.3)

    first = backfill_scanner(scanner, "BTCUSDT", candles, repository, validator)
    second = backfill_scanner(scanner, "BTCUSDT", candles, repository, validator)

    assert first.saved > 0
    assert second.saved == 0
    assert second.rejected == first.saved


def test_outcome_reports_expiry():
    candles = make_candles([100.0] * 5, timeframe="1h")
    result = outcome_for_signal(
        "long", 100.0, 99.0, 102.0, candles, expires_at=candles[-1].timestamp
    )
    assert result["status"] == "expired"
    assert result["realized_r"] == 0.0
