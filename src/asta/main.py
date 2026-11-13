"""ASTA command line entry point.

    asta --once            # single scan cycle, then exit
    asta --once --dry-run  # scan without posting to Discord
    asta                   # run the scheduler loop
    asta --list-scanners   # show discovered scanners and their config
    asta --health          # provider/credential status
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from asta.app import AstaApp
from asta.core.signal_model import Market
from asta.utils.exceptions import AstaError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asta", description="ASTA V0.1 signal scanner")
    parser.add_argument("--config", default=None, help="path to asta.yaml (default: config/asta.yaml)")
    parser.add_argument("--once", action="store_true", help="run a single scan cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="never post to Discord")
    parser.add_argument("--list-scanners", action="store_true", help="print discovered scanners")
    parser.add_argument("--health", action="store_true", help="print provider and credential health")
    parser.add_argument(
        "--sample-alert",
        action="store_true",
        help="post a labelled sample signal card to each enabled market channel",
    )
    parser.add_argument(
        "--test-alert",
        action="store_true",
        help="post a labelled connectivity test to every configured Discord webhook",
    )
    parser.add_argument(
        "--markets",
        default="",
        help="comma separated market filter, e.g. crypto,forex",
    )
    parser.add_argument(
        "--scanners",
        default="",
        help="comma separated scanner id filter, e.g. CXS002_VOLUME_SPIKE",
    )
    return parser


def _parse_markets(raw: str) -> Optional[List[Market]]:
    values = [item.strip().lower() for item in (raw or "").split(",") if item.strip()]
    if not values:
        return None
    markets: List[Market] = []
    for value in values:
        try:
            markets.append(Market(value))
        except ValueError:
            raise AstaError("unknown market {!r}".format(value))
    return markets


def _parse_scanners(raw: str) -> Optional[List[str]]:
    values = [item.strip().upper() for item in (raw or "").split(",") if item.strip()]
    return values or None


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        app = AstaApp.from_config(args.config, dry_run=True if args.dry_run else None)
        app.build()
    except AstaError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2

    try:
        if args.list_scanners:
            for scanner in app.scanner_inventory():
                print(
                    "{id:<26} {market:<7} {timeframe:<4} {state:<8} {name}".format(
                        id=scanner["id"],
                        market=scanner["market"],
                        timeframe=scanner["timeframe"],
                        state="enabled" if scanner["enabled"] else "disabled",
                        name=scanner["name"],
                    )
                )
            return 0

        if args.health:
            print(json.dumps(app.health(), indent=2))
            return 0

        if args.sample_alert:
            results = app.send_sample_alerts()
            print(json.dumps({"sample_alerts": results}, indent=2))
            return 0 if all(item.get("ok") for item in results) else 1

        if args.test_alert:
            results = app.send_test_alerts()
            print(json.dumps({"test_alerts": results}, indent=2))
            return 0 if all(item.get("ok") for item in results) else 1

        if args.once:
            report = app.run_once(
                markets=_parse_markets(args.markets),
                scanner_ids=_parse_scanners(args.scanners),
            )
            print(json.dumps(report.to_dict(), indent=2))
            return 0

        app.run()
        return 0
    finally:
        app.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
