"""Replay the BPJS scanner (``STS003_IDX_LIQUIDITY``) on real IDX bars.

Synthetic candles hide real-world problems: the lunch break, halted names, the
value/volume scale in rupiah, and whether the previous close is actually inside
the window the provider returns. This probe fetches live 5m bars through the
configured stock provider and reports, per symbol, which screen rejected it.

    python scripts/probe_idx_screen.py                       # 30 liquid names
    python scripts/probe_idx_screen.py --symbols BBCA.JK,ANTM.JK
    python scripts/probe_idx_screen.py --limit 120 --now 2026-11-17T15:44

``--now`` defaults to the newest bar plus one bar, so the probe works after the
close too (the scanner's own session gate is what you are bypassing).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.config import load_config  # noqa: E402
from asta.core.scanner_base import ScannerConfig  # noqa: E402
from asta.core.signal_model import Market, ScanContext  # noqa: E402
from asta.markets.stock.scanners.STS003_IDX_LIQUIDITY.scanner import (  # noqa: E402
    IndexLiquidityScanner,
)
from asta.providers import build_providers  # noqa: E402
from asta.utils.exceptions import AstaError  # noqa: E402
from asta.utils.logger import get_logger  # noqa: E402

JKT = ZoneInfo("Asia/Jakarta")

LIQUID = [
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK",
    "ANTM.JK", "ADRO.JK", "AMMN.JK", "BRPT.JK", "CPIN.JK", "GOTO.JK",
    "ICBP.JK", "INDF.JK", "INCO.JK", "ITMG.JK", "KLBF.JK", "MDKA.JK",
    "MEDC.JK", "PGAS.JK", "PGEO.JK", "PTBA.JK", "SMGR.JK", "TPIA.JK",
    "UNTR.JK", "UNVR.JK", "BREN.JK", "CUAN.JK", "ADMR.JK", "NCKL.JK",
]


def default_now(candles) -> datetime:
    """Latest moment the scanner could evaluate: last bar + 5m, capped before 15:45."""
    last = candles[-1].timestamp.astimezone(JKT)
    stamp = last + timedelta(minutes=5)
    cap = datetime.combine(last.date(), dtime(15, 44), tzinfo=JKT)
    return min(stamp, cap)


def build_scanner(limit: int) -> IndexLiquidityScanner:
    return IndexLiquidityScanner(
        ScannerConfig(
            id="STS003_IDX_LIQUIDITY",
            name="BPJS SCANNER",
            market=Market.STOCK,
            timeframe="5m",
            params={"min_candles": 90, "batch_size": 0, "currency": "IDR"},
            symbols=[],
        )
    )


def probe(symbols: List[str], now: Optional[datetime], show: int) -> int:
    config = load_config()
    provider = build_providers(config.providers)[Market.STOCK]
    scanner = build_scanner(len(symbols))
    logger = get_logger("asta.probe")

    fired = 0
    rows = []
    for symbol in symbols:
        try:
            candles = provider.fetch_candles(symbol, "5m", 130)
        except AstaError as exc:
            rows.append((symbol, "provider: {}".format(str(exc)[:60]), None))
            continue
        stamp = now or default_now(candles)
        context = ScanContext(
            market=Market.STOCK,
            symbol=symbol,
            timeframe="5m",
            candles=candles,
            now=stamp,
        )
        # measure on the same window the scanner sees (nothing after ``stamp``)
        seen = [c for c in candles if c.timestamp <= stamp]
        today = [c for c in seen if c.timestamp.astimezone(JKT).date() == stamp.astimezone(JKT).date()]
        older = [c for c in seen if c.timestamp.astimezone(JKT).date() < stamp.astimezone(JKT).date()]
        volume = sum(c.volume for c in today)
        value = sum(c.close * c.volume for c in today)
        prev_close = older[-1].close if older else float("nan")
        change = (seen[-1].close / prev_close - 1.0) * 100.0 if older else float("nan")
        signals = scanner.scan(context) if today and older else []
        if signals:
            fired += 1
            signal = signals[0]
            rows.append(
                (
                    symbol,
                    "SIGNAL score={:.2f} sl={:,.0f} tp={:,.0f} exp={}".format(
                        signal.confidence,
                        signal.stop_loss or 0,
                        signal.take_profit or 0,
                        signal.expires_at.astimezone(JKT).strftime("%H:%M") if signal.expires_at else "-",
                    ),
                    (seen[-1].close, volume, value, change),
                )
            )
        else:
            reasons = []
            if not today:
                reasons.append("no bars today")
            if not older:
                reasons.append("no previous close")
            if today and seen[-1].close < 100:
                reasons.append("price<100")
            if today and volume <= 1_000_000:
                reasons.append("volume<=1jt")
            if today and value <= 1_000_000_000:
                reasons.append("value<=1M")
            if older and change <= 0:
                reasons.append("change<=0")
            rows.append((symbol, ", ".join(reasons) or "skipped", (seen[-1].close, volume, value, change)))

    print("{:<12} {:>10} {:>14} {:>16} {:>8}  {}".format("symbol", "price", "volume", "value(IDR)", "chg%", "verdict"))
    for symbol, verdict, numbers in rows[:show]:
        if numbers is None:
            print("{:<12} {:>10} {:>14} {:>16} {:>8}  {}".format(symbol, "-", "-", "-", "-", verdict))
            continue
        price, volume, value, change = numbers
        print(
            "{:<12} {:>10,.0f} {:>14,.0f} {:>16,.0f} {:>8.2f}  {}".format(
                symbol, price, volume, value, change, verdict
            )
        )
    print("\n{}/{} symbols produced a signal".format(fired, len(symbols)))
    logger.info("probe done", extra={"fired": fired, "symbols": len(symbols)})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default="", help="comma separated, .JK optional")
    parser.add_argument("--limit", type=int, default=30, help="how many of the liquid list to probe")
    parser.add_argument("--now", default="", help="ISO timestamp in WIB, e.g. 2026-11-17T15:44")
    parser.add_argument("--show", type=int, default=40)
    args = parser.parse_args()

    if args.symbols.strip():
        symbols = [
            item.strip().upper() + ("" if item.strip().upper().endswith(".JK") else ".JK")
            for item in args.symbols.split(",")
            if item.strip()
        ]
    else:
        symbols = LIQUID[: max(args.limit, 1)]

    now = None
    if args.now.strip():
        now = datetime.fromisoformat(args.now.strip()).replace(tzinfo=JKT)

    return probe(symbols, now, args.show)


if __name__ == "__main__":
    raise SystemExit(main())
