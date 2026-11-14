import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

from asta.providers.mcp import MCPClient, MCPError


class StubMCP(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        return

    def _send(self, body, content_type="application/json", session=None):
        payload = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        if session:
            self.send_header("Mcp-Session-Id", session)
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode() or "{}")
        method = payload.get("method")
        StubMCP.requests.append((method, self.headers.get("Mcp-Session-Id")))

        if method == "initialize":
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"protocolVersion": "2025-06-18", "serverInfo": {"name": "stub"}},
                }
            )
            self._send(body, session="session-1")
        elif method == "notifications/initialized":
            self._send("")
        elif method == "tools/list":
            self._send(
                json.dumps(
                    {"jsonrpc": "2.0", "id": payload["id"], "result": {"tools": [{"name": "ping"}]}}
                )
            )
        elif method == "tools/call":
            name = payload["params"]["name"]
            if name == "boom":
                self._send(
                    json.dumps(
                        {"jsonrpc": "2.0", "id": payload["id"], "error": {"message": "no such tool"}}
                    )
                )
                return
            # SSE frame with a JSON-RPC envelope split over several data lines
            text = json.dumps({"ok": True, "symbol": "EURUSD", "history": []})
            envelope = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"content": [{"type": "text", "text": text}]},
                }
            )
            body = (
                "event: message\ndata: "
                + envelope[:40]
                + "\ndata: "
                + envelope[40:]
                + "\n\n"
            )
            self._send(body, content_type="text/event-stream")
        else:
            self._send("{}")


@pytest.fixture
def stub():
    StubMCP.requests = []
    server = HTTPServer(("127.0.0.1", 0), StubMCP)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:{}/mcp".format(server.server_port)
    server.shutdown()
    server.server_close()


def test_initialize_keeps_session_and_sends_bearer(stub):
    client = MCPClient(stub, token="tok-1", client=httpx.Client(timeout=5))
    client.initialize()
    assert client._session_id == "session-1"
    assert StubMCP.requests[0][0] == "initialize"
    assert any(method == "notifications/initialized" for method, _ in StubMCP.requests)


def test_call_tool_decodes_sse_and_json(stub):
    client = MCPClient(stub, token="tok-1", client=httpx.Client(timeout=5))
    payload = client.call_tool("marketdata_symbol_history", {"symbol": "EURUSD"})
    assert payload["ok"] is True
    assert payload["symbol"] == "EURUSD"


def test_tool_error_raises(stub):
    client = MCPClient(stub, token="tok-1", client=httpx.Client(timeout=5))
    with pytest.raises(MCPError):
        client.call_tool("boom", {})


def test_http_error_raises():
    transport = httpx.MockTransport(lambda request: httpx.Response(503, text="down"))
    client = MCPClient("http://stub/mcp", client=httpx.Client(transport=transport))
    with pytest.raises(MCPError):
        client.initialize()


def test_decode_structured_content():
    result = {
        "structuredContent": {"symbols": [{"ticker": "EURUSD"}]},
        "content": [{"type": "text", "text": "ignored"}],
    }
    assert MCPClient.decode_tool_result(result) == {"symbols": [{"ticker": "EURUSD"}]}
