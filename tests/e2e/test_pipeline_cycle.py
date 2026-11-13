"""End-to-end: config files -> discovery -> provider -> services -> storage."""

from typing import List

from asta.bootstrap import AstaApp
from asta.core.signal_model import Candle, Market
from asta.providers.base import MarketDataProvider
from tests.fixtures.market_data import bullish_divergence_closes, make_candles

APP = """
dry_run: true
storage:
  backend: jsonl
  signal_history_path: {history}
  sqlite_path: {sqlite}
logging:
  level: ERROR
  format: text
  file: null
markets:
  crypto:
    enabled: true
    symbols: [BTCUSDT]
  forex:
    enabled: false
    symbols: []
  stock:
    enabled: false
    symbols: []
"""

MARKETS = """
markets:
  crypto:
    enabled: true
    symbols: [BTCUSDT]
  forex:
    enabled: false
    symbols: []
  stock:
    enabled: false
    symbols: []
scanner_overrides:
  CXS002_VOLUME_SPIKE:
    enabled: false
  CXS003_BREAKOUT_TREND:
    enabled: false
"""

CONFIG = """
{}"""


class StubCryptoProvider(MarketDataProvider):
    market = Market.CRYPTO
    name = "stub"

    def __init__(self):
        super().__init__({})
        self.calls: List[str] = []

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        self.calls.append(symbol)
        return make_candles(bullish_divergence_closes(), timeframe=timeframe)

    def health_check(self) -> bool:
        return True


def write_config(tmp_path, backend="jsonl"):
    directory = tmp_path / "config"
    directory.mkdir(parents=True, exist_ok=True)
    history = tmp_path / "history" / "signals.jsonl"
    sqlite = tmp_path / "history" / "asta.db"
    app = APP.format(history=history, sqlite=sqlite)
    if backend == "sqlite":
        app = app.replace("backend: jsonl", "backend: sqlite")
    (directory / "app.yaml").write_text(app)
    (directory / "markets.yaml").write_text(MARKETS)
    (directory / "logging.yaml").write_text("level: ERROR\nformat: text\n")
    (directory / "discord.yaml").write_text(
        "username: ASTA\nchannels:\n  crypto:\n    env: DISCORD_WEBHOOK_CRYPTO\n    label: '#cryptic'\n"
    )
    return directory, history, sqlite


def test_app_runs_a_full_cycle_and_persists_signals(tmp_path):
    directory, history_path, _ = write_config(tmp_path)
    provider = StubCryptoProvider()
    app = AstaApp.from_config(str(directory), providers={Market.CRYPTO: provider})
    app.build()

    report = app.run_once()

    assert report.scanners_run >= 1
    assert report.signals_accepted >= 1
    assert report.signals_delivered >= 1
    assert report.errors == []
    assert provider.calls == ["BTCUSDT"]
    assert history_path.exists()

    health = app.health()
    assert health["dry_run"] is True
    assert health["storage"]["backend"] == "jsonl"
    assert health["storage"]["records"] >= 1
    assert health["providers"]["crypto"] is True
    assert health["events"] >= 2

    inventory = app.scanner_inventory()
    assert len(inventory) == 8
    assert {item["market"] for item in inventory} == {"forex", "crypto", "stock"}
    app.close()


def test_app_cycle_is_deduplicated_on_second_run(tmp_path):
    directory, _, _ = write_config(tmp_path)
    app = AstaApp.from_config(
        str(directory), providers={Market.CRYPTO: StubCryptoProvider()}
    )
    app.build()
    first = app.run_once()
    second = app.run_once()

    assert first.signals_accepted >= 1
    assert second.signals_accepted == 0
    assert second.signals_rejected >= 1
    assert second.signals_delivered == 0
    app.close()


def test_app_can_persist_to_sqlite(tmp_path):
    directory, _, sqlite_path = write_config(tmp_path, backend="sqlite")
    app = AstaApp.from_config(
        str(directory), providers={Market.CRYPTO: StubCryptoProvider()}
    )
    app.build()
    app.run_once()

    health = app.health()
    assert health["storage"]["backend"] == "sqlite"
    assert health["storage"]["records"] >= 1
    assert sqlite_path.exists()
    app.close()


def test_app_test_alerts_skip_unconfigured_channels(tmp_path, monkeypatch):
    directory, _, _ = write_config(tmp_path)
    monkeypatch.setenv("DISCORD_WEBHOOK_CRYPTO", "https://discord.com/api/webhooks/1/abc")
    monkeypatch.setenv("DISCORD_WEBHOOK_FOREX", "")
    monkeypatch.setenv("DISCORD_WEBHOOK_STOCK", "")

    app = AstaApp.from_config(
        str(directory), providers={Market.CRYPTO: StubCryptoProvider()}
    )
    app.build()

    assert [item["market"] for item in app.send_test_alerts()] == ["crypto"]
    app.close()
