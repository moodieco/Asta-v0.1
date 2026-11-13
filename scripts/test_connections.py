"""Check every data provider and Discord webhook.

    PYTHONPATH=src python scripts/test_connections.py
    PYTHONPATH=src python scripts/test_connections.py --send   # also post test alerts

Exits non-zero if an enabled market cannot fetch data or a configured webhook is dead.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402

from asta.bootstrap import AstaApp  # noqa: E402
from asta.core.signal_model import Market  # noqa: E402
from asta.utils.logger import configure_logging  # noqa: E402


def webhook_details(url: str) -> dict:
    try:
        response = httpx.get(url, timeout=10)
        payload = response.json() if response.status_code == 200 else {}
        return {
            "status": response.status_code,
            "channel": payload.get("name") or payload.get("channel_id") or "?",
            "ok": response.status_code == 200,
        }
    except Exception as exc:  # noqa: BLE001 - diagnostic tool
        return {"status": None, "channel": "?", "ok": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Provider + Discord connectivity check")
    parser.add_argument("--config", default=None, help="config directory")
    parser.add_argument("--send", action="store_true", help="post a labelled test alert")
    args = parser.parse_args()

    configure_logging("WARNING")
    app = AstaApp.from_config(args.config).build()
    failures = 0

    print("\nPROVIDERS")
    for market in Market:
        provider = app.market_manager.providers.get(market)
        if provider is None:
            print("  {:<7} no provider".format(market.value))
            failures += 1
            continue
        enabled = app.market_manager.is_enabled(market)
        configured = provider.is_configured()
        healthy = provider.health_check() if configured else False
        state = "ok" if healthy else ("unconfigured" if not configured else "unreachable")
        print(
            "  {:<7} provider={:<8} enabled={:<5} {:<13} {}".format(
                market.value, provider.name, str(enabled), state,
                "" if healthy or not enabled else "<-- problem",
            )
        )
        if enabled and not healthy:
            failures += 1

    print("\nDISCORD")
    for market in Market:
        webhook = app.notifications.channels.webhook_for(market)
        if not webhook:
            print("  {:<7} no webhook configured".format(market.value))
            if app.market_manager.is_enabled(market):
                failures += 1
            continue
        detail = webhook_details(webhook)
        print(
            "  {:<7} channel={:<16} http={} {}".format(
                market.value, detail["channel"], detail["status"],
                "ok" if detail["ok"] else "<-- problem",
            )
        )
        if not detail["ok"]:
            failures += 1

    if args.send:
        print("\nTEST ALERTS")
        for result in app.send_test_alerts():
            print("  {}".format(result))
            failures += 0 if result.get("ok") else 1

    app.close()
    print("\nresult: {}".format("OK" if failures == 0 else "{} problem(s)".format(failures)))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
