import asyncio

from asta.core.scanner_scheduler import ScannerScheduler


class FakeManager:
    def __init__(self, scanners):
        self._scanners = scanners

    def enabled(self, market=None):
        return [scanner for scanner in self._scanners if scanner.enabled]

    def all(self):
        return list(self._scanners)

    def __len__(self):
        return len(self._scanners)

    def run_cycle(self, scanner_ids=None, markets=None):
        self.ran = list(scanner_ids or [])
        from datetime import datetime, timezone

        from asta.core.scanner_manager import CycleReport

        return CycleReport(started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc))


class FakeScanner:
    def __init__(self, scanner_id, timeframe="1h", enabled=True):
        self.id = scanner_id
        self.timeframe = timeframe
        self.enabled = enabled


def test_due_scanners_respect_timeframe_interval():
    manager = FakeManager([FakeScanner("A", "1h"), FakeScanner("B", "15m")])
    scheduler = ScannerScheduler(manager, tick_seconds=60, respect_timeframe=True)
    assert set(scheduler.due_scanners(now=0.0)) == {"A", "B"}
    scheduler.mark_ran(["A", "B"], now=0.0)
    assert scheduler.due_scanners(now=120.0) == []  # both too early
    assert set(scheduler.due_scanners(now=460.0)) == {"B"}  # 15m -> 450s interval
    assert set(scheduler.due_scanners(now=1800.0)) == {"A", "B"}


def test_respect_timeframe_can_be_disabled():
    manager = FakeManager([FakeScanner("A", "1h")])
    scheduler = ScannerScheduler(manager, tick_seconds=60, respect_timeframe=False)
    scheduler.mark_ran(["A"], now=0.0)
    assert scheduler.due_scanners(now=61.0) == ["A"]


def test_disabled_scanner_is_never_due():
    manager = FakeManager([FakeScanner("A", "1h", enabled=False)])
    scheduler = ScannerScheduler(manager, tick_seconds=60)
    assert scheduler.due_scanners(now=0.0) == []


def test_run_once_executes_only_due_scanners():
    manager = FakeManager([FakeScanner("A", "1h"), FakeScanner("B", "4h")])
    scheduler = ScannerScheduler(manager, tick_seconds=60)
    asyncio.run(scheduler.run_once())
    assert set(manager.ran) == {"A", "B"}
    asyncio.run(scheduler.run_once())  # nothing due right after
    assert set(manager.ran) == {"A", "B"}
