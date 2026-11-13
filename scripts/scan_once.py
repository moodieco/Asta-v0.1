"""Offline end-to-end demo: synthetic candles -> scanners -> pipeline -> dry-run alerts.

Run with the package installed (``pip install -e .``) or via::

    PYTHONPATH=src python scripts/scan_once.py
"""

from __future__ import annotations

import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.core.deduplication import DeduplicationStore
from asta.core.market_manager import MarketManager, MarketSettings
from asta.core.scanner_manager import ScannerManager
from asta.core.scanner_registry import ScannerRegistry
from asta.core.signal_manager import SignalManager
from asta.core.signal_model import Candle, Market
from asta.core.signal_validator import SignalValidator
from asta.integrations.discord.alert_manager import AlertManager
from asta.integrations.discord.channel_config import ChannelConfig
from asta.integrations.discord.discord_router import DiscordRouter
from asta.providers.base import MarketDataProvider
from asta.storage.cache import TTLCache
from asta.utils.logger import configure_logging


class SyntheticProvider(MarketDataProvider):
    """Deterministic fake provider: every market gets a trend + pullback series."""

    health_symbol = "SYNTH"

    def __init__(self, market: Market, base_price: float = 100.0):
        super().__init__({})
        self.market = market
        self.name = "synthetic-{}".format(market.value)
        self.base_price = base_price

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        random.seed("{}:{}:{}".format(symbol, timeframe, limit))
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        step = timedelta(hours=1)
        candles: List[Candle] = []
        price = self.base_price
        for index in range(limit):
            drift = 0.15 if index < limit * 0.6 else -0.22
            noise = random.gauss(0, 0.35)
            close = price + drift + noise
            open_ = price
            high = max(open_, close) + abs(random.gauss(0, 0.3))
            low = min(open_, close) - abs(random.gauss(0, 0.3))
            volume = 1000 * (1 + abs(math.sin(index / 4.0))) * (4.5 if index == limit - 1 else 1.0)
            candles.append(
                Candle(
                    timestamp=start + step * index,
                    open=round(open_, 4),
                    high=round(high, 4),
                    low=round(low, 4),
                    close=round(close, 4),
                    volume=round(volume, 2),
                )
            )
            price = close
        return candles


def main() -> int:
    configure_logging("INFO")
    providers: Dict[Market, MarketDataProvider] = {
        Market.FOREX: SyntheticProvider(Market.FOREX, 1.08),
        Market.CRYPTO: SyntheticProvider(Market.CRYPTO, 42000.0),
        Market.STOCK: SyntheticProvider(Market.STOCK, 190.0),
    }
    markets = {
        "forex": MarketSettings(enabled=True, symbols=["EUR_USD", "GBP_USD"]),
        "crypto": MarketSettings(enabled=True, symbols=["BTCUSDT", "ETHUSDT"]),
        "stock": MarketSettings(enabled=True, symbols=["AAPL", "NVDA"]),
    }
    market_manager = MarketManager(providers, markets)
    registry = ScannerRegistry()
    registry.discover()
    scanners = registry.build_all(registry.load_configs())
    router = DiscordRouter(ChannelConfig.from_env(), dry_run=True)
    signal_manager = SignalManager(
        validator=SignalValidator(min_confidence=0.3, max_age_seconds=86400 * 365 * 50),
        deduplication=DeduplicationStore(3600, TTLCache(3600)),
        history=None,
        alert_manager=AlertManager(router, dry_run=True),
    )
    manager = ScannerManager(market_manager, signal_manager, scanners)
    report = manager.run_cycle()
    print("\nscanners discovered:", len(scanners))
    print("cycle report:", report.to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
