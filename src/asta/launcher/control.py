"""Local control API for the launcher panel.

The panel is a normal web page (HTML/CSS/JS) shown in a native WebView window, because
this machine's Tk 8.5 paints only native controls - every drawn widget comes out
blank. The page talks to this loopback-only service:

    GET  /                      the panel itself
    GET  /api/launcher/status   supervisor state + /api/health of the dashboard
    POST /api/launcher/start    spawn `asta serve` (detached) and wait for health
    POST /api/launcher/stop     SIGTERM the child
    POST /api/launcher/restart
    POST /api/launcher/open     open the dashboard in the browser
    GET  /api/launcher/setup    quick-setup context (secrets masked)
    POST /api/launcher/setup/validate
    POST /api/launcher/setup/save

Every POST must carry ``X-ASTA-Panel: 1`` so a random web page cannot drive the API
(and the listener is bound to 127.0.0.1 only).
"""

from __future__ import annotations

import gzip
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from asta.config import load_config
from asta.core.scanner_registry import ScannerRegistry
from asta.launcher.supervisor import Supervisor
from asta.setup import secrets, validators, writer
from asta.setup.state import SetupState
from asta.utils.logger import get_logger

logger = get_logger("asta.launcher.panel")

PANEL_DIR = Path(__file__).resolve().parent / "panel"
MARKETS = ("forex", "crypto", "stock")
WEBHOOK_ENV = {
    "forex": "DISCORD_WEBHOOK_FOREX",
    "crypto": "DISCORD_WEBHOOK_CRYPTO",
    "stock": "DISCORD_WEBHOOK_STOCK",
}
MAX_BODY = 64 * 1024


