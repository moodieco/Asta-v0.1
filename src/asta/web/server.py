"""Loopback HTTP server for the dashboard SPA + JSON API.

Deliberately stdlib-only (``http.server``): ASTA targets Python 3.9 and keeps a
three-dependency footprint, so pulling in FastAPI/uvicorn for four read-only
endpoints would cost more than it buys. The server runs in its own thread while
the scanner owns the asyncio loop in the main thread.
"""

from __future__ import annotations

import gzip
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import unquote, urlparse

from asta.utils.logger import get_logger
from asta.web.queries import SignalQueries
from asta.web.routes import Routes

logger = get_logger("asta.web")

API_PREFIX = "/api/"


class _Handler(BaseHTTPRequestHandler):
    server_version = "ASTA-Dashboard"
    protocol_version = "HTTP/1.1"

    routes: Routes
    web_dir: Path

    # -- plumbing ---------------------------------------------------------
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.debug("%s - %s", self.address_string(), format % args)

    def _send(self, status: int, body: bytes, content_type: str, cache: str = "no-store") -> None:
        accepts_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
        payload = body
        headers = [
            ("Content-Type", content_type),
            ("Cache-Control", cache),
            ("X-Content-Type-Options", "nosniff"),
        ]
        if accepts_gzip and len(body) > 1024:
            payload = gzip.compress(body, compresslevel=6)
            headers.append(("Content-Encoding", "gzip"))
        headers.append(("Content-Length", str(len(payload))))
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    # -- static -----------------------------------------------------------
    def _resolve(self, path: str) -> Optional[Path]:
        candidate = (self.web_dir / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(self.web_dir.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    def _serve_file(self, target: Path) -> None:
        suffix = target.suffix.lower()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if suffix == ".html":
            content_type = "text/html; charset=utf-8"
        cache = "public, max-age=31536000, immutable" if "/assets/" in str(target) else "no-cache"
        self._send(200, target.read_bytes(), content_type, cache)

    # -- entry point ------------------------------------------------------
    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path.startswith(API_PREFIX):
            try:
                status, payload = self.routes.dispatch(path, parsed.query)
            except Exception as exc:  # noqa: BLE001 - never leak a traceback to the browser
                logger.exception("api failure")
                status, payload = 500, {"error": "internal error", "detail": str(exc)}
            self._json(status, payload)
            return

        if path in ("/", "/index.html"):
            index = self.web_dir / "index.html"
            if index.is_file():
                self._serve_file(index)
            else:
                self._json(
                    503,
                    {
                        "error": "dashboard build missing",
                        "hint": "run: cd web && npm install && npm run build",
                        "looked_for": str(index),
                    },
                )
            return

        target = self._resolve(path)
        if target is not None:
            self._serve_file(target)
            return

        # SPA fallback: unknown non-API paths render the app shell.
        index = self.web_dir / "index.html"
        if index.is_file():
            self._serve_file(index)
        else:
            self._json(404, {"error": "not found", "path": path})


class DashboardServer:
    """Owns the listening socket and its thread."""

    def __init__(
        self,
        db_path: Path | str,
        web_dir: Path | str,
        host: str = "127.0.0.1",
        port: int = 4310,
        status_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        config_summary: Optional[Callable[[], Dict[str, Any]]] = None,
        setup_summary: Optional[Callable[[], Dict[str, Any]]] = None,
        system_snapshot: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.host = host
        self.port = int(port)
        self.web_dir = Path(web_dir).expanduser().resolve()
        self.routes = Routes(
            SignalQueries(db_path),
            status_provider=status_provider,
            config_summary=config_summary,
            setup_summary=setup_summary,
            system_snapshot=system_snapshot,
        )
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def url(self) -> str:
        return "http://{}:{}/".format(self.host, self.port)

    def start(self) -> str:
        handler = type(
            "AstaDashboardHandler",
            (_Handler,),
            {"routes": self.routes, "web_dir": self.web_dir},
        )
        try:
            httpd = ThreadingHTTPServer((self.host, self.port), handler)
        except OSError as exc:
            raise OSError(
                "cannot bind {}:{} - {}".format(self.host, self.port, exc)
            ) from exc
        httpd.daemon_threads = True
        self._httpd = httpd
        self.port = httpd.server_address[1]
        self._thread = threading.Thread(target=httpd.serve_forever, name="asta-web", daemon=True)
        self._thread.start()
        logger.info("dashboard listening", extra={"url": self.url, "web_dir": str(self.web_dir)})
        return self.url

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("dashboard stopped")

    @property
    def running(self) -> bool:
        return self._httpd is not None
