import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def scanner_registry():
    from asta.core.scanner_registry import ScannerRegistry

    registry = ScannerRegistry()
    registry.discover()
    return registry


@pytest.fixture
def scanners(scanner_registry):
    return {scanner.id: scanner for scanner in scanner_registry.build_all(scanner_registry.load_configs())}
