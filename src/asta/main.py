"""ASTA command line interface.

    asta                        # scheduler loop (scanner only, no dashboard)
    asta serve                  # scanner + dashboard on http://127.0.0.1:4310
    asta status                 # JSON status of a running instance
    asta setup                  # quick setup wizard (desktop window)
    asta launcher               # desktop launcher (start/stop/status)

    asta --once                 # single scan cycle, then exit
    asta --once --dry-run       # scan without posting to Discord
    asta --list-scanners        # discovered scanners and their config
    asta --health               # providers, storage, webhooks
    asta --test-alert           # connectivity test to every webhook
    asta --sample-alert         # sample signal card in each enabled channel
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from typing import List, Optional

from asta import __version__
from asta.bootstrap import AstaApp
from asta.core.signal_model import Market
from asta.utils.exceptions import AstaError

COMMANDS = ("serve", "status", "setup", "launcher", "pins")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asta", description="ASTA V0.1 signal scanner")
    parser.add_argument(
        "command",
        nargs="?",
        default=None,
        choices=COMMANDS,
        help="serve = scanner + dashboard; status; setup; launcher; pins",
    )
    parser.add_argument(
        "action",
        nargs="?",
        default=None,
        choices=("set", "status", "clear"),
        help="pins only: set | status | clear (default status)",
    )
    parser.add_argument(
        "--role",
        default=None,
        choices=("viewer", "editor"),
        help="pins only: which role the PIN unlocks",
    )
    parser.add_argument("--pin", default=None, help="pins set only: the PIN itself")
    parser.add_argument("--config", default=None, help="config directory (default: config/)")
    parser.add_argument("--once", action="store_true", help="run a single scan cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="never post to Discord")
    parser.add_argument("--host", default=None, help="dashboard bind host (default: from config)")
    parser.add_argument("--port", type=int, default=None, help="dashboard port (default: 4310)")
    parser.add_argument(
        "--no-browser", action="store_true", help="serve without opening a browser"
    )
    parser.add_argument(
        "--browser", action="store_true", help="open the launcher panel in the default browser"
    )
    parser.add_argument("--list-scanners", action="store_true", help="print discovered scanners")
    parser.add_argument("--health", action="store_true", help="print provider/storage/webhook health")
    parser.add_argument(
        "--test-alert", action="store_true", help="post a labelled test to every webhook"
    )
    parser.add_argument(
        "--sample-alert", action="store_true", help="post a labelled sample signal card"
    )
    parser.add_argument("--markets", default="", help="comma separated market filter")
    parser.add_argument("--scanners", default="", help="comma separated scanner id filter")
    parser.add_argument("--version", action="version", version="asta {}".format(__version__))
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
            raise AstaError("unknown market {!r}".format(value)) from None
    return markets


def _parse_scanners(raw: str) -> Optional[List[str]]:
    values = [item.strip().upper() for item in (raw or "").split(",") if item.strip()]
    return values or None


async def _run_until_signal(app: AstaApp) -> None:
    """Run the scanner loop until SIGINT/SIGTERM.

    The stop event must be created *inside* the running loop: an ``asyncio.Event``
    built before ``asyncio.run`` binds to a different (never-running) loop and the
    wait then dies with "Future attached to a different loop".
    """
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):  # pragma: no cover - non-POSIX
            signal.signal(sig, lambda *_: stop.set())
    await app.run_forever(stop_event=stop)


def _serve(args: argparse.Namespace) -> int:
    """Scanner + dashboard in one process: the browser is optional, the scanner is not."""
    from asta.web.service import WebService

    app = AstaApp.from_config(args.config, dry_run=True if args.dry_run else None)
    app.build()
    service = WebService(
        app,
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
    )
    url = service.start()
    print(
        json.dumps(
            {
                "status": "serving",
                "url": url,
                "pid": os.getpid(),
                "scanners": len(app.analysis) if app.analysis else 0,
                "open_browser": not args.no_browser,
            },
            indent=2,
        ),
        flush=True,
    )
    try:
        asyncio.run(_run_until_signal(app))
    except KeyboardInterrupt:  # pragma: no cover - interactive
        pass
    finally:
        service.stop()
        app.close()
    return 0


def _status(args: argparse.Namespace) -> int:
    from asta.config import load_config
    from asta.web.service import probe

    config = load_config(args.config, require=False)
    web = getattr(config, "web", None)
    host = args.host or getattr(web, "host", "127.0.0.1") or "127.0.0.1"
    port = args.port or getattr(web, "port", 4310) or 4310
    url = "http://{}:{}/".format(host, port)
    remote = probe(url)
    payload = {
        "running": remote is not None,
        "url": url,
        "config": {
            "environment": config.environment,
            "storage_backend": config.storage.backend,
            "sqlite_path": str(config.resolve_path(config.storage.sqlite_path)),
        },
    }
    if remote is not None:
        payload["server"] = remote
    print(json.dumps(payload, indent=2))
    return 0 if remote is not None else 1


def _setup(args: argparse.Namespace) -> int:
    from asta.launcher.app import run_launcher

    return run_launcher(args.config, focus_setup=True)


def _launcher(args: argparse.Namespace) -> int:
    from asta.launcher.app import run_launcher

    return run_launcher(args.config, in_browser=bool(getattr(args, "browser", False)))


def _pins(args: argparse.Namespace) -> int:
    """Manage the role PINs the public dashboard asks for on the login screen."""
    from asta.config import load_config
    from asta.web.share import PIN_ROLES, SESSION_TTL, ShareManager

    config = load_config(args.config, require=False)
    path = config.resolve_path("data/share.json")
    manager = ShareManager(path)
    action = getattr(args, "action", None) or "status"
    role = (getattr(args, "role", None) or "").strip().lower()

    if action == "status":
        print(
            json.dumps(
                {
                    "path": str(path),
                    "configured": manager.pins_configured(),
                    "sessionTtlSeconds": SESSION_TTL,
                    "sharedLinksStillWork": bool(manager.tokens()),
                },
                indent=2,
            )
        )
        return 0

    if role not in PIN_ROLES:
        print("error: --role must be viewer or editor", file=sys.stderr)
        return 2

    if action == "clear":
        removed = manager.clear_pin(role)
        print(json.dumps({"role": role, "cleared": removed, "path": str(path)}, indent=2))
        return 0

    pin = getattr(args, "pin", None)
    if not pin:
        print("error: --pin is required (or pipe it through --pin)", file=sys.stderr)
        return 2
    try:
        manager.set_pin(role, pin)
    except ValueError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    print(json.dumps({"role": role, "configured": True, "path": str(path)}, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "serve":
        try:
            return _serve(args)
        except AstaError as exc:
            print("error: {}".format(exc), file=sys.stderr)
            return 2
    if args.command == "status":
        return _status(args)
    if args.command == "setup":
        return _setup(args)
    if args.command == "launcher":
        return _launcher(args)
    if args.command == "pins":
        return _pins(args)

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

        if args.test_alert:
            results = app.send_test_alerts()
            print(json.dumps({"test_alerts": results}, indent=2))
            return 0 if all(item.get("ok") for item in results) else 1

        if args.sample_alert:
            results = app.send_sample_alerts()
            print(json.dumps({"sample_alerts": results}, indent=2))
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