class PanelRoutes:
    def __init__(self, supervisor: Supervisor, config_dir: Optional[str] = None):
        self.supervisor = supervisor
        self.config_dir = config_dir
        self.config = load_config(config_dir, require=False)
        self.root = Path(self.config.project_root).resolve()
        self.state = SetupState.load(self.config.resolve_path(self.config.setup.state_path))

    # -- helpers ----------------------------------------------------------
    def _env(self) -> Dict[str, str]:
        return secrets.read_env(self.root / ".env")

    def _scanners(self) -> list:
        items = []
        try:
            registry = ScannerRegistry()
            registry.discover()
            overrides = self.config.scanner_overrides or {}
            for scanner_id, config in sorted(registry.load_configs().items()):
                if isinstance(overrides.get(scanner_id), dict):
                    config = config.with_overrides(overrides[scanner_id])
                items.append(
                    {
                        "id": scanner_id,
                        "name": config.name,
                        "market": getattr(config.market, "value", str(config.market)),
                        "timeframe": config.timeframe,
                        "enabled": bool(config.enabled),
                    }
                )
        except Exception:  # noqa: BLE001 - panel must render even if discovery fails
            logger.exception("scanner discovery failed")
        return items

    def status(self) -> Dict[str, Any]:
        status = self.supervisor.status()
        return {
            "supervisor": status,
            "setupComplete": self.state.complete,
            "config": {
                "root": str(self.root),
                "environment": self.config.environment,
                "port": self.config.web.port,
                "logPath": status.get("logPath"),
            },
        }

    # -- setup ------------------------------------------------------------
    def setup_context(self) -> Dict[str, Any]:
        env = self._env()
        webhooks = {}
        for market in MARKETS:
            key = WEBHOOK_ENV[market]
            value = env.get(key, "")
            webhooks[market] = {
                "env": key,
                "configured": secrets.is_configured(value),
                "masked": secrets.mask(value),
            }
        providers = self.config.providers or {}
        return {
            "state": {"complete": self.state.complete, "steps": self.state.completed_steps()},
            "webhooks": webhooks,
            "providers": {
                "forex": {
                    "type": (providers.get("forex") or {}).get("type", "mt5"),
                    "terminalUrl": env.get("MT5_TERMINAL_URL", ""),
                    "tokenConfigured": secrets.is_configured(env.get("MT5_TERMINAL_TOKEN")),
                },
                "crypto": {"type": (providers.get("crypto") or {}).get("type", "binance")},
                "stock": {"type": (providers.get("stock") or {}).get("type", "yahoo")},
            },
            "scanners": self._scanners(),
            "system": {
                "dbPath": self.config.storage.sqlite_path,
                "host": self.config.web.host,
                "port": self.config.web.port,
                "openBrowser": self.config.web.open_browser,
            },
        }

    def _merged_env(self, payload: Dict[str, Any]) -> Dict[str, str]:
        env = dict(self._env())
        for market in MARKETS:
            value = str((payload.get("webhooks") or {}).get(market, "") or "").strip()
            if value:
                env[WEBHOOK_ENV[market]] = value
        mt5 = payload.get("mt5") or {}
        if str(mt5.get("url", "") or "").strip():
            env["MT5_TERMINAL_URL"] = str(mt5["url"]).strip()
        if str(mt5.get("token", "") or "").strip():
            env["MT5_TERMINAL_TOKEN"] = str(mt5["token"]).strip()
        return env

    def validate_setup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        system = payload.get("system") or {}
        try:
            port = int(system.get("port") or self.config.web.port)
        except (TypeError, ValueError):
            port = 0
        results = validators.validate_all(
            self._merged_env(payload),
            self.config.providers or {},
            str(system.get("dbPath") or self.config.storage.sqlite_path),
            str(system.get("host") or self.config.web.host),
            port,
        )
        return {"results": results}

    def save_setup(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        env_updates = {}
        for market in MARKETS:
            value = str((payload.get("webhooks") or {}).get(market, "") or "").strip()
            if value:
                env_updates[WEBHOOK_ENV[market]] = value
        mt5 = payload.get("mt5") or {}
        if str(mt5.get("url", "") or "").strip():
            env_updates["MT5_TERMINAL_URL"] = str(mt5["url"]).strip()
        if str(mt5.get("token", "") or "").strip():
            env_updates["MT5_TERMINAL_TOKEN"] = str(mt5["token"]).strip()
        if env_updates:
            secrets.write_env(self.root / ".env", env_updates)

        system = payload.get("system") or {}
        try:
            port = int(system.get("port") or self.config.web.port)
        except (TypeError, ValueError):
            port = self.config.web.port
        app_doc = writer.set_web(
            self.root / "config" / "app.yaml",
            host=str(system.get("host") or self.config.web.host),
            port=port,
        )
        if system.get("dbPath"):
            writer.set_sqlite_path(self.root / "config" / "app.yaml", str(system["dbPath"]))
        app_doc.set(["web", "open_browser"], bool(system.get("openBrowser", True)))
        app_doc.write()

        scanners = payload.get("scanners") or {}
        if scanners:
            markets_doc = writer.YamlFile(self.root / "config" / "markets.yaml")
            for scanner_id, enabled in scanners.items():
                markets_doc.set(["scanner_overrides", scanner_id, "enabled"], bool(enabled))
            markets_doc.write()

        env = self._env()
        self.state.record_step(
            "discord",
            {"configured": [m for m in MARKETS if secrets.is_configured(env.get(WEBHOOK_ENV[m]))]},
        )
        self.state.record_step("scanners", {"enabled": sorted(k for k, v in scanners.items() if v)})
        self.state.record_step("system", {"port": port, "database": system.get("dbPath")})
        self.state.record_step("review", {"validated": True})
        self.state.mark_complete(
            {
                "webhooks": {m: secrets.mask(env.get(WEBHOOK_ENV[m], "")) for m in MARKETS},
                "port": port,
                "scanners": len([v for v in scanners.values() if v]),
            }
        )

        started = None
        if payload.get("startAfter"):
            started = self.supervisor.start(open_browser=bool(system.get("openBrowser", True)))
        return {"saved": True, "started": started}


class _Handler(BaseHTTPRequestHandler):
    server_version = "ASTA-Panel"
    protocol_version = "HTTP/1.1"
    routes: PanelRoutes
    panel_dir: Path

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.debug("%s - %s", self.address_string(), format % args)

    # -- io ---------------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str, cache: str = "no-store") -> None:
        payload = body
        headers = [
            ("Content-Type", content_type),
            ("Cache-Control", cache),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
        ]
        if "gzip" in self.headers.get("Accept-Encoding", "") and len(body) > 1024:
            payload = gzip.compress(body, compresslevel=6)
            headers.append(("Content-Encoding", "gzip"))
        headers.append(("Content-Length", str(len(payload))))
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, payload: Dict[str, Any]) -> None:
        self._send(status, json.dumps(payload, default=str).encode(), "application/json; charset=utf-8")

    def _body(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if length <= 0 or length > MAX_BODY:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}

    def _allowed(self) -> bool:
        if self.headers.get("X-ASTA-Panel") != "1":
            return False
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = urlparse(origin).hostname or ""
        return host in ("127.0.0.1", "localhost", "::1")

    # -- routes -----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            if path == "/api/launcher/status":
                self._json(200, self.routes.status())
                return
            if path == "/api/launcher/setup":
                self._json(200, self.routes.setup_context())
                return
            if path == "/api/launcher/log":
                self._json(200, {"lines": self.routes.supervisor.tail_log(60)})
                return
            self._json(404, {"error": "unknown endpoint", "path": path})
            return

        target = (self.panel_dir / (path.lstrip("/") or "index.html")).resolve()
        try:
            target.relative_to(self.panel_dir.resolve())
        except ValueError:
            self._json(403, {"error": "forbidden"})
            return
        if not target.is_file():
            target = self.panel_dir / "index.html"
        content_type = mimetypes.guess_type(str(target))[0] or "text/html"
        if target.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        self._send(200, target.read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not self._allowed():
            self._json(403, {"error": "missing X-ASTA-Panel header"})
            return
        payload = self._body()
        try:
            if path == "/api/launcher/start":
                self._json(200, {"result": self.routes.supervisor.start(open_browser=True)})
            elif path == "/api/launcher/stop":
                self._json(200, {"result": self.routes.supervisor.stop()})
            elif path == "/api/launcher/restart":
                self._json(200, {"result": self.routes.supervisor.restart(open_browser=True)})
            elif path == "/api/launcher/open":
                self._json(200, {"opened": self.routes.supervisor.open_dashboard()})
            elif path == "/api/launcher/setup/validate":
                self._json(200, self.routes.validate_setup(payload))
            elif path == "/api/launcher/setup/save":
                self._json(200, self.routes.save_setup(payload))
            else:
                self._json(404, {"error": "unknown endpoint", "path": path})
        except Exception as exc:  # noqa: BLE001 - report, never crash the panel
            logger.exception("panel action failed")
            self._json(500, {"error": str(exc)})


class PanelServer:
    def __init__(self, supervisor: Supervisor, host: str = "127.0.0.1", port: int = 4311,
                 config_dir: Optional[str] = None):
        self.host = host
        self.port = int(port)
        self.routes = PanelRoutes(supervisor, config_dir=config_dir)
        self.panel_dir = PANEL_DIR
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def url(self) -> str:
        return "http://{}:{}/".format(self.host, self.port)

    def start(self) -> str:
        handler = type("AstaPanelHandler", (_Handler,), {"routes": self.routes, "panel_dir": self.panel_dir})
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="asta-panel", daemon=True)
        self._thread.start()
        logger.info("launcher panel listening", extra={"url": self.url})
        return self.url

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
