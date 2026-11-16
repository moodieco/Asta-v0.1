import pytest

from asta.core.scanner_base import ScannerBase, ScannerConfig
from asta.core.scanner_registry import (
    SCANNER_CLASSES,
    log_discovery_error,
    register_scanner,
)
from asta.core.signal_model import Market
from asta.utils.exceptions import ConfigurationError

EXPECTED_IDS = {
    "FXS001_RSI_DIVERGENCE",
    "FXS002_EMA_CROSSOVER",
    "CXS001_RSI_DIVERGENCE",
    "CXS002_VOLUME_SPIKE",
    "CXS003_BREAKOUT_TREND",
    "CXS004_EMA_PULLBACK",
    "FXS003_ASIA_RANGE_BREAKOUT",
    "STS001_EMA_TREND",
    "STS002_BREAKOUT_TREND",
}


def test_discovery_registers_every_scanner(scanner_registry):
    assert EXPECTED_IDS.issubset(set(scanner_registry.ids()))


def test_second_discovery_restores_scanners_from_cached_modules(monkeypatch):
    """Discovery must be idempotent inside one process.

    A module already in ``sys.modules`` is not re-executed, so its
    ``@register_scanner`` decorator never runs again. If another component left a
    partial global registry behind (a stub class, a cleared dict), a second
    discovery used to register nothing and every real scanner silently vanished.
    """
    from asta.core import scanner_registry as sr

    first = sr.ScannerRegistry()
    first.discover()
    assert "CXS003_BREAKOUT_TREND" in first.ids()

    stub = first.get_class("CXS003_BREAKOUT_TREND")
    monkeypatch.setattr(sr, "SCANNER_CLASSES", {"CXS777_ENGINE": stub})

    second = sr.ScannerRegistry()
    second.discover()
    assert "CXS003_BREAKOUT_TREND" in second.ids()


def test_each_scanner_has_a_config_file(scanner_registry):
    configs = scanner_registry.load_configs()
    assert EXPECTED_IDS.issubset(set(configs))
    for scanner_id in EXPECTED_IDS:
        config = configs[scanner_id]
        assert config.id == scanner_id
        assert config.name
        assert config.description
        assert isinstance(config.market, Market)


def test_config_matches_scanner_market(scanner_registry):
    for scanner in scanner_registry.build_all(scanner_registry.load_configs()):
        assert scanner.config.market is scanner.market
        assert scanner.timeframe == scanner.config.timeframe


def test_overrides_are_applied_and_leave_defaults_intact(scanner_registry):
    configs = scanner_registry.load_configs()
    base = scanner_registry.create(configs["FXS001_RSI_DIVERGENCE"])
    overridden = scanner_registry.create(
        configs["FXS001_RSI_DIVERGENCE"],
        {"timeframe": "4h", "params": {"lookback": 60}, "symbols": ["eur_usd"]},
    )
    assert base.timeframe == "1h"
    assert base.params["lookback"] == 120
    assert overridden.timeframe == "4h"
    assert overridden.params["lookback"] == 60
    assert overridden.symbols == ["EUR_USD"]


def test_unknown_scanner_id_raises(scanner_registry):
    with pytest.raises(ConfigurationError):
        scanner_registry.get_class("NOPE_001")


def test_duplicate_registration_is_rejected():
    class First(ScannerBase):
        id = "DUP_001"
        name = "First"
        market = Market.STOCK

        def evaluate(self, context):  # pragma: no cover - unused
            return []

    class Second(ScannerBase):
        id = "DUP_001"
        name = "Second"
        market = Market.STOCK

        def evaluate(self, context):  # pragma: no cover - unused
            return []

    register_scanner(First)
    try:
        with pytest.raises(ConfigurationError):
            register_scanner(Second)
    finally:
        SCANNER_CLASSES.pop("DUP_001", None)


def test_build_all_skips_configs_without_classes(scanner_registry):
    configs = scanner_registry.load_configs()
    orphan = ScannerConfig(id="ORPHAN_001", name="Orphan", market="stock")
    scanners = scanner_registry.build_all({**configs, "ORPHAN_001": orphan})
    assert "ORPHAN_001" not in [scanner.id for scanner in scanners]


def test_discovery_error_logging_does_not_raise():
    # "module" is reserved on LogRecord; logging it in `extra` used to raise KeyError
    # and hide the real import error.
    log_discovery_error("asta.markets.crypto.scanners.BROKEN.scanner")
