"""Loopback HTTP server for the dashboard SPA + JSON API.

Deliberately stdlib-only (``http.server``): ASTA targets Python 3.9 and keeps a
three-dependency footprint, so pulling in FastAPI/uvicorn would cost more than it
buys. The server runs in its own thread while the scanner owns the asyncio loop
in the main thread.

When ``bind`` is ``0.0.0.0`` the dashboard is reachable from the LAN; any request
not from loopback must present a valid share token (editor or view-only). Loopback
stays open for the machine owner — unless the request arrived through a tunnel or
reverse proxy (``X-Forwarded-*`` / ``Cf-*`` headers), because those connect over
loopback and would otherwise hand every internet visitor editor access.

A token supplied as ``?token=`` is remembered in an ``HttpOnly`` cookie so the
SPA's asset and API requests keep their role without the token in every URL.
"""

from __future__ import annotations

import gzip
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, quote, unquote, urlparse

from asta.utils.logger import get_logger
from asta.web.queries import SignalQueries
from asta.web.routes import Routes

logger = get_logger("asta.web")

API_PREFIX = "/api/"
MAX_BODY = 48 * 1024 * 1024  # .zip bundles upload base64-encoded, up to 25 MB source
TOKEN_COOKIE = "asta_share"
TOKEN_COOKIE_MAX_AGE = 7 * 24 * 3600

# Headers that only a tunnel / reverse proxy adds. Their presence means loopback
# is the proxy, not the owner.
_PROXY_HEADERS = (
    "X-Forwarded-For",
    "X-Forwarded-Host",
    "X-Forwarded-Proto",
    "Forwarded",
    "Cf-Connecting-Ip",
    "Cf-Ray",
)

_DENIED_HTML = (
    "<!doctype html><html><body style='font-family:system-ui;display:grid;place-items:center;"
    "min-height:100vh;margin:0;color:#334155'><div style='text-align:center;max-width:420px;"
    "padding:24px'><h2 style='margin:0 0 8px;font-size:18px'>ASTA — share link required</h2>"
    "<p style='margin:0;font-size:14px;line-height:1.5'>This dashboard is only reachable with a "
    "valid share link. Open the dashboard on this machine and copy the editor or view-only URL.</p>"
    "</div></body></html>"
)


