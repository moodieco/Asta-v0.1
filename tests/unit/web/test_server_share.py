"""Share-link auth over real HTTP: proxy detection, tokens, cookies.

The risk these cover: a tunnel (cloudflared, ngrok, Caddy) relays requests over
loopback, so ``client_address`` alone would grant editor access to the whole
internet. And a ``?token=`` URL must survive the SPA's asset requests, which the
browser issues without the query string.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from asta.storage.database import Database
from asta.web.server import TOKEN_COOKIE, DashboardServer
from asta.web.share import ShareManager

PROXY = {"X-Forwarded-For": "203.0.113.9", "X-Forwarded-Proto": "https"}


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "asta.db"
    db = Database(str(path))
    db.initialize()
    db.close()
    return path


@pytest.fixture()
def server(db_path: Path, tmp_path: Path):
    web_dir = tmp_path / "dist"
    (web_dir / "assets").mkdir(parents=True)
    (web_dir / "index.html").write_text("<!doctype html><div id='root'></div>", encoding="utf-8")
    (web_dir / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")

    share = ShareManager(tmp_path / "share.json")
    share.tokens()
    instance = DashboardServer(
        db_path=db_path,
        web_dir=web_dir,
        host="127.0.0.1",
        port=0,
        share_manager=share,
        regenerate_share_provider=share.regenerate,
    )
    instance.start()
    instance.share = share  # type: ignore[attr-defined]
    try:
        yield instance
    finally:
        instance.stop()


def fetch(url: str, headers: dict | None = None, method: str = "GET", body: dict | None = None):
    data = None
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def test_loopback_without_proxy_headers_is_editor(server) -> None:
    status, _, _ = fetch(server.url + "api/status")
    assert status == 200


def test_proxied_loopback_needs_a_token(server) -> None:
    status, _, _ = fetch(server.url + "api/status", headers=PROXY)
    assert status == 401


def test_proxy_header_alone_does_not_upgrade_to_editor(server) -> None:
    """A viewer token relayed by a tunnel must stay view-only."""
    viewer = server.share.tokens()["viewer"]  # type: ignore[attr-defined]
    status, headers, _ = fetch(server.url + "api/status?token=" + viewer, headers=PROXY)
    assert status == 200
    cookie = headers.get("Set-Cookie") or ""
    assert cookie.startswith(TOKEN_COOKIE + "=")
    assert "HttpOnly" in cookie and "Secure" in cookie


def test_token_url_sets_cookie_so_assets_load(server) -> None:
    """The SPA asks for /assets/x.js without ?token=; the cookie must carry auth."""
    viewer = server.share.tokens()["viewer"]  # type: ignore[attr-defined]

    status, headers, _ = fetch(server.url + "?token=" + viewer, headers=PROXY)
    assert status == 200
    assert "id='root'" in _.decode()
    cookie = (headers.get("Set-Cookie") or "").split(";")[0]
    assert cookie

    plain = dict(PROXY, Cookie=cookie)
    assert fetch(server.url + "assets/app.js", headers=plain)[0] == 200
    assert fetch(server.url + "assets/app.js", headers=PROXY)[0] == 401
    assert fetch(server.url + "api/status", headers=plain)[0] == 200


def test_viewer_cookie_cannot_write(server) -> None:
    viewer = server.share.tokens()["viewer"]  # type: ignore[attr-defined]
    _, headers, _ = fetch(server.url + "?token=" + viewer, headers=PROXY)
    cookie = (headers.get("Set-Cookie") or "").split(";")[0]
    status, _, _ = fetch(
        server.url + "api/share/regenerate",
        headers=dict(PROXY, Cookie=cookie),
        method="POST",
        body={},
    )
    assert status == 403


def test_funnel_request_without_token_is_denied(server) -> None:
    """Tailscale Funnel relays over loopback and adds X-Forwarded-For.

    If that header stopped being recognised, a public funnel would hand out
    editor access to anyone who opened the URL.
    """
    funnel = {"X-Forwarded-For": "100.64.0.9"}
    status, _, body = fetch(server.url + "api/access", headers=funnel)
    assert status == 401
    assert "editor" not in body.decode()


def test_healthz_is_public_for_hosting_platform_checks(server) -> None:
    """Render/Fly probe this path without a share token — it must never 401."""
    status, _, body = fetch(server.url + "healthz", headers=PROXY)
    assert status == 200 and json.loads(body) == {"ok": True}


def test_env_tokens_win_over_the_share_file(tmp_path, monkeypatch) -> None:
    """A redeploy keeps working links: tokens come from the platform env."""
    share = ShareManager(tmp_path / "share.json")
    share.tokens()
    monkeypatch.setenv("ASTA_EDITOR_TOKEN", "editor-from-env")
    monkeypatch.setenv("ASTA_VIEWER_TOKEN", "viewer-from-env")
    assert share.authenticate("editor-from-env") == "editor"
    assert share.authenticate("viewer-from-env") == "viewer"


def test_editor_cookie_can_write(server) -> None:
    editor = server.share.tokens()["editor"]  # type: ignore[attr-defined]
    _, headers, _ = fetch(server.url + "?token=" + editor, headers=PROXY)
    cookie = (headers.get("Set-Cookie") or "").split(";")[0]
    status, _, body = fetch(
        server.url + "api/share/regenerate",
        headers=dict(PROXY, Cookie=cookie),
        method="POST",
        body={},
    )
    assert status == 200 and "tokens" in json.loads(body)
