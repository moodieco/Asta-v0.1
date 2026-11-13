from datetime import datetime, timedelta, timezone

from asta.core.signal_model import Market, Signal, SignalType
from asta.storage.database import Database
from asta.storage.repositories.signal_repository import SignalRepository
from asta.storage.signal_history import SqliteSignalHistory


def make_signal(minutes_ago=0, symbol="BTCUSDT"):
    return Signal(
        scanner_id="CXS002_VOLUME_SPIKE",
        scanner_name="Volume Spike",
        market=Market.CRYPTO,
        symbol=symbol,
        timeframe="15m",
        signal_type=SignalType.LONG,
        reason="volume spike 5.2x the 20-bar average",
        confidence=0.88,
        price=42000.0,
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        indicators={"volume_ratio": 5.2},
        metadata={"note": "test"},
    )


def test_save_is_idempotent_and_readable(tmp_path):
    repository = SignalRepository(Database(tmp_path / "asta.db"))
    signal = make_signal()

    assert repository.save(signal) is True
    assert repository.save(signal) is False  # same signal_id -> ignored
    assert repository.count() == 1

    row = repository.recent(1)[0]
    assert row["symbol"] == "BTCUSDT"
    assert row["indicators"]["volume_ratio"] == 5.2
    assert row["metadata"]["note"] == "test"


def test_filters_and_stats(tmp_path):
    repository = SignalRepository(Database(tmp_path / "asta.db"))
    repository.save(make_signal(minutes_ago=10))
    repository.save(make_signal(minutes_ago=5))
    repository.save(make_signal(symbol="ETHUSDT"))

    assert repository.count() == 3
    assert len(repository.by_market("crypto", 10)) == 3
    assert len(repository.by_scanner("CXS002_VOLUME_SPIKE", 2)) == 2
    assert repository.stats()["crypto:CXS002_VOLUME_SPIKE"] == 3


def test_last_timestamp(tmp_path):
    repository = SignalRepository(Database(tmp_path / "asta.db"))
    repository.save(make_signal(minutes_ago=10))
    assert repository.last_timestamp("CXS002_VOLUME_SPIKE", "BTCUSDT") is not None
    assert repository.last_timestamp("NOPE", "BTCUSDT") is None


def test_sqlite_history_adapter(tmp_path):
    repository = SignalRepository(Database(tmp_path / "asta.db"))
    history = SqliteSignalHistory(repository)

    assert history.append(make_signal()) is True
    assert history.count() == 1
    assert history.tail(1)[0]["symbol"] == "BTCUSDT"
    assert history.stats()["crypto:CXS002_VOLUME_SPIKE"] == 1
    assert history.path == tmp_path / "asta.db"
