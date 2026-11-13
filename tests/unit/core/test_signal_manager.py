from datetime import datetime, timezone

from asta.core.deduplication import DeduplicationStore
from asta.core.signal_manager import SignalManager
from asta.core.signal_model import Market, Signal, SignalType
from asta.core.signal_validator import SignalValidator
from asta.integrations.discord.client import DeliveryResult
from asta.storage.cache import TTLCache
from asta.storage.signal_history import SignalHistory


class FakeNotifier:
    def __init__(self, ok=True, error=None):
        self.ok = ok
        self.error = error
        self.dispatched = []

    def dispatch(self, signal):
        self.dispatched.append(signal)
        return DeliveryResult(ok=self.ok, error=self.error, status_code=204 if self.ok else 500)


def make_signal(confidence=0.7, symbol="BTCUSDT", reason="volume spike on the last candle"):
    return Signal(
        scanner_id="CXS002_VOLUME_SPIKE",
        scanner_name="Volume Spike",
        market=Market.CRYPTO,
        symbol=symbol,
        timeframe="15m",
        signal_type=SignalType.LONG,
        reason=reason,
        confidence=confidence,
        price=42000.0,
        timestamp=datetime.now(timezone.utc),
    )


def build_manager(tmp_path, notifier=None, max_age=3600):
    return SignalManager(
        validator=SignalValidator(min_confidence=0.5, max_age_seconds=max_age),
        deduplication=DeduplicationStore(3600, TTLCache(3600)),
        history=SignalHistory(tmp_path / "signals.jsonl"),
        notifier=notifier,
    )


def test_accepted_signal_is_persisted_and_dispatched(tmp_path):
    alerts = FakeNotifier()
    manager = build_manager(tmp_path, alerts)
    outcome = manager.process([make_signal()])

    assert len(outcome.accepted) == 1
    assert outcome.delivered == 1
    assert outcome.rejected == []
    assert len(alerts.dispatched) == 1
    assert (tmp_path / "signals.jsonl").exists()
    assert SignalHistory(tmp_path / "signals.jsonl").count() == 1


def test_duplicate_signal_is_rejected_and_not_dispatched(tmp_path):
    alerts = FakeNotifier()
    manager = build_manager(tmp_path, alerts)
    signal = make_signal()
    manager.process([signal])
    outcome = manager.process([signal])

    assert outcome.accepted == []
    assert "duplicate" in outcome.rejected[0][1]
    assert len(alerts.dispatched) == 1


def test_invalid_signal_is_rejected(tmp_path):
    manager = build_manager(tmp_path, FakeNotifier())
    outcome = manager.process([make_signal(confidence=0.2)])
    assert outcome.accepted == []
    assert "low_confidence" in outcome.rejected[0][1]


def test_delivery_failure_is_reported_but_signal_kept(tmp_path):
    manager = build_manager(tmp_path, FakeNotifier(ok=False, error="HTTP 500"))
    outcome = manager.process([make_signal()])
    assert len(outcome.accepted) == 1
    assert outcome.delivered == 0
    assert outcome.delivery_errors
    assert manager.stats()["accepted_total"] == 1
