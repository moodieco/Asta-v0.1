"""YAML edits must keep every comment and stay parseable."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from asta.setup.writer import YamlFile, set_scanner_enabled, set_web

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    target.mkdir()
    shutil.copy(REPO / "config" / "app.yaml", target / "app.yaml")
    shutil.copy(REPO / "config" / "markets.yaml", target / "markets.yaml")
    return target


def test_scalar_edit_keeps_comments_and_parses(config_dir: Path) -> None:
    before = (config_dir / "app.yaml").read_text(encoding="utf-8")
    document = set_web(config_dir / "app.yaml", port=4321)
    document.write()
    after = (config_dir / "app.yaml").read_text(encoding="utf-8")

    assert "port: 4310" not in after
    parsed = yaml.safe_load(after)
    assert parsed["web"]["port"] == 4321
    # every comment line that existed before still exists
    comments_before = [line for line in before.splitlines() if line.strip().startswith("#")]
    comments_after = [line for line in after.splitlines() if line.strip().startswith("#")]
    assert comments_after == comments_before


def test_nested_scanner_override_is_added(config_dir: Path) -> None:
    document = set_scanner_enabled(config_dir / "markets.yaml", "CXS002_VOLUME_SPIKE", False)
    document.write()
    parsed = yaml.safe_load((config_dir / "markets.yaml").read_text(encoding="utf-8"))
    assert parsed["scanner_overrides"]["CXS002_VOLUME_SPIKE"]["enabled"] is False
    # existing parameters survive
    assert parsed["scanner_overrides"]["CXS002_VOLUME_SPIKE"]["params"]["spike_multiplier"] == 3.0


def test_new_top_level_block_is_appended(tmp_path: Path) -> None:
    path = tmp_path / "app.yaml"
    path.write_text("environment: development\n", encoding="utf-8")
    document = YamlFile(path)
    document.set(["web", "port"], 4310)
    document.write()
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert parsed["web"]["port"] == 4310


def test_boolean_formatting(config_dir: Path) -> None:
    document = YamlFile(config_dir / "app.yaml")
    document.set(["web", "open_browser"], False)
    document.write()
    body = (config_dir / "app.yaml").read_text(encoding="utf-8")
    assert "open_browser: false" in body
    assert yaml.safe_load(body)["web"]["open_browser"] is False
