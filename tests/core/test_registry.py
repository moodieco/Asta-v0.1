import pytest

from asta.core.scanner_registry import SCANNER_CLASSES, ScannerRegistry, register_scanner
from asta.core.scanner_base import ScannerBase, ScannerConfig
from asta.core.signal_model import Market
from asta.utils.exceptions import ConfigurationError

EXPECTED_IDS = {
    "FXS001_RSI_DIVERGENCE",
    "FXS002_EMA_CROSSOVER",
    "CXS001_RSI_DIVERGENCE",
    "CXS002_VOLUME_SPIKE",
    "CXS003_BREAKOUT_TREND",
    "STS001_EMA_TREND",
    "STS002_BREAKOUT_TREND",
}


def test_discovery_registers_every_scanner(scanner_registry):
    assert EXPECTED_IDS.issubset(set(scanner_registry.ids()))


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
