"""HTTP routing for the ASTA dashboard API.

Kept separate from the socket layer so endpoints can be unit-tested by calling
`Routes.dispatch()` directly, with no server and no browser.

Read endpoints (signals, health, config) stay as they were. Write endpoints
(upload / uninstall / restore / test alert / share) are opt-in: they only work
when the matching provider is wired in, and they refuse ``access == "viewer"``.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import parse_qs

from asta import __version__
from asta.utils.exceptions import ConfigurationError
from asta.web.queries import SignalQueries

STARTED_AT = time.time()

Response = Tuple[int, Dict[str, Any]]

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class Routes:
    def __init__(
        self,
        queries: SignalQueries,
        status_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        config_summary: Optional[Callable[[], Dict[str, Any]]] = None,
        setup_summary: Optional[Callable[[], Dict[str, Any]]] = None,
        setup_complete_provider: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        system_snapshot: Optional[Callable[[], Dict[str, Any]]] = None,
        scanner_library: Optional[Any] = None,
        alert_log: Optional[Any] = None,
        test_alert_provider: Optional[Callable[[Optional[str]], Any]] = None,
        sample_alert_provider: Optional[Callable[[Optional[str]], Any]] = None,
        set_enabled_provider: Optional[Callable[[str, bool], Dict[str, Any]]] = None,
        share_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        regenerate_share_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.queries = queries
        self.status_provider = status_provider
        self.config_summary = config_summary
        self.setup_summary = setup_summary
        self.setup_complete_provider = setup_complete_provider
        self.system_snapshot = system_snapshot
        self.scanner_library = scanner_library
        self.alert_log = alert_log
        self.test_alert_provider = test_alert_provider
        self.sample_alert_provider = sample_alert_provider
        self.set_enabled_provider = set_enabled_provider
        self.share_provider = share_provider
        self.regenerate_share_provider = regenerate_share_provider

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
    def dispatch(
        self,
        path: str,
        raw_query: str = "",
        method: str = "GET",
        body: Optional[Dict[str, Any]] = None,
        access: str = "editor",
    ) -> Response:
        params = parse_qs(raw_query or "")
        body = body if isinstance(body, dict) else {}

        if path == "/api/access":
            return 200, {"access": access}

        # -- read-only endpoints -----------------------------------------
        if method == "GET":
            return self._dispatch_get(path, params, access)

        # -- write endpoints ----------------------------------------------
        if method in WRITE_METHODS:
            if access != "editor":
                return 403, {"error": "view-only access", "detail": "share link is read-only"}
            return self._dispatch_write(path, body)

        return 405, {"error": "method not allowed", "method": method}

    def _dispatch_get(
        self, path: str, params: Dict[str, list], access: str = "editor"
    ) -> Response:
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

        if path == "/api/setup":
            if self.setup_summary is None:
                return 200, {"available": False}
            return 200, self.setup_summary()

        if path == "/api/system":
            if self.system_snapshot is None:
                return 200, {"available": False}
            return 200, self.system_snapshot()

        if path == "/api/share":
            if self.share_provider is None:
                return 200, {"enabled": False}
            if access != "editor":
                # A view-only session must not read the editor token and upgrade
                # itself by copying it into the URL.
                return 200, {"enabled": True, "tokens": None, "note": "share tokens are editor-only"}
            return 200, self.share_provider()

        if path == "/api/scanners/library":
            if self.scanner_library is None:
                return 200, {"available": False, "installed": [], "trash": [], "history": []}
            return 200, {
                "available": True,
                "installed": self.scanner_library.list_installed(),
                "trash": self.scanner_library.list_trash(),
                "history": self.scanner_library.history(),
                "root": str(self.scanner_library.root),
                "trashRoot": str(self.scanner_library.trash_root),
            }

        if path == "/api/alerts/log":
            if self.alert_log is None:
                return 200, {"entries": []}
            return 200, {"entries": self.alert_log.list()}

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

    def _dispatch_write(self, path: str, body: Dict[str, Any]) -> Response:
        # -- scanner library ----------------------------------------------
        if path == "/api/scanners/install":
            if self.scanner_library is None:
                return 503, {"error": "scanner library unavailable"}
            try:
                record = self.scanner_library.install(
                    market=str(body.get("market", "")),
                    name=str(body.get("name", "")),
                    version=str(body.get("version", "")),
                    source=str(body.get("source", "")),
                    source_name=str(body.get("sourceName", "")),
                    timeframes=[str(tf) for tf in (body.get("timeframes") or [])],
                    description=str(body.get("description", "")),
                    dependencies=[str(dep) for dep in (body.get("dependencies") or [])],
                    changes=[str(change) for change in (body.get("changes") or [])],
                    sha256=str(body.get("sha256", "")),
                )
                return 200, {"installed": True, "record": record}
            except ConfigurationError as exc:
                return 400, {"error": str(exc)}

        for action in ("uninstall", "restore", "purge"):
            prefix = "/api/scanners/"
            suffix = "/" + action
            if path.startswith(prefix) and path.endswith(suffix):
                scanner_id = path[len(prefix) : -len(suffix)].strip("/")
                return self._scanner_mutation(action, scanner_id, body)

        if path.startswith("/api/scanners/") and path.endswith("/set-enabled"):
            scanner_id = path[len("/api/scanners/") : -len("/set-enabled")].strip("/")
            if self.set_enabled_provider is None:
                return 503, {"error": "set-enabled unavailable"}
            try:
                result = self.set_enabled_provider(scanner_id, bool(body.get("enabled", True)))
                return 200, {"scannerId": scanner_id, **result}
            except ConfigurationError as exc:
                return 400, {"error": str(exc)}

        # -- notifications -------------------------------------------------
        if path == "/api/alerts/test":
            if self.test_alert_provider is None:
                return 503, {"error": "test alerts unavailable"}
            market = body.get("market") or None
            try:
                results = self.test_alert_provider(market if isinstance(market, str) else None)
                return 200, {"results": results}
            except ConfigurationError as exc:
                return 400, {"error": str(exc)}

        if path == "/api/alerts/sample":
            if self.sample_alert_provider is None:
                return 503, {"error": "sample alerts unavailable"}
            market = body.get("market") or None
            try:
                results = self.sample_alert_provider(market if isinstance(market, str) else None)
                return 200, {"results": results}
            except ConfigurationError as exc:
                return 400, {"error": str(exc)}

        # -- setup ---------------------------------------------------------
        if path == "/api/setup/complete":
            if self.setup_complete_provider is None:
                return 503, {"error": "setup writes unavailable"}
            try:
                summary = self.setup_complete_provider(body or {})
            except ConfigurationError as exc:
                return 400, {"error": str(exc)}
            return 200, {"completed": True, "setup": summary}

        # -- share ---------------------------------------------------------
        if path == "/api/share/regenerate":
            if self.regenerate_share_provider is None:
                return 503, {"error": "share unavailable"}
            return 200, {"tokens": self.regenerate_share_provider()}

        return 404, {"error": "unknown endpoint", "path": path}

    def _scanner_mutation(self, action: str, scanner_id: str, body: Dict[str, Any]) -> Response:
        if self.scanner_library is None:
            return 503, {"error": "scanner library unavailable"}
        if not scanner_id:
            return 400, {"error": "scanner id required"}
        try:
            if action == "uninstall":
                record = self.scanner_library.uninstall(
                    scanner_id, reason=str(body.get("reason", ""))
                )
                return 200, {"uninstalled": True, "record": record}
            if action == "restore":
                record = self.scanner_library.restore(scanner_id)
                return 200, {"restored": True, "record": record}
            record = self.scanner_library.purge(scanner_id)
            return 200, {"purged": True, "record": record}
        except ConfigurationError as exc:
            return 400, {"error": str(exc)}
