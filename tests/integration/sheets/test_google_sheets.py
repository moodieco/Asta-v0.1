"""Google Sheets writer against a stub HTTP server (no Google account needed)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote, urlparse

import httpx
import pytest

from asta.integrations.sheets.base import HEADER
from asta.integrations.sheets.google_sheets import GoogleSheetsAuth, GoogleSheetsWriter


class StubGoogle(BaseHTTPRequestHandler):
    requests = []
    header_rows = 0
    tab_titles = ["Signals"]

    def log_message(self, *args):  # silence
        return

    def _send(self, payload=None, status=200):
        body = json.dumps(payload or {}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else ""
        path = unquote(urlparse(self.path).path)
        StubGoogle.requests.append(("POST", path, body, self.headers.get("Authorization")))

        if path == "/token":
            self._send({"access_token": "tok-1", "expires_in": 3600})
        elif path.endswith(":batchUpdate"):
            payload = json.loads(body)
            title = payload["requests"][0]["addSheet"]["properties"]["title"]
            StubGoogle.tab_titles.append(title)
            self._send({"replies": [{}]})
        elif path == "/v4/spreadsheets":
            self._send({"spreadsheetId": "sheet-123", "spreadsheetUrl": "https://docs.google.com/x"})
        elif path.endswith(":append"):
            payload = json.loads(body)
            if payload["values"] == [HEADER]:
                StubGoogle.header_rows += 1
            self._send({"updates": {"updatedRows": len(payload["values"])}})
        else:
            self._send({"error": "not found"}, status=404)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        StubGoogle.requests.append(("GET", path, "", self.headers.get("Authorization")))
        if path.endswith("/values/Signals!A1"):
            values = [] if StubGoogle.header_rows == 0 else [HEADER]
            self._send({"values": values})
        elif path.startswith("/v4/spreadsheets/sheet-123"):
            self._send(
                {"sheets": [{"properties": {"title": title}} for title in StubGoogle.tab_titles]}
            )
        else:
            self._send({"error": "not found"}, status=404)


@pytest.fixture
def stub(monkeypatch):
    StubGoogle.requests = []
    StubGoogle.header_rows = 0
    StubGoogle.tab_titles = ["Signals"]
    server = HTTPServer(("127.0.0.1", 0), StubGoogle)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:{}".format(server.server_port)
    yield base
    server.shutdown()
    server.server_close()


def make_writer(tmp_path, base):
    token_path = tmp_path / "token.json"
    token_path.write_text(
        json.dumps(
            {
                "token": "stale-token",
                "refresh_token": "refresh-1",
                "client_id": "client-1",
                "client_secret": "secret-1",
                "expiry": "2000-01-01T00:00:00Z",
            }
        )
    )
    client = httpx.Client(timeout=5)
    auth = GoogleSheetsAuth(token_path, client=client, token_url=base + "/token")
    writer = GoogleSheetsWriter(
        auth,
        spreadsheet_id="",
        sheet_name="Signals",
        create_if_missing=True,
        client=client,
        base_url=base + "/v4",
    )
    return writer


def test_creates_sheet_writes_header_then_rows(tmp_path, stub):
    writer = make_writer(tmp_path, stub)
    assert writer.append_rows([["2026-11-13T20:00:00Z", "crypto"]]) == 1

    paths = [(method, path) for method, path, _, _ in StubGoogle.requests]
    assert ("POST", "/token") in paths
    assert ("POST", "/v4/spreadsheets") in paths
    assert ("GET", "/v4/spreadsheets/sheet-123/values/Signals!A1") in paths
    append_calls = [p for m, p, _, _ in StubGoogle.requests if p.endswith(":append")]
    assert append_calls[0].endswith("/values/Signals!A1:append")
    assert StubGoogle.header_rows == 1
    assert writer.spreadsheet_id == "sheet-123"

    auth_headers = [auth for _, _, _, auth in StubGoogle.requests]
    assert all(header == "Bearer tok-1" for header in auth_headers if header)


def test_second_append_does_not_rewrite_header(tmp_path, stub):
    writer = make_writer(tmp_path, stub)
    writer.append_rows([["row-1"]])
    writer.append_rows([["row-2"]])
    assert StubGoogle.header_rows == 1


def test_missing_token_file_is_actionable(tmp_path, stub):
    from asta.utils.exceptions import SheetsError

    auth = GoogleSheetsAuth(tmp_path / "nope.json", client=httpx.Client(timeout=5))
    writer = GoogleSheetsWriter(auth, spreadsheet_id="sheet-123", client=httpx.Client(timeout=5), base_url=stub + "/v4")
    with pytest.raises(SheetsError) as exc:
        writer.append_rows([["row"]])
    assert "token not found" in str(exc.value)


def test_service_account_quota_error_is_actionable():
    from asta.utils.exceptions import SheetsError

    class QuotaAuth:
        def access_token(self, force_refresh=False):
            return "tok"

        def close(self):
            pass

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            403, json={"error": {"message": "Service Accounts do not have storage quota."}}
        )
    )
    writer = GoogleSheetsWriter(
        QuotaAuth(),
        spreadsheet_id="",
        create_if_missing=True,
        client=httpx.Client(transport=transport),
        base_url="https://sheets.googleapis.com/v4",
    )
    with pytest.raises(SheetsError) as exc:
        writer.ensure_ready()
    assert "service account" in str(exc.value).lower()


def test_missing_tab_is_created(tmp_path, stub):
    StubGoogle.tab_titles = ["Sheet1"]
    token_path = tmp_path / "token.json"
    token_path.write_text(
        json.dumps(
            {
                "token": "tok-1",
                "refresh_token": "r",
                "client_id": "c",
                "client_secret": "s",
                "expiry": "2999-01-01T00:00:00Z",
            }
        )
    )
    client = httpx.Client(timeout=5)
    auth = GoogleSheetsAuth(token_path, client=client, token_url=stub + "/token")
    writer = GoogleSheetsWriter(
        auth,
        spreadsheet_id="sheet-123",
        sheet_name="Signals",
        client=client,
        base_url=stub + "/v4",
    )
    writer.ensure_ready()
    paths = [p for _, p, _, _ in StubGoogle.requests]
    assert "/v4/spreadsheets/sheet-123:batchUpdate" in paths
    assert StubGoogle.header_rows == 1
