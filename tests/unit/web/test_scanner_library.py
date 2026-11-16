"""User scanner library: install / uninstall / restore / purge / enable."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

import pytest

from asta.core.scanner_registry import ScannerRegistry
from asta.utils.exceptions import ConfigurationError
from asta.web.scanner_library import ScannerLibrary


def scanner_source(scanner_id: str) -> str:
    return (
        "from asta.core.scanner_base import ScannerBase\n"
        "from asta.core.scanner_registry import register_scanner\n"
        "from asta.core.signal_model import Market\n\n"
        "@register_scanner\n"
        "class DemoScanner(ScannerBase):\n"
        "    id = '{}'\n"
        "    name = 'Demo'\n"
        "    market = Market.CRYPTO\n"
        "    def evaluate(self, context):\n"
        "        return []\n"
    ).format(scanner_id)


@pytest.fixture()
def library(tmp_path: Path) -> ScannerLibrary:
    return ScannerLibrary(tmp_path / "scanners")


def test_install_writes_files_and_manifest(library: ScannerLibrary) -> None:
    source = scanner_source("CXS001_MY_SCANNER")
    record = library.install("crypto", "My Scanner", "0.1.0", source, "scanner.py", timeframes=["1h"])
    assert record["scannerId"] == "CXS001_MY_SCANNER"
    folder = library.root / "crypto" / "CXS001_MY_SCANNER"
    assert (folder / "scanner.py").is_file()
    assert (folder / "config.yaml").is_file()
    assert (folder / "manifest.json").is_file()
    installed = library.list_installed()
    assert installed[0]["name"] == "My Scanner"
    assert installed[0]["status"] == "installed"


def test_install_uses_the_declared_id(library: ScannerLibrary) -> None:
    record = library.install("crypto", "Whatever Name", "0.1.0", scanner_source("CXS042_DEMO"), "scanner.py")
    assert record["scannerId"] == "CXS042_DEMO"


def test_install_rejects_id_without_declared_value(library: ScannerLibrary) -> None:
    source = "class X:\n    pass\n"
    with pytest.raises(ConfigurationError):
        library.install("crypto", "X", "0.1.0", source, "scanner.py")


def test_install_rejects_mismatched_market_prefix(library: ScannerLibrary) -> None:
    with pytest.raises(ConfigurationError):
        library.install("stock", "X", "0.1.0", scanner_source("CXS001_DEMO"), "scanner.py")


def test_install_rejects_bad_version(library: ScannerLibrary) -> None:
    with pytest.raises(ConfigurationError):
        library.install("crypto", "X", "not-semver", scanner_source("CXS001_DEMO"), "scanner.py")


def test_install_rejects_unknown_market(library: ScannerLibrary) -> None:
    with pytest.raises(ConfigurationError):
        library.install("bonds", "X", "0.1.0", scanner_source("CXS001_DEMO"), "scanner.py")


def test_install_rejects_empty_source(library: ScannerLibrary) -> None:
    with pytest.raises(ConfigurationError):
        library.install("crypto", "X", "0.1.0", "", "scanner.py")


def test_install_from_zip(library: ScannerLibrary) -> None:
    source = scanner_source("CXS001_ZIPPED")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("scanner.py", source)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    library.install("crypto", "Zipped", "0.1.0", encoded, "bundle.zip", timeframes=["4h"])
    folder = library.root / "crypto" / "CXS001_ZIPPED"
    assert (folder / "scanner.py").read_text(encoding="utf-8") == source


def test_uninstall_moves_to_trash_and_restore(library: ScannerLibrary) -> None:
    record = library.install("stock", "Trend", "0.1.0", scanner_source("STS001_TREND"), "scanner.py")
    scanner_id = record["scannerId"]

    library.uninstall(scanner_id, reason="cleanup")
    assert library.find_installed(scanner_id) is None
    trashed = library.find_trash(scanner_id)
    assert trashed is not None
    assert trashed["status"] == "deleted"
    assert trashed["deletedReason"] == "cleanup"

    library.restore(scanner_id)
    assert library.find_installed(scanner_id) is not None
    assert library.find_trash(scanner_id) is None


def test_purge_permanently_deletes(library: ScannerLibrary) -> None:
    record = library.install("forex", "Cross", "0.1.0", scanner_source("FXS001_CROSS"), "scanner.py")
    scanner_id = record["scannerId"]
    library.uninstall(scanner_id)
    library.purge(scanner_id)
    assert library.find_trash(scanner_id) is None
    assert not (library.trash_root / scanner_id).exists()


def test_set_enabled_flips_config(library: ScannerLibrary) -> None:
    record = library.install("crypto", "X", "0.1.0", scanner_source("CXS001_X"), "scanner.py")
    scanner_id = record["scannerId"]
    library.set_enabled(scanner_id, False)
    assert library.find_installed(scanner_id)["enabled"] is False
    library.set_enabled(scanner_id, True)
    assert library.find_installed(scanner_id)["enabled"] is True


def test_duplicate_id_is_rejected(library: ScannerLibrary) -> None:
    source = scanner_source("CXS001_DUP")
    library.install("crypto", "First", "0.1.0", source, "scanner.py")
    with pytest.raises(ConfigurationError):
        library.install("crypto", "Second", "0.1.0", source, "scanner.py")


def test_history_records_events(library: ScannerLibrary) -> None:
    record = library.install("crypto", "Log", "0.1.0", scanner_source("CXS001_LOG"), "scanner.py")
    library.uninstall(record["scannerId"])
    actions = [event["action"] for event in library.history()]
    assert actions == ["uninstall", "install"]


def test_engine_discovers_and_loads_user_scanners(library: ScannerLibrary) -> None:
    """An uploaded scanner is importable and configurable by the real registry."""
    library.install("crypto", "Engine", "0.1.0", scanner_source("CXS777_ENGINE"), "scanner.py")

    registry = ScannerRegistry()
    imported = registry.discover_user_scanners(library.root)
    assert any("CXS777_ENGINE" in name for name in imported)
    assert "CXS777_ENGINE" in registry.classes

    configs = registry.load_user_configs(library.root)
    assert "CXS777_ENGINE" in configs
    assert configs["CXS777_ENGINE"].market.value == "crypto"
