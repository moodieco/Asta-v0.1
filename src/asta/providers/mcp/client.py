"""Streamable-HTTP MCP client: JSON-RPC 2.0 with SSE or JSON responses.

Only what ASTA needs: ``initialize`` handshake (session id), ``tools/list`` and
``tools/call``. Tool payloads come back either as ``structuredContent`` or as a
JSON string inside ``content[].text``; both are normalised to a dict.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from asta.utils.exceptions import ProviderError
from asta.utils.logger import get_logger


class MCPError(ProviderError):
    """MCP transport or tool error."""


class MCPClient:
    def __init__(
        self,
        url: str,
        token: str = "",
        timeout: float = 30.0,
        client: Optional[httpx.Client] = None,
    ):
        self.url = url
        self.token = token
        self.timeout = float(timeout)
        self._client = client
        self._owns_client = client is None
        self._session_id: Optional[str] = None
        self._initialized = False
        self._next_id = 0
        self.logger = get_logger("asta.mcp")

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
            self._owns_client = True
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
        self._client = None
        self._session_id = None
        self._initialized = False

    # -- transport --------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.token:
            headers["Authorization"] = "Bearer {}".format(self.token)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _decode_response(response: httpx.Response) -> Dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        text = response.text
        if "text/event-stream" in content_type:
            chunks: List[str] = []
            for line in text.splitlines():
                if line.startswith("data:"):
                    chunks.append(line[5:].strip())
            text = "".join(chunks)
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise MCPError("invalid MCP response: {}".format(text[:200])) from exc

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.post(self.url, json=payload, headers=self._headers())
        if response.status_code >= 400:
            raise MCPError(
                "MCP HTTP {} on {}".format(response.status_code, self.url),
                body=response.text[:300],
            )
        session = response.headers.get("mcp-session-id")
        if session:
            self._session_id = session
        return self._decode_response(response)

    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            payload["params"] = params
        data = self._post(payload)
        if "error" in data:
            raise MCPError(
                "MCP error on {}: {}".format(method, data["error"]),
            )
        return data.get("result", {})

    def _notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._post(payload)

    # -- protocol ---------------------------------------------------------
    def initialize(self) -> Dict[str, Any]:
        if self._initialized:
            return {"already": True}
        result = self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "asta", "version": "0.1"},
            },
        )
        self._initialized = True
        try:
            self._notify("notifications/initialized")
        except MCPError:
            pass
        return result

    def tools_list(self) -> List[Dict[str, Any]]:
        self.initialize()
        return self._request("tools/list", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.initialize()
        result = self._request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )
        if result.get("isError"):
            raise MCPError("tool {} returned an error".format(name), result=result)
        return self.decode_tool_result(result)

    @staticmethod
    def decode_tool_result(result: Dict[str, Any]) -> Dict[str, Any]:
        structured = result.get("structuredContent")
        if isinstance(structured, dict) and structured:
            return structured
        texts = [
            item.get("text", "")
            for item in result.get("content", [])
            if item.get("type") == "text"
        ]
        for text in reversed(texts):
            text = text.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}
        return {"text": "\n".join(texts)}
