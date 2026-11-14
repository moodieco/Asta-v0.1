"""Close open signals by replaying candles: hit SL, hit TP, or expired.

    PYTHONPATH=src python scripts/update_outcomes.py
    PYTHONPATH=src python scripts/update_outcomes.py --dry-run
    PYTHONPATH=src python scripts/update_outcomes.py --no-sync   # DB only

Conservative rule: if one candle touches both stop and target, the stop is assumed
first. Realized R is +1 for a target hit, -1 for a stop, 0 for expiry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.bootstrap import AstaApp  # noqa: E402
from asta.core.risk import outcome_for_signal  # noqa: E402
from asta.core.signal_model import Market  # noqa: E402
from asta.utils.exceptions import AstaError  # noqa: E402
from asta.utils.logger import configure_logging  # noqa: E402
from asta.utils.time_utils import parse_datetime, utcnow  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Update signal outcomes from candles")
    parser.add_argument("--config", default=None)
    parser.add_argument("--limit", type=int, default=200, help="open signals to check")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configure_logging("WARNING")
    app = AstaApp.from_config(args.config).build()
    if app.history is None or app.data_service is None:
        print("history/data service unavailable")
        return 2

    rows = app.history.open_signals(args.limit)
    closed = []
    skipped = 0
    errors = []

    for row in rows:
        if row.get("stop_loss") is None or row.get("take_profit") is None:
            skipped += 1  # legacy rows recorded before risk levels existed
            continue
        market = Market(row["market"])
        if not app.data_service.is_enabled(market):
            skipped += 1
            continue
        try:
            candles = app.data_service.provider(market).fetch_candles(
                row["symbol"], row["timeframe"], 500
            )
        except AstaError as exc:
            errors.append("{} {}: {}".format(row.get("symbol"), row.get("timeframe"), exc))
            continue

        signal_time = parse_datetime(row["timestamp"])
        after = [candle for candle in candles if candle.timestamp > signal_time]
        expires_at = parse_datetime(row["expires_at"]) if row.get("expires_at") else None
        outcome = outcome_for_signal(
            row["signal_type"],
            float(row["price"]),
            row.get("stop_loss"),
            row.get("take_profit"),
            after,
            expires_at,
        )
        if outcome["status"] == "open" and expires_at is not None and utcnow() >= expires_at:
            outcome = {
                "status": "expired",
                "closed_at": expires_at.isoformat(),
                "realized_r": 0.0,
                "bars_held": len(after),
            }
        if outcome["status"] == "open":
            continue

        if not args.dry_run:
            app.history.update_outcome(
                row["signal_id"],
                outcome["status"],
                outcome["closed_at"],
                outcome["realized_r"],
                outcome["bars_held"],
            )
        closed.append(
            {
                "signal_id": row["signal_id"],
                "symbol": row["symbol"],
                "scanner_id": row["scanner_id"],
                **outcome,
            }
        )

    print(
        json.dumps(
            {
                "checked": len(rows),
                "closed": len(closed),
                "still_open": len(rows) - len(closed) - skipped,
                "skipped_legacy": skipped,
                "errors": errors,
                "closed_detail": closed,
            },
            indent=2,
        )
    )
    app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
