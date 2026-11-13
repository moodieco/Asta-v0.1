"""Trading session helpers for forex."""

from __future__ import annotations

from datetime import datetime
from typing import List

from asta.utils.time_utils import ensure_utc

#: UTC hour ranges, end exclusive. Asia spans midnight.
SESSIONS = {
    "sydney": (21, 24),
    "tokyo": (0, 9),
    "london": (7, 16),
    "new_york": (12, 21),
}


def active_sessions(timestamp: datetime) -> List[str]:
    hour = ensure_utc(timestamp).hour
    return [name for name, (start, end) in SESSIONS.items() if start <= hour < end]


def session_for(timestamp: datetime) -> str:
    """Primary session label, ordered by liquidity."""
    sessions = active_sessions(timestamp)
    for preferred in ("london", "new_york", "tokyo", "sydney"):
        if preferred in sessions:
            return preferred
    return "off_hours"


def is_major_session(timestamp: datetime) -> bool:
    return bool({"london", "new_york"} & set(active_sessions(timestamp)))
