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
from asta.web.scanner_library import ScannerLibrary
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


def test_setup_and_system_endpoints_are_optional(db_path: Path) -> None:
    """Without providers the endpoints answer 200 with a clear 'unavailable' flag."""
    routes = Routes(SignalQueries(db_path))
    assert routes.dispatch("/api/setup") == (200, {"available": False})
    assert routes.dispatch("/api/system") == (200, {"available": False})


def test_setup_and_system_endpoints_forward_the_providers(db_path: Path) -> None:
    """The dashboard must never receive a raw secret from /api/setup."""
    setup_payload = {
        "available": True,
        "complete": True,
        "webhooks": {"crypto": {"env": "DISCORD_WEBHOOK_CRYPTO", "configured": True, "masked": "••••••••abcd"}},
    }
    system_payload = {"available": True, "cpuPct": 1.5, "database": {"sizeBytes": 1024}}
    routes = Routes(
        SignalQueries(db_path),
        setup_summary=lambda: setup_payload,
        system_snapshot=lambda: system_payload,
    )

    status, payload = routes.dispatch("/api/setup")
    assert status == 200 and payload["complete"] is True
    masked = payload["webhooks"]["crypto"]["masked"]
    assert masked.startswith("•") and "discord.com/api/webhooks" not in json.dumps(payload)

    status, payload = routes.dispatch("/api/system")
    assert status == 200 and payload["cpuPct"] == 1.5


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


SOURCE = (
    "from asta.core.scanner_base import ScannerBase\n"
    "from asta.core.scanner_registry import register_scanner\n"
    "from asta.core.signal_model import Market\n\n"
    "@register_scanner\n"
    "class Demo(ScannerBase):\n"
    "    id = 'CXS099_DEMO'\n"
    "    name = 'Demo'\n"
    "    market = Market.CRYPTO\n"
    "    def evaluate(self, context):\n"
    "        return []\n"
)


def test_write_endpoints_install_uninstall_restore(db_path: Path, tmp_path: Path) -> None:
    library = ScannerLibrary(tmp_path / "scanners")
    routes = Routes(SignalQueries(db_path), scanner_library=library)

    status, payload = routes.dispatch(
        "/api/scanners/install",
        method="POST",
        body={"name": "Demo", "market": "crypto", "version": "0.1.0", "source": SOURCE, "sourceName": "scanner.py"},
    )
    assert status == 200 and payload["installed"] is True
    scanner_id = payload["record"]["scannerId"]

    status, payload = routes.dispatch("/api/scanners/library")
    assert status == 200 and payload["available"] is True
    assert payload["installed"][0]["scannerId"] == scanner_id
    assert payload["trash"] == []

    status, payload = routes.dispatch("/api/scanners/{}/uninstall".format(scanner_id), method="POST", body={})
    assert status == 200 and payload["uninstalled"] is True

    status, payload = routes.dispatch("/api/scanners/library")
    assert payload["trash"][0]["scannerId"] == scanner_id

    status, payload = routes.dispatch("/api/scanners/{}/restore".format(scanner_id), method="POST", body={})
    assert status == 200 and payload["restored"] is True


def test_write_endpoints_reject_bad_payload(db_path: Path, tmp_path: Path) -> None:
    library = ScannerLibrary(tmp_path / "scanners")
    routes = Routes(SignalQueries(db_path), scanner_library=library)
    status, payload = routes.dispatch(
        "/api/scanners/install", method="POST", body={"name": "X", "market": "crypto", "version": "no", "source": ""}
    )
    assert status == 400
    assert "error" in payload


def test_viewer_access_is_read_only(db_path: Path, tmp_path: Path) -> None:
    library = ScannerLibrary(tmp_path / "scanners")
    routes = Routes(SignalQueries(db_path), scanner_library=library)
    status, payload = routes.dispatch(
        "/api/scanners/install",
        method="POST",
        body={"name": "X", "market": "crypto", "version": "0.1.0", "source": SOURCE, "sourceName": "scanner.py"},
        access="viewer",
    )
    assert status == 403
    assert "view-only" in payload["error"]

    # reads still work for a viewer
    status, payload = routes.dispatch("/api/meta", access="viewer")
    assert status == 200


def test_optional_write_providers_answer_unavailable(db_path: Path) -> None:
    routes = Routes(SignalQueries(db_path))
    assert routes.dispatch("/api/scanners/library") == (200, {"available": False, "installed": [], "trash": [], "history": []})
    assert routes.dispatch("/api/share") == (200, {"enabled": False})
    status, payload = routes.dispatch("/api/scanners/install", method="POST", body={})
    assert status == 503
