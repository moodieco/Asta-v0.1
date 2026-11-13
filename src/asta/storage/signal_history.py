"""Append-only JSONL signal history.

Deliberately dumb: one line per accepted signal, fsync-friendly, easy to grep
and easy to replay into a database later.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from asta.core.signal_model import Signal
from asta.utils.logger import get_logger
from asta.utils.time_utils import parse_datetime


class SignalHistory:
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
