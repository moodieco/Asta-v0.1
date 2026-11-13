"""Diagnostic view of what ASTA actually reads from a market.

    python scripts/inspect_market.py --market crypto --symbols BTCUSDT,ETHUSDT
    python scripts/inspect_market.py --market stock --timeframes 1d

Prints, per symbol and timeframe: the raw candle window, the indicator values
the scanners use, market structure levels, and the verdict of every scanner
(including why a scanner stayed quiet).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.config import load_config
from asta.core.indicators import (
    atr,
    ema,
    find_divergence,
    rsi_series,
    volume_ratio,
)
from asta.core.scanner_registry import ScannerRegistry
from asta.core.signal_model import Market, ScanContext
from asta.providers import build_providers
from asta.utils.exceptions import AstaError
from asta.utils.logger import configure_logging
from asta.utils.time_utils import human_age, isoformat, timeframe_to_seconds, utcnow


def fmt(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if abs(value) >= 1000:
        return "{:,.{}f}".format(value, digits)
    return "{:.{}f}".format(value, digits)


def pct(value: Optional[float]) -> str:
    return "n/a" if value is None else "{:+.2f}%".format(value)


def inspect(provider, scanner_list, symbol: str, timeframe: str, limit: int = 160) -> None:
    print("\n=== {} · {} ===".format(provider.market.value.upper(), symbol, ))
    try:
        raw = provider.fetch_candles(symbol, timeframe, limit)
    except AstaError as exc:
        print("  provider error:", exc)
        return
    if not raw:
        print("  no candles returned")
        return

    seconds = timeframe_to_seconds(timeframe)
    now = utcnow()
    age = (now - raw[-1].timestamp).total_seconds()
    print(
        "  candles: {} closed | window {} -> {} | last candle age {}".format(
            len(raw),
            isoformat(raw[0].timestamp),
            isoformat(raw[-1].timestamp),
            human_age(raw[-1].timestamp, now),
        )
    )
    if age < seconds * 0.5:
        print("  note: last bar closed recently, the forming bar was dropped")

    last = raw[-1]
    change = (last.close - raw[-2].close) / raw[-2].close * 100 if len(raw) > 1 else 0.0
    print(
        "  last OHLCV: O {} H {} L {} C {} V {} ({})".format(
            fmt(last.open), fmt(last.high), fmt(last.low), fmt(last.close), fmt(last.volume, 2), pct(change)
        )
    )

    closes = [c.close for c in raw]
    rsi_values = rsi_series(closes, 14)
    rsi_now = rsi_values[-1]
    atr_now = atr(raw, 14)
    ema20, ema50, ema200 = ema(closes, 20), ema(closes, 50), ema(closes, 200)
    print(
        "  trend: RSI14 {} | EMA20 {} | EMA50 {} | EMA200 {}".format(
            fmt(rsi_now, 1), fmt(ema20), fmt(ema50), fmt(ema200)
        )
    )
    print(
        "  volatility: ATR14 {} ({}) | volume {}x SMA20".format(
            fmt(atr_now),
            pct(atr_now / last.close * 100 if atr_now and last.close else None),
            fmt(volume_ratio(closes and [c.volume for c in raw], 20), 2),
        )
    )

    lookback = 30
    window = raw[-lookback - 1 : -1] if len(raw) > lookback else raw[:-1]
    if window:
        high = max(c.high for c in window)
        low = min(c.low for c in window)
        print(
            "  structure: {}-bar high {} ({}) | {}-bar low {} ({})".format(
                lookback, fmt(high), pct((last.close - high) / high * 100),
                lookback, fmt(low), pct((last.close - low) / low * 100),
            )
        )

    divergence = find_divergence(closes, rsi_values, span=2)
    print("  RSI divergence: {}".format("none" if divergence is None else divergence.direction))

    context = ScanContext(
        market=provider.market, symbol=symbol, timeframe=timeframe, candles=raw
    )
    verdicts: List[str] = []
    for scanner in scanner_list:
        if scanner.market is not provider.market or scanner.timeframe != timeframe:
            continue
        try:
            signals = scanner.scan(context)
        except AstaError as exc:
            verdicts.append("  - {}: skipped ({})".format(scanner.id, exc))
            continue
        if signals:
            for signal in signals:
                verdicts.append(
                    "  + {}: {} @ {:.0%} — {}".format(
                        scanner.id, signal.signal_type.value.upper(), signal.confidence, signal.reason
                    )
                )
        else:
            verdicts.append("  - {}: no setup".format(scanner.id))
    print("  scanner verdicts:")
    for line in verdicts or ["  (no scanner covers this market/timeframe)"]:
        print(line)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect market data + scanner verdicts")
    parser.add_argument("--config", default=None)
    parser.add_argument("--market", default="crypto", choices=["crypto", "forex", "stock"])
    parser.add_argument("--symbols", default="")
    parser.add_argument("--timeframes", default="")
    parser.add_argument("--limit", type=int, default=160)
    args = parser.parse_args(argv)

    configure_logging("WARNING")
    config = load_config(args.config)
    market = Market(args.market)
    providers = build_providers(config.providers)
    provider = providers[market]
    if not provider.is_configured():
        print("{} provider is not configured (missing credentials)".format(market.value))
        return 2

    registry = ScannerRegistry()
    registry.discover()
    scanners = registry.build_all(registry.load_configs(), config.scanner_overrides)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        market_settings = config.markets.get(market.value)
        symbols = list(market_settings.symbols) if market_settings else []
    timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    if not timeframes:
        timeframes = sorted({scanner.timeframe for scanner in scanners if scanner.market is market})

    for symbol in symbols[:10]:
        for timeframe in timeframes:
            inspect(provider, scanners, symbol, timeframe, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
