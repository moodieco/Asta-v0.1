from asta.integrations.sheets.csv_writer import CsvSheetWriter
from asta.integrations.sheets.sync import SheetSyncService


class FakeHistory:
    def __init__(self, records):
        self.records = records
        self.calls = []

    def recorded_after(self, recorded_at, limit=200):
        self.calls.append((recorded_at, limit))
        if not recorded_at:
            return self.records[:limit]
        return [r for r in self.records if r["recorded_at"] > recorded_at][:limit]


def record(index, recorded_at):
    return {
        "recorded_at": recorded_at,
        "timestamp": "2026-11-13T20:00:{:02d}Z".format(index),
        "market": "crypto",
        "scanner_id": "CXS002_VOLUME_SPIKE",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "signal_type": "long",
        "confidence": 0.8,
        "price": 42000 + index,
        "strategy": "Volume Spike",
        "reason": "volume spike 5x",
        "indicators": {"volume_ratio": 5.0},
        "signal_id": "sig{}".format(index),
    }


def test_sync_appends_only_new_rows_and_persists_cursor(tmp_path):
    records = [record(1, "2026-11-13T20:00:01Z"), record(2, "2026-11-13T20:00:02Z")]
    history = FakeHistory(records)
    writer = CsvSheetWriter(tmp_path / "export.csv")
    service = SheetSyncService(writer, history, tmp_path / "state.json")

    first = service.sync_once()
    assert first["appended"] == 2
    assert first["total_rows"] == 2

    second = service.sync_once()
    assert second["appended"] == 0

    # a new process reading the same cursor must not duplicate rows
    restarted = SheetSyncService(
        CsvSheetWriter(tmp_path / "export.csv"), history, tmp_path / "state.json"
    )
    assert restarted.sync_once()["appended"] == 0

    rows = writer.read_rows()
    assert len(rows) == 3  # header + 2 signals
    assert rows[1][3] == "CXS002_VOLUME_SPIKE"
    assert rows[1][11] == "volume_ratio=5.0"

    records.append(record(3, "2026-11-13T20:00:03Z"))
    third = restarted.sync_once()
    assert third["appended"] == 1
    assert third["total_rows"] == 3
