import os

import pytest

from asta.config import AstaConfig, load_config
from asta.core.signal_model import Market
from asta.utils.exceptions import ConfigurationError

CONFIG_YAML = """
log_level: WARNING
storage:
  signal_history_path: ${SIGNALS_PATH}
markets:
  crypto:
    enabled: true
    symbols: [btcusdt, ethusdt]
  forex:
    enabled: false
    symbols: []
scanner_overrides:
  CXS002_VOLUME_SPIKE:
    timeframe: 5m
    params:
      spike_multiplier: 4.0
providers:
  oanda:
    api_token: ${OANDA_API_TOKEN}
"""


def write_config(tmp_path, text=CONFIG_YAML):
    path = tmp_path / "config" / "asta.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(text)
    return path


def test_load_config_expands_env_and_resolves_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNALS_PATH", str(tmp_path / "signals.jsonl"))
    monkeypatch.setenv("OANDA_API_TOKEN", "tok")
    path = write_config(tmp_path)

    config = load_config(str(path))
    assert config.log_level == "WARNING"
    assert config.markets["crypto"].normalized_symbols() == ["BTCUSDT", "ETHUSDT"]
    assert config.markets["forex"].enabled is False
    assert config.providers["oanda"]["api_token"] == "tok"
    assert config.resolve_path(config.storage.signal_history_path) == tmp_path / "signals.jsonl"
    assert config.scanner_overrides["CXS002_VOLUME_SPIKE"]["timeframe"] == "5m"


def test_missing_config_raises(tmp_path):
    with pytest.raises(ConfigurationError):
        load_config(str(tmp_path / "nope.yaml"))


def test_project_root_is_parent_of_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNALS_PATH", "data/signals.jsonl")
    monkeypatch.setenv("OANDA_API_TOKEN", "")
    path = write_config(tmp_path)
    config = load_config(str(path))
    assert config.project_root == tmp_path
    assert config.resolve_path("data/signals.jsonl") == tmp_path / "data" / "signals.jsonl"


def test_dry_run_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNALS_PATH", "data/signals.jsonl")
    monkeypatch.setenv("OANDA_API_TOKEN", "")
    monkeypatch.setenv("ASTA_DRY_RUN", "1")
    config = load_config(str(write_config(tmp_path)))
    assert config.dry_run is True


def test_defaults_are_sane():
    config = AstaConfig()
    assert config.scheduler.tick_seconds == 60
    assert config.validator.min_confidence < 0.5
    assert config.market_settings() == {}
