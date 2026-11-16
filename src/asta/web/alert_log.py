"""Append-only delivery log for test and sample notifications.

The engine does not persist webhook responses (it stores signals, not delivery),
so the dashboard keeps its own JSONL record of every operator-triggered send
(test alert / sample card) under ``data/alerts/delivery_log.jsonl``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List


class AlertLog:
    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()

    def append(self, entry: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = dict(entry)
        entry.setdefault("at", _now())
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, sort_keys=True, default=str) + "\n")

    def list(self, limit: int = 200) -> List[Dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: List[Dict[str, Any]] = []
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
        except OSError:
            return []
        return list(reversed(rows[-limit:]))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
