import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def clean_asta_env(monkeypatch):
    """Keep the developer's .env from leaking into assertions."""
    for variable in (
        "ASTA_LOG_LEVEL",
        "ASTA_LOG_FORMAT",
        "ASTA_DRY_RUN",
        "ASTA_CONFIG",
        "ASTA_CONFIG_DIR",
        "OANDA_API_TOKEN",
        "OANDA_ACCOUNT_ID",
        "SIGNALS_PATH",
        "STORAGE_BACKEND",
        "DISCORD_WEBHOOK_FOREX",
        "DISCORD_WEBHOOK_CRYPTO",
        "DISCORD_WEBHOOK_STOCK",
    ):
        monkeypatch.delenv(variable, raising=False)
    yield


@pytest.fixture
def scanner_registry():
    from asta.core.scanner_registry import ScannerRegistry

    registry = ScannerRegistry()
    registry.discover()
    return registry


@pytest.fixture
def scanners(scanner_registry):
    return {scanner.id: scanner for scanner in scanner_registry.build_all(scanner_registry.load_configs())}
