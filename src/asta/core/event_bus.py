"""Tiny synchronous event bus.

Used to decouple "what happened" (a scanner found a signal, a cycle finished,
a provider failed) from "who cares" (logging, metrics, future dashboards).
Handlers must never break the pipeline, so exceptions are logged and swallowed.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, DefaultDict, Dict, List

from asta.utils.logger import get_logger
from asta.utils.time_utils import utcnow

Handler = Callable[["Event"], None]


@dataclass(frozen=True)
class Event:
    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        # "name" is reserved on LogRecord, so the payload key is "event".
        return {"event": self.name, "timestamp": self.timestamp.isoformat(), **self.payload}


class EventBus:
    def __init__(self):
        self._handlers: DefaultDict[str, List[Handler]] = defaultdict(list)
        self._history: List[Event] = []
        self.logger = get_logger("asta.events")

    def subscribe(self, name: str, handler: Handler) -> None:
        """Subscribe to one event name, or ``*`` for everything."""
        if handler not in self._handlers[name]:
            self._handlers[name].append(handler)

    def unsubscribe(self, name: str, handler: Handler) -> None:
        if handler in self._handlers.get(name, []):
            self._handlers[name].remove(handler)

    def publish(self, name: str, **payload: Any) -> Event:
        event = Event(name=name, payload=payload)
        self._history.append(event)
        for handler in list(self._handlers.get(name, [])) + list(self._handlers.get("*", [])):
            try:
                handler(event)
            except Exception:  # noqa: BLE001 - a bad subscriber must not kill a cycle
                self.logger.exception("event handler failed", extra={"event": name})
        return event

    def subscribers(self, name: str) -> int:
        return len(self._handlers.get(name, []))

    @property
    def history(self) -> List[Event]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()
        self._handlers.clear()
