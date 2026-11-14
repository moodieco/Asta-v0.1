"""HTTP routing for the ASTA dashboard API.

Kept separate from the socket layer so endpoints can be unit-tested by calling
`Routes.dispatch()` directly, with no server and no browser.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import parse_qs

from asta import __version__
from asta.web.queries import SignalQueries

STARTED_AT = time.time()

Response = Tuple[int, Dict[str, Any]]


class Routes:
    def __init__(
        self,
        queries: SignalQueries,
        status_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        config_summary: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.queries = queries
        self.status_provider = status_provider
        self.config_summary = config_summary

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _int(params: Dict[str, list], key: str, default: Optional[int]) -> Optional[int]:
        raw = params.get(key, [None])[0]
        if raw in (None, ""):
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def health(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "status": "ok",
            "version": __version__,
            "pid": os.getpid(),
            "uptimeSeconds": round(time.time() - STARTED_AT, 1),
            "database": {
                "available": self.queries.available(),
                "signals": self.queries.count(),
            },
        }
        if self.status_provider is not None:
            try:
                payload.update(self.status_provider() or {})
            except Exception as exc:  # noqa: BLE001 - status must never 500
                payload["statusProviderError"] = str(exc)
        return payload

    # -- dispatch ---------------------------------------------------------
    def dispatch(self, path: str, raw_query: str = "") -> Response:
        params = parse_qs(raw_query or "")
        if path in ("/api/health", "/api/status"):
            return 200, self.health()

        if path == "/api/meta":
            return 200, self.queries.meta()

        if path == "/api/facets":
            return 200, self.queries.facets()

        if path == "/api/config":
            if self.config_summary is None:
                return 200, {"available": False}
            return 200, self.config_summary()

        if path == "/api/signals":
            signals, total = self.queries.list_signals(
                status=params.get("status", [None])[0],
                scanner=params.get("scanner", [None])[0],
                market=params.get("market", [None])[0],
                timeframe=params.get("timeframe", [None])[0],
                query=params.get("q", [None])[0],
                sort=params.get("sort", ["newest"])[0] or "newest",
                limit=self._int(params, "limit", None),
                offset=self._int(params, "offset", 0) or 0,
            )
            return 200, {
                "meta": self.queries.meta(),
                "signals": signals,
                "total": total,
                "offset": self._int(params, "offset", 0) or 0,
                "hasMore": total > (self._int(params, "offset", 0) or 0) + len(signals),
                "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

        if path.startswith("/api/signals/"):
            key = path[len("/api/signals/") :].strip("/")
            signal = self.queries.get_signal(key)
            if signal is None:
                return 404, {"error": "signal not found", "key": key}
            return 200, signal

        return 404, {"error": "unknown endpoint", "path": path}
