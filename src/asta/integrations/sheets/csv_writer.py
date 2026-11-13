"""CSV writer: zero-auth spreadsheet export (Excel / Google Sheets import)."""

from __future__ import annotations

import csv
import threading
from pathlib import Path
from typing import Any, List, Union

from asta.integrations.sheets.base import HEADER, SheetWriter


class CsvSheetWriter(SheetWriter):
    name = "csv"

    def __init__(self, path: Union[str, Path], header: List[str] = None):
        self.path = Path(path).expanduser()
        self.header = list(header or HEADER)
        self._lock = threading.Lock()

    def ensure_ready(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if self.path.exists() and self.path.stat().st_size > 0:
                return
            with self.path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerow(self.header)

    def append_rows(self, rows: List[List[Any]]) -> int:
        if not rows:
            return 0
        self.ensure_ready()
        with self._lock:
            with self.path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                for row in rows:
                    writer.writerow(row)
        return len(rows)

    def clear(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()
        self.ensure_ready()

    def replace_all(self, rows: List[List[Any]]) -> int:
        if not rows:
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows(rows)
        return len(rows)

    def read_rows(self, limit: int = 0) -> List[List[str]]:
        if not self.path.exists():
            return []
        with self.path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        return rows[:limit] if limit else rows
