"""Accepted-signal storage: JSONL by default, SQLite optional.

Both implementations expose the same tiny interface consumed by
:class:`asta.core.signal_manager.SignalManager`::

    append(signal) -> bool
    load_all() -> List[dict]
    tail(n) -> List[dict]
    count() -> int
    stats() -> Dict[str, int]
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from asta.core.signal_model import Signal
from asta.storage.database import Database
from asta.storage.repositories.signal_repository import SignalRepository
from asta.utils.logger import get_logger
from asta.utils.time_utils import parse_datetime


class SignalHistory:
    """Append-only JSONL log: one line per accepted signal."""

    def __init__(self, path: Optional[Union[str, Path]] = None, enabled: bool = True):
        self.path = Path(path).expanduser() if path else None
        self.enabled = bool(enabled and self.path)
        self._lock = threading.Lock()
        self.logger = get_logger("asta.history")
        if self.enabled and self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, signal: Union[Signal, Dict[str, Any]]) -> bool:
        if not self.enabled or self.path is None:
            return False
        record = signal.to_dict() if isinstance(signal, Signal) else dict(signal)
        record.setdefault("recorded_at", datetime.utcnow().isoformat() + "Z")
        line = json.dumps(record, default=str, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return True

    def append_many(self, signals: Iterable[Union[Signal, Dict[str, Any]]]) -> int:
        return sum(1 for signal in signals if self.append(signal))

    def load_all(self) -> List[Dict[str, Any]]:
        if not self.enabled or self.path is None or not self.path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    self.logger.warning("skipping malformed history line")
        return records

    def tail(self, count: int = 20) -> List[Dict[str, Any]]:
        return self.load_all()[-count:] if count > 0 else []

    def count(self) -> int:
        return len(self.load_all())

    def recorded_after(self, recorded_at: Optional[str], limit: int = 200) -> List[Dict[str, Any]]:
        if not recorded_at:
            return self.load_all()[:limit]
        return [r for r in self.load_all() if str(r.get("recorded_at", "")) > recorded_at][:limit]

    def open_signals(self, limit: int = 500) -> List[Dict[str, Any]]:
        records = [
            record
            for record in self.load_all()
            if str(record.get("status") or "open") == "open"
        ]
        return records[:limit]

    def update_outcome(
        self,
        signal_id: str,
        status: str,
        closed_at: Optional[str] = None,
        realized_r: Optional[float] = None,
        bars_held: Optional[int] = None,
    ) -> bool:
        if not self.enabled or self.path is None:
            return False
        records = self.load_all()
        changed = False
        for record in records:
            if record.get("signal_id") != signal_id:
                continue
            record["status"] = status
            record["closed_at"] = closed_at
            record["realized_r"] = realized_r
            record["bars_held"] = bars_held
            changed = True
        if changed:
            with self._lock:
                with self.path.open("w", encoding="utf-8") as handle:
                    for record in records:
                        handle.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
        return changed

    def last_timestamp(self, scanner_id: str, symbol: str) -> Optional[datetime]:
        for record in reversed(self.load_all()):
            if record.get("scanner_id") == scanner_id and record.get("symbol") == symbol:
                raw = record.get("timestamp")
                return parse_datetime(raw) if raw else None
        return None

    def stats(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for record in self.load_all():
            key = "{}:{}".format(record.get("market", "?"), record.get("scanner_id", "?"))
            counts[key] = counts.get(key, 0) + 1
        return counts


class SqliteSignalHistory:
    """SQLite-backed store with the same interface as :class:`SignalHistory`."""

    def __init__(self, repository: SignalRepository, enabled: bool = True):
        self.repository = repository
        self.enabled = enabled
        self.path = repository.database.path

    def append(self, signal: Union[Signal, Dict[str, Any]]) -> bool:
        if not self.enabled:
            return False
        if isinstance(signal, dict):
            raise TypeError("SqliteSignalHistory expects a Signal instance")
        return self.repository.save(signal)

    def load_all(self) -> List[Dict[str, Any]]:
        return self.repository.recent(limit=10000)

    def tail(self, count: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self.repository.recent(limit=count)))

    def count(self) -> int:
        return self.repository.count()

    def recorded_after(self, recorded_at: Optional[str], limit: int = 200) -> List[Dict[str, Any]]:
        return self.repository.recorded_after(recorded_at, limit)

    def open_signals(self, limit: int = 500) -> List[Dict[str, Any]]:
        return self.repository.open_signals(limit)

    def update_outcome(
        self,
        signal_id: str,
        status: str,
        closed_at: Optional[str] = None,
        realized_r: Optional[float] = None,
        bars_held: Optional[int] = None,
    ) -> bool:
        return self.repository.update_outcome(signal_id, status, closed_at, realized_r, bars_held)

    def last_timestamp(self, scanner_id: str, symbol: str) -> Optional[datetime]:
        return self.repository.last_timestamp(scanner_id, symbol)

    def stats(self) -> Dict[str, int]:
        return self.repository.stats()


def build_signal_history(
    backend: str,
    jsonl_path: Union[str, Path],
    sqlite_path: Union[str, Path],
    enabled: bool = True,
) -> Union[SignalHistory, SqliteSignalHistory]:
    """Factory used by the composition root."""
    if not enabled:
        return SignalHistory(path=jsonl_path, enabled=False)
    if backend == "sqlite":
        return SqliteSignalHistory(SignalRepository(Database(sqlite_path)), enabled=True)
    return SignalHistory(path=jsonl_path, enabled=True)
