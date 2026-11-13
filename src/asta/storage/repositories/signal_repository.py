"""SQLite persistence for accepted signals."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from asta.core.signal_model import Signal
from asta.storage.database import Database
from asta.storage.models.signal_record import SignalRecord
from asta.utils.logger import get_logger
from asta.utils.time_utils import parse_datetime

_COLUMNS = (
    "signal_id, scanner_id, scanner_name, market, symbol, timeframe, signal_type, "
    "confidence, price, reason, strategy, indicators, metadata, created_at, recorded_at"
)


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
                    "INSERT INTO signals ({}) VALUES ({})".format(
                        _COLUMNS, ", ".join(["?"] * 15)
                    ),
                    (
                        record.signal_id,
                        record.scanner_id,
                        record.scanner_name,
                        record.market,
                        record.symbol,
                        record.timeframe,
                        record.signal_type,
                        record.confidence,
                        record.price,
                        record.reason,
                        record.strategy,
                        json.dumps(record.indicators),
                        json.dumps(record.metadata, default=str),
                        record.created_at,
                        record.recorded_at,
                    ),
                )
        except sqlite3.IntegrityError:
            self.logger.info("duplicate signal ignored", extra={"signal_id": record.signal_id})
            return False
        return True

    def save_many(self, signals: Iterable[Signal]) -> int:
        return sum(1 for signal in signals if self.save(signal))

    # -- reads ------------------------------------------------------------
    def count(self) -> int:
        with self.database.session() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM signals").fetchone()
        return int(row["total"] if row else 0)

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT {} FROM signals ORDER BY id DESC LIMIT ?".format(_COLUMNS), (int(limit),)
            ).fetchall()
        return [SignalRecord.from_row(row).to_dict() for row in rows]

    def by_market(self, market: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT {} FROM signals WHERE market = ? ORDER BY id DESC LIMIT ?".format(_COLUMNS),
                (market, int(limit)),
            ).fetchall()
        return [SignalRecord.from_row(row).to_dict() for row in rows]

    def by_scanner(self, scanner_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT {} FROM signals WHERE scanner_id = ? ORDER BY id DESC LIMIT ?".format(
                    _COLUMNS
                ),
                (scanner_id, int(limit)),
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
