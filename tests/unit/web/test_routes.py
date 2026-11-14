"""Dashboard API: queries + routing, exercised without a browser."""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from pathlib import Path

import pytest

from asta.storage.database import Database
from asta.web.queries import SignalQueries
from asta.web.routes import Routes
from asta.web.server import DashboardServer

ROWS = [
    ("s1", "CXS001_RSI_DIVERGENCE", "RSI Divergence", "crypto", "BTCUSDT", "1h", "long",
     0.81, 100.0, 98.0, 104.0, 2.0, "2026-01-01T00:00:00Z", "hit_tp", 2.0, 5, "2026-01-01T08:00:00Z"),
    ("s2", "CXS001_RSI_DIVERGENCE", "RSI Divergence", "crypto", "ETHUSDT", "1h", "short",
     0.62, 50.0, 52.0, 46.0, 2.0, "2026-01-02T00:00:00Z", "hit_sl", -1.0, 3, "2026-01-02T05:00:00Z"),
    ("s3", "STS001_EMA_TREND", "EMA Trend", "stock", "AAPL", "1d", "long",
     0.55, 190.0, 185.0, 200.0, 2.0, "2026-01-03T00:00:00Z", "open", None, None, None),
]


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "asta.db"
    Database(path)
    connection = sqlite3.connect(str(path))
    connection.executemany(
        """
        INSERT INTO signals (signal_id, scanner_id, scanner_name, market, symbol, timeframe,
                             signal_type, confidence, price, stop_loss, take_profit, risk_reward,
                             created_at, status, realized_r, bars_held, closed_at, reason, recorded_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'test reason', '2026-01-01T00:00:00Z')
        """,
        ROWS,
    )
    connection.commit()
    connection.close()
    return path


def test_meta_matches_the_rows(db_path: Path) -> None:
    meta = SignalQueries(db_path).meta()
    assert meta["total"] == 3
    assert meta["closed"] == 2
    assert meta["open"] == 1
    assert meta["wins"] == 1
    assert meta["losses"] == 1
    assert meta["winRate"] == pytest.approx(50.0)
    assert meta["netR"] == pytest.approx(1.0)
    assert meta["expectancyR"] == pytest.approx(0.5)
    assert meta["profitFactor"] == pytest.approx(2.0)


def test_filters_and_pagination(db_path: Path) -> None:
    queries = SignalQueries(db_path)
    rows, total = queries.list_signals(status="hit_sl")
    assert total == 1
    assert rows[0]["symbol"] == "ETHUSDT"
    assert rows[0]["side"] == "short"

    rows, total = queries.list_signals(market="crypto", sort="best")
    assert total == 2
    assert [r["realizedR"] for r in rows] == [2.0, -1.0]

    rows, total = queries.list_signals(query="aapl")
    assert total == 1
    assert rows[0]["market"] == "stock"

    page, total = queries.list_signals(limit=1, offset=1, sort="oldest")
    assert total == 3
    assert len(page) == 1
    assert page[0]["signalId"] == "s2"


def test_facets(db_path: Path) -> None:
    facets = SignalQueries(db_path).facets()
    assert facets["scanners"] == ["EMA Trend", "RSI Divergence"]
    assert facets["markets"] == ["crypto", "stock"]
    assert facets["timeframes"] == ["1d", "1h"]


def test_routes_dispatch(db_path: Path) -> None:
    routes = Routes(SignalQueries(db_path))
    status, payload = routes.dispatch("/api/health")
    assert status == 200 and payload["status"] == "ok"

    status, payload = routes.dispatch("/api/signals", "status=open")
    assert status == 200 and payload["total"] == 1 and payload["signals"][0]["symbol"] == "AAPL"
    assert payload["hasMore"] is False

    status, payload = routes.dispatch("/api/signals/s2")
    assert status == 200 and payload["symbol"] == "ETHUSDT"

    status, payload = routes.dispatch("/api/signals/999")
    assert status == 404
    assert payload["error"] == "signal not found"

    status, payload = routes.dispatch("/api/nope")
    assert status == 404


def test_server_serves_spa_and_api(db_path: Path, tmp_path: Path) -> None:
    web_dir = tmp_path / "dist"
    (web_dir / "assets").mkdir(parents=True)
    (web_dir / "index.html").write_text("<!doctype html><div id='root'></div>", encoding="utf-8")
    (web_dir / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")

    server = DashboardServer(db_path=db_path, web_dir=web_dir, host="127.0.0.1", port=0)
    url = server.start()
    try:
        with urllib.request.urlopen(url + "api/meta", timeout=5) as response:
            assert json.loads(response.read())["total"] == 3
        with urllib.request.urlopen(url + "assets/app.js", timeout=5) as response:
            assert "console.log" in response.read().decode()
        with urllib.request.urlopen(url + "some/spa/route", timeout=5) as response:
            assert "id='root'" in response.read().decode()
    finally:
        server.stop()
