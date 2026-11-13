"""Incremental sync: stored signals -> spreadsheet rows.

A cursor file records the last exported ``recorded_at`` so restarts and repeated
runs never duplicate rows.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict

from asta.integrations.sheets.base import SheetWriter, signal_to_row
from asta.integrations.sheets.csv_writer import CsvSheetWriter
from asta.integrations.sheets.google_sheets import (
    GoogleServiceAccountAuth,
    GoogleSheetsAuth,
    GoogleSheetsWriter,
)
from asta.utils.exceptions import SheetsError
from asta.utils.logger import get_logger
from asta.utils.time_utils import isoformat, utcnow


def build_sheet_writer(settings: Any, project_root: Path) -> SheetWriter:
    """Instantiate the configured driver."""
    if settings.driver == "google":
        if getattr(settings, "service_account_path", ""):
            auth = GoogleServiceAccountAuth(Path(settings.service_account_path).expanduser())
        else:
            auth = GoogleSheetsAuth(Path(settings.token_path).expanduser())
        return GoogleSheetsWriter(
            auth,
            spreadsheet_id=settings.spreadsheet_id,
            sheet_name=settings.sheet_name,
            create_if_missing=settings.create_if_missing,
        )
    path = Path(settings.csv_path).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return CsvSheetWriter(path)


class SheetSyncService:
    def __init__(
        self,
        writer: SheetWriter,
        history,
        state_path: Path,
        batch_size: int = 200,
    ):
        self.writer = writer
        self.history = history
        self.state_path = Path(state_path)
        self.batch_size = int(batch_size)
        self.logger = get_logger("asta.sheets.sync")
        self._lock = threading.Lock()

    # -- state ------------------------------------------------------------
    def _read_raw(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {"drivers": {}}
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.logger.warning("sync state is corrupt, starting from the beginning")
            return {"drivers": {}}
        if "drivers" not in raw:
            # legacy flat file: it belonged to whichever driver wrote it
            legacy = {
                "last_recorded_at": raw.get("last_recorded_at", ""),
                "total_rows": int(raw.get("total_rows", 0)),
                "updated_at": raw.get("updated_at", ""),
            }
            has_data = bool(legacy["last_recorded_at"] or legacy["total_rows"])
            # before per-driver cursors only the csv driver existed
            return {"drivers": {"csv": legacy} if has_data else {}}
        return raw

    def _load_state(self) -> Dict[str, Any]:
        raw = self._read_raw()
        return raw["drivers"].setdefault(
            self.writer.name, {"last_recorded_at": "", "total_rows": 0, "updated_at": ""}
        )

    def _save_state(self, state: Dict[str, Any]) -> None:
        raw = self._read_raw()
        raw["drivers"][self.writer.name] = state
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def status(self) -> Dict[str, Any]:
        state = self._load_state()
        target = getattr(self.writer, "path", None) or getattr(self.writer, "spreadsheet_id", "")
        return {
            "enabled": True,
            "driver": self.writer.name,
            "target": str(target),
            "last_recorded_at": state.get("last_recorded_at", ""),
            "total_rows": state.get("total_rows", 0),
            "updated_at": state.get("updated_at", ""),
        }

    # -- export -----------------------------------------------------------
    def sync_once(self) -> Dict[str, Any]:
        with self._lock:
            state = self._load_state()
            records = self.history.recorded_after(
                state.get("last_recorded_at") or None, self.batch_size
            )
            if not records:
                return {
                    "driver": self.writer.name,
                    "appended": 0,
                    "total_rows": state.get("total_rows", 0),
                }

            try:
                self.writer.ensure_ready()
                rows = [signal_to_row(record) for record in records]
                appended = self.writer.append_rows(rows)
            except SheetsError as exc:
                self.logger.error("sheet export failed", extra={"error": str(exc)})
                return {"driver": self.writer.name, "appended": 0, "error": str(exc)}

            cursor = max(str(record.get("recorded_at", "")) for record in records)
            state["last_recorded_at"] = cursor
            state["total_rows"] = int(state.get("total_rows", 0)) + appended
            state["updated_at"] = isoformat(utcnow())
            self._save_state(state)
            self.logger.info(
                "sheet rows exported",
                extra={"driver": self.writer.name, "rows": appended, "total": state["total_rows"]},
            )
            return {
                "driver": self.writer.name,
                "appended": appended,
                "total_rows": state["total_rows"],
                "cursor": cursor,
            }

    def close(self) -> None:
        try:
            self.writer.close()
        except Exception:  # noqa: BLE001 - shutdown must not raise
            pass
