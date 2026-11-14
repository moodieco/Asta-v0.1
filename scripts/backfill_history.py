"""Backfill signal history by replaying real market data.

    # preview: how many signals would be written
    PYTHONPATH=src python scripts/backfill_history.py --market crypto --days 90

    # write them into SQLite
    PYTHONPATH=src python scripts/backfill_history.py --market crypto --days 90 --commit
    PYTHONPATH=src python scripts/backfill_history.py --market stock --days 730 --commit

Signals are tagged ``source=backfill`` so they never look like live alerts.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.config import load_config  # noqa: E402
from asta.core.scanner_base import ScannerBase  # noqa: E402
from asta.core.scanner_registry import ScannerRegistry  # noqa: E402
from asta.core.signal_model import Market  # noqa: E402
from asta.core.signal_validator import SignalValidator  # noqa: E402
from asta.providers import build_providers  # noqa: E402
from asta.services.backtest_service import ReplayStats, backfill_scanner, replay_scanner  # noqa: E402
from asta.storage.database import Database  # noqa: E402
from asta.storage.repositories.signal_repository import SignalRepository  # noqa: E402
from asta.utils.logger import configure_logging  # noqa: E402


def fetch_history(provider, symbol: str, timeframe: str, days: int):
    if hasattr(provider, "fetch_history"):
        return provider.fetch_history(symbol, timeframe, days)
    return provider.fetch_candles(symbol, timeframe, 1000)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill signal history from market data")
    parser.add_argument("--config", default=None)
    parser.add_argument("--market", default="crypto", choices=["crypto", "stock", "forex"])
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--symbols", default="")
    parser.add_argument("--scanners", default="")
    parser.add_argument(
        "--commit", action="store_true", help="write to SQLite (default is a dry run)"
    )
    args = parser.parse_args()

    configure_logging("INFO" if args.commit else "WARNING")
    config = load_config(args.config)
    market = Market(args.market)
    provider = build_providers(config.providers)[market]
    if not provider.is_configured():
        print("{} provider not configured".format(market.value))
        return 2

    registry = ScannerRegistry()
    registry.discover()
    scanners: List[ScannerBase] = [
        scanner
        for scanner in registry.build_all(registry.load_configs(), config.scanner_overrides)
        if scanner.market is market
    ]
    if args.scanners:
        wanted = {item.strip().upper() for item in args.scanners.split(",") if item.strip()}
        scanners = [scanner for scanner in scanners if scanner.id in wanted]
    if not scanners:
        print("no scanners selected for {}".format(market.value))
        return 2

    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    if not symbols:
        settings = config.markets.get(market.value)
        symbols = list(settings.symbols) if settings else []

    repository = SignalRepository(
        Database(config.resolve_path(config.storage.sqlite_path))
    )
    validator = SignalValidator(
        min_confidence=config.validator.min_confidence,
        require_levels=config.validator.require_levels,
    )

    candle_cache: Dict[tuple, object] = {}
    rows: List[ReplayStats] = []
    started = time.perf_counter()
    for symbol in symbols:
        for timeframe in sorted({scanner.timeframe for scanner in scanners}):
            key = (symbol, timeframe)
            if key not in candle_cache:
                try:
                    candle_cache[key] = fetch_history(provider, symbol, timeframe, args.days)
                except Exception as exc:  # noqa: BLE001 - report and continue
                    print("  {} {} failed: {}".format(symbol, timeframe, exc))
                    candle_cache[key] = []
            candles = candle_cache[key]
            if not candles:
                continue
            print("  {} {}: {} candles".format(symbol, timeframe, len(candles)))
            for scanner in scanners:
                if scanner.timeframe != timeframe:
                    continue
                if args.commit:
                    rows.append(
                        backfill_scanner(
                            scanner, symbol, candles, repository, validator, source="backfill"
                        )
                    )
                else:
                    signals = replay_scanner(scanner, symbol, candles, validator, "backfill")
                    stats = ReplayStats(
                        scanner_id=scanner.id,
                        symbol=symbol,
                        timeframe=timeframe,
                        candles=len(candles),
                        raw=len(signals),
                    )
                    rows.append(stats)

    print(
        "\n{:<26} {:<10} {:>5} {:>8} {:>7} {:>9}".format(
            "scanner", "symbol", "tf", "candles", "signals", "saved"
        )
    )
    for row in rows:
        print(
            "{:<26} {:<10} {:>5} {:>8} {:>7} {:>9}".format(
                row.scanner_id,
                row.symbol,
                row.timeframe,
                row.candles,
                row.raw,
                row.saved,
            )
        )

    outcomes = {}
    for row in rows:
        for status, count in row.outcomes.items():
            outcomes[status] = outcomes.get(status, 0) + count

    summary = {
        "market": market.value,
        "days": args.days,
        "symbols": symbols,
        "committed": bool(args.commit),
        "signals_found": sum(row.raw for row in rows),
        "signals_saved": sum(row.saved for row in rows),
        "signals_rejected": sum(row.rejected for row in rows),
        "outcomes": outcomes,
        "status_breakdown": repository.outcome_stats(),
        "duration_seconds": round(time.perf_counter() - started, 2),
        "history_rows": repository.count(),
    }
    print("\n" + json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
