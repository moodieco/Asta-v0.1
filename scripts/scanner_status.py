"""Scanner inventory, provider health and recent signals.

    PYTHONPATH=src python scripts/scanner_status.py
    PYTHONPATH=src python scripts/scanner_status.py --limit 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.bootstrap import AstaApp  # noqa: E402
from asta.utils.logger import configure_logging  # noqa: E402
from asta.utils.time_utils import parse_datetime, short_datetime  # noqa: E402


def _short(value) -> str:
    if not value:
        return "?"
    try:
        return short_datetime(parse_datetime(str(value)))
    except (TypeError, ValueError):
        return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="ASTA scanner status")
    parser.add_argument("--config", default=None, help="config directory")
    parser.add_argument("--limit", type=int, default=5, help="recent signals to show")
    args = parser.parse_args()

    configure_logging("WARNING")
    app = AstaApp.from_config(args.config).build()

    print("\nSCANNERS")
    for scanner in app.scanner_inventory():
        symbols = scanner["symbols"] or ["<market universe>"]
        print(
            "  {id:<26} {market:<7} {timeframe:<4} {state:<8} {name}".format(
                id=scanner["id"],
                market=scanner["market"],
                timeframe=scanner["timeframe"],
                state="enabled" if scanner["enabled"] else "disabled",
                name=scanner["name"],
            )
        )
        print("      symbols: {}".format(", ".join(symbols)))

    health = app.health()
    print("\nHEALTH")
    print("  providers : {}".format(health["providers"]))
    print("  webhooks  : {}".format(health["webhooks"]))
    print(
        "  storage   : {} ({} records)".format(
            health["storage"]["backend"], health["storage"]["records"]
        )
    )
    print("  cache     : {}".format(health["data_cache"]))

    recent = app.history.tail(args.limit) if app.history else []
    print("\nRECENT SIGNALS ({})".format(len(recent)))
    for record in reversed(recent):
        print(
            "  {} {} {} {} conf={:.0%} {}".format(
                _short(record.get("timestamp")),
                record.get("scanner_id", "?"),
                record.get("symbol", "?"),
                record.get("signal_type", "?"),
                float(record.get("confidence", 0)),
                record.get("reason", "")[:60],
            )
        )
    if not recent:
        print("  (none yet)")

    app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
