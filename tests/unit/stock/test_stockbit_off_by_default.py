"""Guards for the OFF state of the Stockbit MCP integration.

The sidecar is not part of the install: it is a third-party Node process, it is
never started by ASTA, and it is not a selectable provider type. These tests
exist so "off by default" stays a checked fact instead of a sentence in a doc.
"""

import pytest

from asta.config import load_config
from asta.core.signal_model import Market
from asta.providers import PROVIDER_TYPES, build_providers
from asta.providers.stock.yahoo import StockProvider
from asta.utils.exceptions import ConfigurationError


def test_stockbit_is_not_a_provider_type():
    assert "stockbit" not in PROVIDER_TYPES


def test_default_stock_provider_is_still_yahoo():
    providers = build_providers({})
    assert isinstance(providers[Market.STOCK], StockProvider)


def test_selecting_stockbit_as_provider_type_fails_loudly():
    with pytest.raises(ConfigurationError) as excinfo:
        build_providers({"stock": {"type": "stockbit"}})
    assert "unknown provider type" in str(excinfo.value)


def test_shipped_config_has_no_stockbit_block():
    config = load_config()
    assert "stockbit" not in config.providers
    assert config.providers["stock"].get("type") == "yahoo"
