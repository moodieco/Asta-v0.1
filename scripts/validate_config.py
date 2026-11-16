"""Static validation of the config directory and scanner packages.

    PYTHONPATH=src python scripts/validate_config.py

Checks: config files parse, scanner class <-> config.yaml pair, market directory
matches the configured market, timeframes are valid, overrides reference real
scanners, enabled markets have a provider, webhook env vars are present.

Exit code 0 = clean, 1 = errors (warnings do not fail).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import os  # noqa: E402

from asta.config import load_config, validate_scanner_timeframes  # noqa: E402
from asta.core.scanner_registry import ScannerRegistry  # noqa: E402
from asta.core.signal_model import Market  # noqa: E402
from asta.utils.exceptions import AstaError  # noqa: E402

ERRORS = []
WARNINGS = []

PROVIDER_FOR_MARKET = {"forex": "oanda", "crypto": "binance", "stock": "stock"}


def error(message: str) -> None:
    ERRORS.append(message)


def warn(message: str) -> None:
    WARNINGS.append(message)


def main() -> int:
    config_dir = None
    if len(sys.argv) > 1:
        config_dir = sys.argv[1]

    try:
        config = load_config(config_dir)
    except AstaError as exc:
        print("ERROR: {}".format(exc))
        return 1

    registry = ScannerRegistry()
    registry.discover()
    classes = registry.classes
    configs = registry.load_configs()

    for scanner_id in sorted(set(configs) - set(classes)):
        error("scanner config without class: {}".format(scanner_id))
    for scanner_id in sorted(set(classes) - set(configs)):
        error("scanner class without config.yaml: {}".format(scanner_id))

    for scanner_id, scanner_config in configs.items():
        scanner_cls = classes.get(scanner_id)
        if scanner_cls is None:
            continue
        if scanner_cls.market != scanner_config.market:
            error(
                "{}: class market {} != config market {}".format(
                    scanner_id, scanner_cls.market.value, scanner_config.market.value
                )
            )
        source = Path(scanner_config.source_path or "")
        if source and source.parent.parent.parent.name != scanner_config.market.value:
            error(
                "{}: folder market {} != config market {}".format(
                    scanner_id, source.parent.parent.parent.name, scanner_config.market.value
                )
            )
        if scanner_config.enabled and not scanner_config.symbols and not config.markets.get(
            scanner_config.market.value
        ):
            warn("{}: no symbols anywhere (scanner, market config, universe)".format(scanner_id))

    for scanner_id in validate_scanner_timeframes(config):
        error("{}: invalid timeframe override".format(scanner_id))
    for scanner_id in config.scanner_overrides:
        if scanner_id not in classes:
            error("scanner_overrides references unknown scanner: {}".format(scanner_id))

    for market in Market:
        enabled = config.markets.get(market.value)
        if enabled is None:
            warn("market {} missing from markets.yaml".format(market.value))
            continue
        if enabled.enabled:
            # Two accepted shapes: market-keyed (providers.crypto.type: binance)
            # and the legacy flat one (providers.binance). Accept both so a valid
            # config never fails this check.
            legacy_key = PROVIDER_FOR_MARKET.get(market.value)
            block = config.providers.get(market.value)
            if block is None and legacy_key not in config.providers:
                error(
                    "enabled market {} has no provider block (providers.{} or providers.{})".format(
                        market.value, market.value, legacy_key
                    )
                )
            elif isinstance(block, dict) and not block.get("type"):
                error("providers.{} has no type".format(market.value))
            webhook_env = config.webhook_env(market.value)
            if not os.getenv(webhook_env, "").strip():
                warn("{}: {} is empty -> alerts cannot be delivered".format(market.value, webhook_env))

    print("config dir : {}".format(config.config_dir))
    print("scanners   : {}".format(len(classes)))
    print("markets    : {}".format(", ".join(sorted(config.markets)) or "<none>"))
    storage_path = (
        config.storage.sqlite_path
        if config.storage.backend == "sqlite"
        else config.storage.signal_history_path
    )
    print("storage    : {} -> {}".format(config.storage.backend, storage_path))
    print("warnings   : {}".format(len(WARNINGS)))
    for message in WARNINGS:
        print("  - {}".format(message))
    print("errors     : {}".format(len(ERRORS)))
    for message in ERRORS:
        print("  ! {}".format(message))
    return 0 if not ERRORS else 1


if __name__ == "__main__":
    raise SystemExit(main())
