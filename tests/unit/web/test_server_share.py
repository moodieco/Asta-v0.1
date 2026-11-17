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
from asta.web.server import SESSION_COOKIE, TOKEN_COOKIE, DashboardServer
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
    share.set_pin("viewer", "555001")
    share.set_pin("editor", "777003")
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


def test_spa_shell_is_public_but_the_api_is_not(server) -> None:
    """The login screen has to render before the visitor owns any credential.

    So the shell (index.html + assets) is public, while every /api/* call stays
    gated until a cookie, a token or loopback frees it.
    """
    status, _, body = fetch(server.url, headers=PROXY)
    assert status == 200 and "id='root'" in body.decode()
    assert fetch(server.url + "assets/app.js", headers=PROXY)[0] == 200
    assert fetch(server.url + "api/status", headers=PROXY)[0] == 401

    viewer = server.share.tokens()["viewer"]  # type: ignore[attr-defined]
    _, headers, _ = fetch(server.url + "?token=" + viewer, headers=PROXY)
    cookie = (headers.get("Set-Cookie") or "").split(";")[0]
    plain = dict(PROXY, Cookie=cookie)
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


# -- role + PIN login ------------------------------------------------------


def test_session_endpoint_is_public_and_reports_which_pins_exist(server) -> None:
    status, _, body = fetch(server.url + "api/session", headers=PROXY)
    payload = json.loads(body)
    assert status == 200
    assert payload["authenticated"] is False
    assert payload["role"] is None
    assert payload["pins"] == {"viewer": True, "editor": True}


def test_loopback_session_is_editor_without_a_pin(server) -> None:
    status, _, body = fetch(server.url + "api/session")
    payload = json.loads(body)
    assert status == 200 and payload["authenticated"] is True
    assert payload["role"] == "editor" and payload["loopback"] is True


def test_pin_login_grants_the_role_and_sets_a_secure_cookie(server) -> None:
    remote = {"X-Forwarded-For": "198.51.100.7", "X-Forwarded-Proto": "https"}
    status, headers, body = fetch(
        server.url + "api/auth", headers=remote, method="POST", body={"role": "viewer", "pin": "555001"}
    )
    assert status == 200 and json.loads(body)["role"] == "viewer"
    raw_cookie = headers.get("Set-Cookie") or ""
    assert raw_cookie.startswith(SESSION_COOKIE + "=")
    assert "HttpOnly" in raw_cookie and "Secure" in raw_cookie and "SameSite=Lax" in raw_cookie
    cookie = {"Cookie": raw_cookie.split(";")[0]}

    # the session carries the viewer role onto the API
    status, _, body = fetch(server.url + "api/access", headers=dict(remote, **cookie))
    assert status == 200 and json.loads(body)["access"] == "viewer"
    assert fetch(server.url + "api/status", headers=dict(remote, **cookie))[0] == 200

    # ... and a viewer still cannot write, nor read the editor token
    assert fetch(
        server.url + "api/share/regenerate", headers=dict(remote, **cookie), method="POST", body={}
    )[0] == 403
    status, _, body = fetch(server.url + "api/share", headers=dict(remote, **cookie))
    assert status == 200
    payload = json.loads(body)
    assert payload.get("tokens") is None and "editorToken" not in payload


def test_pin_must_match_the_role_it_was_chosen_for(server) -> None:
    remote = {"X-Forwarded-For": "198.51.100.8", "X-Forwarded-Proto": "https"}
    status, _, body = fetch(
        server.url + "api/auth", headers=remote, method="POST", body={"role": "editor", "pin": "555001"}
    )
    assert status == 401 and json.loads(body)["error"] == "invalid pin"


def test_repeated_wrong_pins_lock_the_client_out(server) -> None:
    remote = {"X-Forwarded-For": "198.51.100.9", "X-Forwarded-Proto": "https"}
    for _ in range(5):
        status, _, _ = fetch(
            server.url + "api/auth", headers=remote, method="POST", body={"role": "editor", "pin": "000000"}
        )
        assert status == 401

    status, _, body = fetch(
        server.url + "api/auth", headers=remote, method="POST", body={"role": "editor", "pin": "777003"}
    )
    assert status == 429
    assert json.loads(body)["retryAfter"] > 0


def test_unknown_role_and_missing_pin_are_rejected(server) -> None:
    remote = {"X-Forwarded-For": "198.51.100.10", "X-Forwarded-Proto": "https"}
    status, _, _ = fetch(server.url + "api/auth", headers=remote, method="POST", body={"role": "admin", "pin": "1"})
    assert status == 400

    share = server.share  # type: ignore[attr-defined]
    share.clear_pin("viewer")
    status, _, body = fetch(
        server.url + "api/auth", headers=remote, method="POST", body={"role": "viewer", "pin": "555001"}
    )
    assert status == 409 and "not configured" in json.loads(body)["error"]


def test_logout_clears_the_session_cookie(server) -> None:
    remote = {"X-Forwarded-For": "198.51.100.11", "X-Forwarded-Proto": "https"}
    _, headers, _ = fetch(
        server.url + "api/auth", headers=remote, method="POST", body={"role": "viewer", "pin": "555001"}
    )
    cookie = {"Cookie": (headers.get("Set-Cookie") or "").split(";")[0]}

    status, headers, _ = fetch(
        server.url + "api/auth/logout", headers=dict(remote, **cookie), method="POST", body={}
    )
    assert status == 200
    cleared = headers.get("Set-Cookie") or ""
    assert cleared.startswith(SESSION_COOKIE + "=") and "Max-Age=0" in cleared
    # a cleared cookie means no access again
    assert fetch(server.url + "api/status", headers=dict(remote, Cookie="asta_session="))[0] == 401
