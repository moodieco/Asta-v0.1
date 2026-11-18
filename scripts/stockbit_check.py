"""Read-only probe of the Stockbit sidecar through ASTA's own client.

    python scripts/stockbit_check.py BBRI
    python scripts/stockbit_check.py --tools          # what the sidecar exposes

Requires the sidecar running (scripts/start_stockbit_mcp.sh) and a Stockbit
login in third_party/stockbit-mcp. Prints what each tool returns so a broken
tool shows its own error instead of a traceback. Never writes to the account.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.providers.stock.stockbit import StockbitClient, StockbitError
from asta.utils.logger import configure_logging


def show(label: str, payload: Any, limit: int = 900) -> None:
    print("\n== {} ==".format(label))
    try:
        text = json.dumps(payload, indent=2, default=str)
    except (TypeError, ValueError):
        text = repr(payload)
    print(text if len(text) <= limit else text[:limit] + "\n... (truncated)")


def attempt(label: str, call: Any) -> Any:
    try:
        return call()
    except StockbitError as exc:
        print("\n== {} ==\n  unavailable: {}".format(label, exc))
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Probe the Stockbit MCP sidecar")
    parser.add_argument("symbols", nargs="*", default=[], help="IDX tickers, e.g. BBRI TLKM")
    parser.add_argument("--window", default="1y", help="chart_series window (1w..5y)")
    parser.add_argument("--tools", action="store_true", help="list the sidecar's tools and exit")
    parser.add_argument("--url", default=None)
    parser.add_argument("--token", default=None)
    args = parser.parse_args(argv)

    configure_logging("WARNING")
    settings = {key: value for key, value in (("url", args.url), ("token", args.token)) if value}
    stockbit = StockbitClient(settings)

    status = attempt("status", stockbit.status)
    if status is not None:
        show("status", status)

    if args.tools:
        show("tools", stockbit.tools(), limit=4000)
        stockbit.close()
        return 0

    symbols = [s.upper() for s in args.symbols] or ["BBRI"]
    for symbol in symbols:
        print("\n{}".format("=" * 60))
        print("symbol: {}".format(symbol))
        for label, call in (
            ("quote", lambda s=symbol: stockbit.quote(s)),
            ("price_bands", lambda s=symbol: stockbit.price_bands(s)),
            ("broker_summary", lambda s=symbol: stockbit.broker_summary(s, period="LAST_7_DAYS", limit=5)),
            ("keystats", lambda s=symbol: stockbit.keystats(s)),
        ):
            value = attempt(label, call)
            if value is not None:
                show(label, value)
        closes = attempt("chart_series", lambda s=symbol: stockbit.daily_closes(s, args.window))
        if closes:
            print("\n== daily closes ({}) ==".format(args.window))
            print("  points : {}".format(len(closes)))
            print("  first  : {}".format(closes[0]))
            print("  last   : {}".format(closes[-1]))
            print("  NOTE   : close-only series, not OHLCV — cannot drive a scanner")

    stockbit.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
