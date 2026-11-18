"""Offline tests for the Stockbit MCP client.

No sidecar and no Stockbit account: every test drives a stub that records the
tool calls, so the things under test are symbol normalisation, argument
filtering and the refusal paths.
"""

import pytest

from asta.providers.mcp import MCPClient, MCPError
from asta.providers.stock.stockbit import (
    CANDLES_UNSUPPORTED,
    StockbitClient,
    StockbitError,
)


class StubMCP:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []
        self.closed = False

    def call_tool(self, name, arguments=None):
        self.calls.append((name, dict(arguments or {})))
        payload = self.responses.get(name, {"ok": True})
        if isinstance(payload, Exception):
            raise payload
        return payload

    def tools_list(self):
        return [{"name": "quote"}, {"name": "status"}]

    def close(self):
        self.closed = True


def client(responses=None, settings=None):
    stub = StubMCP(responses)
    config = {"url": "http://127.0.0.1:8787/mcp", "token": "tok", **(settings or {})}
    return StockbitClient(config, client=stub), stub


# ------------------------------------------------------------------ symbols
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("bbri", "BBRI"),
        ("  BBRI ", "BBRI"),
        ("BBRI.JK", "BBRI"),
        ("bbri.jk", "BBRI"),
        ("BTC/USDT", "BTCUSDT"),
    ],
)
def test_symbol_normalisation(raw, expected):
    assert StockbitClient.normalize_symbol(raw) == expected


def test_quote_sends_the_normalised_symbol():
    stockbit, stub = client()
    stockbit.quote("bbri.jk")
    assert stub.calls == [("quote", {"symbol": "BBRI"})]


# --------------------------------------------------------------- arguments
def test_none_arguments_are_dropped():
    stockbit, stub = client()
    stockbit.news(limit=5)
    assert stub.calls == [("news", {"limit": 5})]


def test_broker_summary_forwards_filters():
    stockbit, stub = client()
    stockbit.broker_summary("bbri", period="LAST_7_DAYS", investor_type="FOREIGN")
    assert stub.calls == [
        ("broker_summary", {"symbol": "BBRI", "period": "LAST_7_DAYS", "investor_type": "FOREIGN"})
    ]


def test_broker_summary_refuses_an_unknown_period():
    stockbit, stub = client()
    with pytest.raises(StockbitError) as excinfo:
        stockbit.broker_summary("BBRI", period="1w")
    assert "LAST_7_DAYS" in str(excinfo.value)
    assert stub.calls == []


def test_broker_activity_upper_cases_the_broker_code():
    stockbit, stub = client()
    stockbit.broker_activity("yp", period="1w")
    assert stub.calls == [("broker_activity", {"broker_code": "YP", "period": "1w"})]


# ---------------------------------------------------------------- payloads
def test_daily_closes_reads_the_close_field():
    stockbit, _ = client(
        {
            "chart_series": {
                "bars": [
                    {"date": "2026-11-14", "close": 4150.0},
                    {"date": "2026-11-17", "close": 4180.0},
                ]
            }
        }
    )
    assert stockbit.daily_closes("BBRI") == [("2026-11-14", 4150.0), ("2026-11-17", 4180.0)]


def test_daily_closes_falls_back_to_value_and_skips_holes():
    stockbit, _ = client(
        {
            "chart_series": {
                "items": [
                    {"date": "2026-11-14", "value": 4150.0},
                    {"date": "2026-11-17"},
                    {"date": "2026-11-18", "close": "4200"},
                ]
            }
        }
    )
    assert stockbit.daily_closes("BBRI") == [("2026-11-14", 4150.0), ("2026-11-18", 4200.0)]


def test_chart_series_refuses_interval_style_windows():
    stockbit, stub = client()
    with pytest.raises(StockbitError) as excinfo:
        stockbit.chart_series("BBRI", "1D")
    assert "1y" in str(excinfo.value)  # names the accepted calendar windows
    assert stub.calls == []


def test_chart_series_lower_cases_the_window():
    stockbit, stub = client()
    stockbit.chart_series("BBRI", "1Y")
    assert stub.calls == [("chart_series", {"symbol": "BBRI", "timeframe": "1y"})]


# ----------------------------------------------------------------- refusal
def test_fetch_candles_refuses_instead_of_returning_flat_bars():
    stockbit, stub = client()
    with pytest.raises(StockbitError) as excinfo:
        stockbit.fetch_candles("BBRI", "1d", 200)
    assert str(excinfo.value).startswith(CANDLES_UNSUPPORTED[:40])
    assert stub.calls == []


# ------------------------------------------------------------------ errors
def test_tool_error_surfaces_as_stockbit_error():
    stockbit, _ = client({"quote": MCPError("MCP HTTP 401 on http://127.0.0.1:8787/mcp")})
    with pytest.raises(StockbitError) as excinfo:
        stockbit.quote("BBRI")
    assert "quote: MCP HTTP 401" in str(excinfo.value)


def test_tool_error_unwraps_the_sidecar_envelope():
    envelope = {
        "content": [
            {
                "type": "text",
                "text": '{"success": false, "error": "No Stockbit session stored.", "kind": "auth"}',
            }
        ],
        "isError": True,
    }
    stockbit, _ = client({"quote": MCPError("tool quote returned an error", result=envelope)})
    with pytest.raises(StockbitError) as excinfo:
        stockbit.quote("bbri")
    assert "quote: No Stockbit session stored." in str(excinfo.value)
    assert excinfo.value.context["kind"] == "auth"


def test_is_configured_requires_a_token(monkeypatch):
    # An exported STOCKBIT_MCP_TOKEN would make the empty-token case pass by
    # accident here, so the env fallback is cleared explicitly.
    monkeypatch.delenv("STOCKBIT_MCP_TOKEN", raising=False)
    monkeypatch.delenv("STOCKBIT_MCP_URL", raising=False)
    assert StockbitClient({"url": "http://x/mcp", "token": "t"}).is_configured() is True
    assert StockbitClient({"url": "http://x/mcp", "token": ""}).is_configured() is False


def test_env_supplies_the_token(monkeypatch):
    monkeypatch.setenv("STOCKBIT_MCP_TOKEN", "from-env")
    monkeypatch.delenv("STOCKBIT_MCP_URL", raising=False)
    stockbit = StockbitClient({}, client=StubMCP())
    assert stockbit.token == "from-env"
    assert stockbit.url == "http://127.0.0.1:8787/mcp"


def test_close_closes_the_underlying_mcp_client():
    stockbit, stub = client()
    stockbit.close()
    assert stub.closed is True


def test_tools_lists_the_sidecar_surface():
    stockbit, _ = client()
    assert stockbit.tools() == ["quote", "status"]


def test_default_mcp_client_is_built_from_settings():
    stockbit = StockbitClient({"url": "http://127.0.0.1:9999/mcp", "token": "tok"}, client=None)
    assert isinstance(stockbit.mcp, MCPClient)
    assert stockbit.mcp.url == "http://127.0.0.1:9999/mcp"
    stockbit.close()
