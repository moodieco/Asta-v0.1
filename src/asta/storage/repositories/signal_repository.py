"""SQLite persistence for accepted signals, including risk levels and outcomes."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from asta.core.signal_model import Signal
from asta.storage.database import Database
from asta.storage.models.signal_record import SignalRecord
from asta.utils.logger import get_logger
from asta.utils.time_utils import parse_datetime

_COLUMNS = SignalRecord.column_names()
_SELECT = ", ".join(_COLUMNS)
_PLACEHOLDERS = ", ".join(["?"] * len(_COLUMNS))


class SignalRepository:
    def __init__(self, database: Database):
        self.database = database
        self.logger = get_logger("asta.repository.signals")

    # -- writes -----------------------------------------------------------
    def save(self, signal: Signal) -> bool:
        record = SignalRecord.from_signal(signal)
        try:
            with self.database.session() as connection:
                connection.execute(
                    "INSERT INTO signals ({}) VALUES ({})".format(_SELECT, _PLACEHOLDERS),
                    tuple(record.as_row()),
                )
        except sqlite3.IntegrityError:
            self.logger.info("duplicate signal ignored", extra={"signal_id": record.signal_id})
            return False
        return True

    def save_many(self, signals: Iterable[Signal]) -> int:
        return sum(1 for signal in signals if self.save(signal))

    def update_outcome(
        self,
        signal_id: str,
        status: str,
        closed_at: Optional[str] = None,
        realized_r: Optional[float] = None,
        bars_held: Optional[int] = None,
    ) -> bool:
        with self.database.session() as connection:
            cursor = connection.execute(
                "UPDATE signals SET status = ?, closed_at = ?, realized_r = ?, bars_held = ? "
                "WHERE signal_id = ?",
                (status, closed_at, realized_r, bars_held, signal_id),
            )
        return cursor.rowcount > 0

    # -- reads ------------------------------------------------------------
    def count(self) -> int:
        with self.database.session() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM signals").fetchone()
        return int(row["total"] if row else 0)

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT {} FROM signals ORDER BY id DESC LIMIT ?".format(_SELECT), (int(limit),)
            ).fetchall()
        return [SignalRecord.from_row(row).to_dict() for row in rows]

    def by_market(self, market: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT {} FROM signals WHERE market = ? ORDER BY id DESC LIMIT ?".format(_SELECT),
                (market, int(limit)),
            ).fetchall()
        return [SignalRecord.from_row(row).to_dict() for row in rows]

    def by_scanner(self, scanner_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT {} FROM signals WHERE scanner_id = ? ORDER BY id DESC LIMIT ?".format(
                    _SELECT
                ),
                (scanner_id, int(limit)),
            ).fetchall()
        return [SignalRecord.from_row(row).to_dict() for row in rows]

    def recorded_after(self, recorded_at: Optional[str], limit: int = 200) -> List[Dict[str, Any]]:
        """Rows inserted after ``recorded_at`` (ISO string), oldest first."""
        with self.database.session() as connection:
            if recorded_at:
                rows = connection.execute(
                    "SELECT {} FROM signals WHERE recorded_at > ? ORDER BY id ASC LIMIT ?".format(
                        _SELECT
                    ),
                    (recorded_at, int(limit)),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT {} FROM signals ORDER BY id ASC LIMIT ?".format(_SELECT),
                    (int(limit),),
                ).fetchall()
        return [SignalRecord.from_row(row).to_dict() for row in rows]

    def open_signals(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT {} FROM signals WHERE status = 'open' ORDER BY id ASC LIMIT ?".format(
                    _SELECT
                ),
                (int(limit),),
            ).fetchall()
        return [SignalRecord.from_row(row).to_dict() for row in rows]

    def last_timestamp(self, scanner_id: str, symbol: str) -> Optional[datetime]:
        with self.database.session() as connection:
            row = connection.execute(
                "SELECT created_at FROM signals WHERE scanner_id = ? AND symbol = ? "
                "ORDER BY id DESC LIMIT 1",
                (scanner_id, symbol),
            ).fetchone()
        return parse_datetime(row["created_at"]) if row else None

    def stats(self) -> Dict[str, int]:
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT market, scanner_id, COUNT(*) AS total FROM signals "
                "GROUP BY market, scanner_id"
            ).fetchall()
        return {"{}:{}".format(row["market"], row["scanner_id"]): int(row["total"]) for row in rows}

    def outcome_stats(self) -> Dict[str, Any]:
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS total, AVG(realized_r) AS avg_r FROM signals "
                "GROUP BY status"
            ).fetchall()
        return {
            row["status"]: {"count": int(row["total"]), "avg_r": row["avg_r"]}
            for row in rows
        }
