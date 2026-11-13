"""SQLite connection handling for ASTA.

One file, WAL mode, no ORM. Missing columns are added on startup so an older
database keeps working after the signal model grows.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Union

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id     TEXT    NOT NULL UNIQUE,
    scanner_id    TEXT    NOT NULL,
    scanner_name  TEXT    NOT NULL,
    market        TEXT    NOT NULL,
    symbol        TEXT    NOT NULL,
    timeframe     TEXT    NOT NULL,
    signal_type   TEXT    NOT NULL,
    confidence    REAL    NOT NULL,
    price         REAL,
    reason        TEXT    NOT NULL,
    strategy      TEXT    NOT NULL DEFAULT '',
    indicators    TEXT    NOT NULL DEFAULT '{}',
    metadata      TEXT    NOT NULL DEFAULT '{}',
    created_at    TEXT    NOT NULL,
    recorded_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_scanner  ON signals(scanner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_market   ON signals(market, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_symbol   ON signals(symbol, timeframe, created_at DESC);
"""

#: Columns added after V0.1 shipped; ALTER TABLE keeps existing databases valid.
MIGRATIONS = {
    "stop_loss": "REAL",
    "take_profit": "REAL",
    "risk_reward": "REAL",
    "risk_pct": "REAL",
    "atr": "REAL",
    "levels_source": "TEXT NOT NULL DEFAULT ''",
    "expires_at": "TEXT",
    "status": "TEXT NOT NULL DEFAULT 'open'",
    "closed_at": "TEXT",
    "realized_r": "REAL",
    "bars_held": "INTEGER",
    "source": "TEXT NOT NULL DEFAULT 'live'",
}


class Database:
    def __init__(self, path: Union[str, Path], timeout: float = 5.0):
        self.path = Path(path).expanduser()
        self.timeout = float(timeout)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=self.timeout)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            with self._lock:
                yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.session() as connection:
            connection.executescript(SCHEMA)
            existing = {
                row["name"] for row in connection.execute("PRAGMA table_info(signals)").fetchall()
            }
            for column, ddl in MIGRATIONS.items():
                if column in existing:
                    continue
                connection.execute(
                    "ALTER TABLE signals ADD COLUMN {} {}".format(column, ddl)
                )

    def close(self) -> None:  # connections are per-session; kept for symmetry
        return None
