"""End-to-end: config -> discovery -> provider -> scanners -> pipeline -> dry-run alerts."""

from typing import List

from asta.app import AstaApp
from asta.core.signal_model import Candle, Market
from asta.providers.base import MarketDataProvider
from tests.helpers import bullish_divergence_closes, make_candles, make_context

CONFIG = """
log_level: ERROR
dry_run: true
storage:
  signal_history_path: {history}
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


def test_app_runs_a_full_cycle_and_persists_signals(tmp_path):
    history_path = tmp_path / "signals.jsonl"
    config_path = tmp_path / "config" / "asta.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(CONFIG.format(history=str(history_path)))

    provider = StubCryptoProvider()
    app = AstaApp.from_config(str(config_path), providers={Market.CRYPTO: provider})
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
    assert health["signal_history"]["records"] >= 1
    assert "crypto" in health["providers"]

    inventory = app.scanner_inventory()
    assert len(inventory) == 7
    assert {item["market"] for item in inventory} == {"forex", "crypto", "stock"}
    app.close()


def test_app_cycle_is_deduplicated_on_second_run(tmp_path):
    history_path = tmp_path / "signals.jsonl"
    config_path = tmp_path / "config" / "asta.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(CONFIG.format(history=str(history_path)))

    app = AstaApp.from_config(str(config_path), providers={Market.CRYPTO: StubCryptoProvider()})
    app.build()
    first = app.run_once()
    second = app.run_once()

    assert first.signals_accepted >= 1
    assert second.signals_accepted == 0
    assert second.signals_rejected >= 1
    assert second.signals_delivered == 0
    app.close()
