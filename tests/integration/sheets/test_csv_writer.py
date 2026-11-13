from asta.integrations.sheets.base import HEADER
from asta.integrations.sheets.csv_writer import CsvSheetWriter


def test_header_written_once_and_rows_appended(tmp_path):
    path = tmp_path / "signals.csv"
    writer = CsvSheetWriter(path)

    assert writer.append_rows([["a", 0.5, 1.0]]) == 1
    assert writer.append_rows([["b", 0.6, 2.0]]) == 1

    rows = writer.read_rows()
    assert rows[0] == HEADER
    assert len(rows) == 3
    assert rows[1][0] == "a"
    assert rows[2][0] == "b"


def test_existing_file_is_not_reheaderised(tmp_path):
    path = tmp_path / "signals.csv"
    path.write_text("custom,header\n1,2\n", encoding="utf-8")
    writer = CsvSheetWriter(path)
    writer.append_rows([["x"]])
    rows = writer.read_rows()
    assert rows[0] == ["custom", "header"]
    assert len(rows) == 3


def test_ensure_ready_is_idempotent(tmp_path):
    path = tmp_path / "signals.csv"
    writer = CsvSheetWriter(path)
    writer.ensure_ready()
    writer.ensure_ready()
    assert writer.read_rows() == [HEADER]