class _Handler(BaseHTTPRequestHandler):
    server_version = "ASTA-Dashboard"
    protocol_version = "HTTP/1.1"

    routes: Routes
    web_dir: Path
    share_manager: Optional[Any] = None
    _pending_cookie: Optional[str] = None

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
        cookie = self._pending_cookie
        if cookie:
            headers.append(("Set-Cookie", cookie))
            self._pending_cookie = None
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

    def _html(self, status: int, body: str) -> None:
        self._send(status, body.encode("utf-8"), "text/html; charset=utf-8")

    # -- auth -------------------------------------------------------------
    def _token(self) -> Optional[str]:
        query = parse_qs(urlparse(self.path).query)
        if query.get("token"):
            return query["token"][0]
        return self.headers.get("X-ASTA-Token") or self._cookie_token() or None

    def _cookie_token(self) -> Optional[str]:
        header = self.headers.get("Cookie") or ""
        for chunk in header.split(";"):
            name, _, value = chunk.strip().partition("=")
            if name == TOKEN_COOKIE and value:
                return unquote(value)
        return None

    def _proxied(self) -> bool:
        """True when a tunnel/reverse proxy relayed this request.

        cloudflared (and ngrok, Caddy, ...) connect over loopback, so
        ``client_address`` alone would make every internet visitor look like the
        machine owner. Proxy-only headers are the tell.
        """
        return any(self.headers.get(header) for header in _PROXY_HEADERS)

    def _secure_request(self) -> bool:
        proto = (self.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip().lower()
        return proto == "https"

    def _remember_token(self) -> None:
        """Persist a ``?token=`` from the URL into an HttpOnly cookie."""
        query = parse_qs(urlparse(self.path).query)
        token = (query.get("token") or [None])[0]
        if not token or self._cookie_token() == token:
            return
        parts = [
            "{}={}".format(TOKEN_COOKIE, quote(token, safe="")),
            "Path=/",
            "HttpOnly",
            "SameSite=Lax",
            "Max-Age={}".format(TOKEN_COOKIE_MAX_AGE),
        ]
        if self._secure_request():
            parts.append("Secure")
        self._pending_cookie = "; ".join(parts)

    def _access(self) -> str:
        ip = self.client_address[0]
        if ip in ("127.0.0.1", "::1", "localhost") and not self._proxied():
            return "editor"
        share = getattr(self, "share_manager", None)
        if share is None:
            return "denied"
        access = share.authenticate(self._token()) or "denied"
        if access != "denied":
            self._remember_token()
        return access

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

    def _serve_spa(self) -> None:
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

    # -- body -------------------------------------------------------------
    def _read_body(self) -> Optional[Dict[str, Any]]:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        if length > MAX_BODY:
            return None
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    # -- entry points -----------------------------------------------------
    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        # Unauthenticated liveness probe: hosting platforms (Render, Fly, k8s)
        # cannot carry a share token, and `/api/health` is gated like any other
        # endpoint. This exposes nothing but "the process is up".
        if path in ("/healthz", "/healthz/"):
            self._json(200, {"ok": True})
            return

        access = self._access()

        if path.startswith(API_PREFIX):
            if access == "denied":
                self._json(401, {"error": "share token required"})
                return
            try:
                status, payload = self.routes.dispatch(path, parsed.query, "GET", access=access)
            except Exception as exc:  # noqa: BLE001 - never leak a traceback to the browser
                logger.exception("api failure")
                status, payload = 500, {"error": "internal error", "detail": str(exc)}
            self._json(status, payload)
            return

        if access == "denied":
            self._html(401, _DENIED_HTML)
            return

        if path in ("/", "/index.html"):
            self._serve_spa()
            return

        target = self._resolve(path)
        if target is not None:
            self._serve_file(target)
            return

        # SPA fallback: unknown non-API paths render the app shell.
        self._serve_spa()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch_write("POST")

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch_write("DELETE")

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch_write("PUT")

    def _dispatch_write(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        access = self._access()
        if access == "denied":
            self._json(401, {"error": "share token required"})
            return
        if not path.startswith(API_PREFIX):
            self._json(404, {"error": "not found", "path": path})
            return
        body = self._read_body()
        if body is None:
            self._json(413, {"error": "request body too large"})
            return
        try:
            status, payload = self.routes.dispatch(path, parsed.query, method, body, access=access)
        except Exception as exc:  # noqa: BLE001
            logger.exception("api write failure")
            status, payload = 500, {"error": "internal error", "detail": str(exc)}
        self._json(status, payload)


class DashboardServer:
    """Owns the listening socket and its thread."""

    def __init__(
        self,
        db_path: Path | str,
        web_dir: Path | str,
        host: str = "127.0.0.1",
        port: int = 4310,
        bind: Optional[str] = None,
        status_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        config_summary: Optional[Callable[[], Dict[str, Any]]] = None,
        setup_summary: Optional[Callable[[], Dict[str, Any]]] = None,
        system_snapshot: Optional[Callable[[], Dict[str, Any]]] = None,
        scanner_library: Optional[Any] = None,
        alert_log: Optional[Any] = None,
        share_manager: Optional[Any] = None,
        test_alert_provider: Optional[Callable[[Optional[str]], Any]] = None,
        sample_alert_provider: Optional[Callable[[Optional[str]], Any]] = None,
        set_enabled_provider: Optional[Callable[[str, bool], Dict[str, Any]]] = None,
        share_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        regenerate_share_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.host = host
        self.bind = bind or host
        self.port = int(port)
        self.web_dir = Path(web_dir).expanduser().resolve()
        self.routes = Routes(
            SignalQueries(db_path),
            status_provider=status_provider,
            config_summary=config_summary,
            setup_summary=setup_summary,
            system_snapshot=system_snapshot,
            scanner_library=scanner_library,
            alert_log=alert_log,
            test_alert_provider=test_alert_provider,
            sample_alert_provider=sample_alert_provider,
            set_enabled_provider=set_enabled_provider,
            share_provider=share_provider,
            regenerate_share_provider=regenerate_share_provider,
        )
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._share_manager = share_manager

    @property
    def url(self) -> str:
        return "http://{}:{}/".format(self.host, self.port)

    def start(self) -> str:
        handler = type(
            "AstaDashboardHandler",
            (_Handler,),
            {
                "routes": self.routes,
                "web_dir": self.web_dir,
                "share_manager": self._share_manager,
            },
        )
        try:
            httpd = ThreadingHTTPServer((self.bind, self.port), handler)
        except OSError as exc:
            raise OSError(
                "cannot bind {}:{} - {}".format(self.bind, self.port, exc)
            ) from exc
        httpd.daemon_threads = True
        self._httpd = httpd
        self.port = httpd.server_address[1]
        self._thread = threading.Thread(target=httpd.serve_forever, name="asta-web", daemon=True)
        self._thread.start()
        logger.info(
            "dashboard listening",
            extra={"url": self.url, "bind": self.bind, "web_dir": str(self.web_dir)},
        )
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
