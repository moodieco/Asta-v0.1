"""Quick-setup bookkeeping.

``config/setup_state.json`` records that setup happened, when, and which answers
were chosen. It deliberately holds **no secrets** - only masked or non-sensitive
summary data - so it is safe to inspect and safe to commit if the user wants to.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

STATE_VERSION = 1
STEPS = ("discord", "providers", "scanners", "system", "review")


class SetupState:
    def __init__(self, path: Path | str, data: Optional[Dict[str, Any]] = None):
        self.path = Path(path).expanduser()
        self.data: Dict[str, Any] = data or {
            "version": STATE_VERSION,
            "completed_at": None,
            "steps": {},
        }

    # -- persistence ------------------------------------------------------
    @classmethod
    def load(cls, path: Path | str) -> "SetupState":
        target = Path(path).expanduser()
        if not target.exists():
            return cls(target)
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls(target)
        if not isinstance(data, dict):
            return cls(target)
        data.setdefault("version", STATE_VERSION)
        data.setdefault("completed_at", None)
        data.setdefault("steps", {})
        return cls(target, data)

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.data, indent=2, sort_keys=True) + "\n"
        handle, temp_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".setup_state.", suffix=".tmp"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return self.path

    # -- queries ----------------------------------------------------------
    @property
    def complete(self) -> bool:
        return bool(self.data.get("completed_at"))

    def completed_steps(self) -> List[str]:
        return [step for step in STEPS if step in (self.data.get("steps") or {})]

    def step(self, name: str) -> Dict[str, Any]:
        return dict((self.data.get("steps") or {}).get(name) or {})

    # -- mutations --------------------------------------------------------
    def record_step(self, name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        steps = self.data.setdefault("steps", {})
        steps[name] = dict(payload or {})
        self.data["updated_at"] = _now()

    def mark_complete(self, summary: Optional[Dict[str, Any]] = None) -> None:
        self.data["completed_at"] = _now()
        if summary is not None:
            self.data["summary"] = summary
        self.save()

    def reset(self) -> None:
        self.data = {"version": STATE_VERSION, "completed_at": None, "steps": {}}
        self.save()


def _now() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
