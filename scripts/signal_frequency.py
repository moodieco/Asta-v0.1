"""Signal frequency report: replay historical candles through every scanner.

Answers the practical question "if I run ASTA for a week, will anything show up in
Discord?" without placing trades or needing a PnL model.

    PYTHONPATH=src python scripts/signal_frequency.py --market crypto --days 30
    PYTHONPATH=src python scripts/signal_frequency.py --market stock

For each scanner/symbol it slides a candle window over history and counts:
  raw detections, deduplicated alerts (same key inside the dedup window counts once),
  alerts per day, mean confidence, and the last alert timestamp.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.config import load_config  # noqa: E402
from asta.core.scanner_base import ScannerBase  # noqa: E402
from asta.core.scanner_registry import ScannerRegistry  # noqa: E402
from asta.core.signal_model import Candle, Market, ScanContext, Signal  # noqa: E402
from asta.providers import build_providers  # noqa: E402
from asta.utils.exceptions import AstaError  # noqa: E402
from asta.utils.logger import configure_logging  # noqa: E402
from asta.utils.time_utils import timeframe_to_seconds  # noqa: E402


@dataclass
class ScannerStats:
    scanner_id: str
    symbol: str
    timeframe: str
    raw: int = 0
    alerts: int = 0
    confidences: List[float] = field(default_factory=list)
    first: Optional[datetime] = None
    last: Optional[datetime] = None
    span_days: float = 0.0

    @property
    def per_day(self) -> float:
        return self.alerts / self.span_days if self.span_days else 0.0

    @property
    def mean_confidence(self) -> float:
        return sum(self.confidences) / len(self.confidences) if self.confidences else 0.0

    @property
    def avg_gap_hours(self) -> float:
        return (self.span_days * 24 / self.alerts) if self.alerts else 0.0


def replay(
    candles: List[Candle],
    scanner: ScannerBase,
    symbol: str,
    dedup_seconds: int,
) -> ScannerStats:
    stats = ScannerStats(
        scanner_id=scanner.id,
        symbol=symbol,
        timeframe=scanner.timeframe,
        span_days=(candles[-1].timestamp - candles[0].timestamp).total_seconds() / 86400,
    )
    window = max(scanner.min_candles, 120)
    if len(candles) <= window:
        return stats

    dedup_window = min(dedup_seconds, max(timeframe_to_seconds(scanner.timeframe) * 2, 60))
    last_seen: Dict[str, datetime] = {}

    for index in range(window - 1, len(candles)):
        context = ScanContext(
            market=scanner.market,
            symbol=symbol,
            timeframe=scanner.timeframe,
            candles=candles[index - window + 1 : index + 1],
            scanner_id=scanner.id,
            now=candles[index].timestamp,
        )
        try:
            signals: List[Signal] = scanner.scan(context)
        except AstaError:
            continue
        for signal in signals:
            stats.raw += 1
            key = signal.dedup_key
            previous = last_seen.get(key)
            if previous is not None:
                elapsed = (signal.timestamp - previous).total_seconds()
                if elapsed < dedup_window:
                    continue
            last_seen[key] = signal.timestamp
            stats.alerts += 1
            stats.confidences.append(signal.confidence)
            stats.first = stats.first or signal.timestamp
            stats.last = signal.timestamp
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Historical signal frequency per scanner")
    parser.add_argument("--config", default=None)
    parser.add_argument("--market", default="crypto", choices=["crypto", "forex", "stock"])
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit", type=int, default=1000, help="candles to replay")
    parser.add_argument("--dedup-window", type=int, default=3600)
    args = parser.parse_args()

    configure_logging("WARNING")
    config = load_config(args.config)
    market = Market(args.market)
    provider = build_providers(config.providers)[market]
    if not provider.is_configured():
        print("{} provider not configured".format(market.value))
        return 2

    registry = ScannerRegistry()
    registry.discover()
    scanners = [
        scanner
        for scanner in registry.build_all(registry.load_configs(), config.scanner_overrides)
        if scanner.market is market
    ]
    if not scanners:
        print("no scanners for {}".format(market.value))
        return 2

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        settings = config.markets.get(market.value)
        symbols = list(settings.symbols) if settings else []

    rows: List[ScannerStats] = []
    for symbol in symbols:
        for timeframe in sorted({scanner.timeframe for scanner in scanners}):
            try:
                candles = provider.fetch_candles(symbol, timeframe, args.limit)
            except AstaError as exc:
                print("  {} {} skipped: {}".format(symbol, timeframe, exc))
                continue
            for scanner in scanners:
                if scanner.timeframe != timeframe:
                    continue
                rows.append(replay(candles, scanner, symbol, args.dedup_window))

    span = max((row.span_days for row in rows), default=0.0)
    print("\nhistorical replay · {} · {} symbols · {:.1f} days".format(
        market.value, len(symbols), span))
    print(
        "\n{:<26} {:<10} {:>4} {:>8} {:>7} {:>10} {:>7}".format(
            "scanner", "symbol", "tf", "raw", "alerts", "alerts/day", "avg conf"
        )
    )
    for row in sorted(rows, key=lambda r: (r.scanner_id, r.symbol)):
        print(
            "{:<26} {:<10} {:>4} {:>8} {:>7} {:>10.2f} {:>7.0%}".format(
                row.scanner_id,
                row.symbol,
                row.timeframe,
                row.raw,
                row.alerts,
                row.per_day,
                row.mean_confidence,
            )
        )

    totals: Dict[str, ScannerStats] = {}
    per_day: Dict[str, float] = {}
    for row in rows:
        aggregate = totals.setdefault(
            row.scanner_id,
            ScannerStats(row.scanner_id, "*", row.timeframe, span_days=row.span_days),
        )
        aggregate.raw += row.raw
        aggregate.alerts += row.alerts
        aggregate.confidences.extend(row.confidences)
        # symbols/timeframes have different history spans: sum the rates, not the counts
        per_day[row.scanner_id] = per_day.get(row.scanner_id, 0.0) + row.per_day

    print("\nper scanner (all symbols)")
    print("{:<26} {:>8} {:>7} {:>10} {:>12}".format("scanner", "raw", "alerts", "alerts/day", "avg gap"))
    for scanner_id, aggregate in sorted(totals.items()):
        rate = per_day.get(scanner_id, 0.0)
        gap = "{:.1f}h".format(24 / rate) if rate else "-"
        print(
            "{:<26} {:>8} {:>7} {:>10.2f} {:>12}".format(
                scanner_id, aggregate.raw, aggregate.alerts, rate, gap
            )
        )

    silent = [scanner_id for scanner_id, aggregate in totals.items() if aggregate.alerts == 0]
    if silent:
        print("\nsilent in this window (thresholds too strict or no such setup):")
        for scanner_id in silent:
            print("  - {}".format(scanner_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
