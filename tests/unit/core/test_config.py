import pytest

from asta.config import load_config
from asta.utils.exceptions import ConfigurationError

APP = """
environment: test
dry_run: false
scheduler:
  tick_seconds: 30
storage:
  backend: ${STORAGE_BACKEND}
  signal_history_path: ${SIGNALS_PATH}
  sqlite_path: data/history/test.db
  dedup_window_seconds: 900
providers:
  oanda:
    api_token: ${OANDA_API_TOKEN}
"""

MARKETS = """
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
"""

LOGGING = """
level: DEBUG
format: json
file: data/logs/test.log
loggers:
  httpx: ERROR
"""

SHEETS = """
enabled: true
driver: csv
csv_path: data/history/export.csv
state_path: data/history/state.json
batch_size: 50
auto_sync: false
"""

DISCORD = """
username: ASTA-TEST
channels:
  crypto:
    env: DISCORD_WEBHOOK_CRYPTO
    label: "#cryptic-test"
  stock:
    env: DISCORD_WEBHOOK_STOCK
    label: "#stocky-test"
"""


def write_config_dir(
    tmp_path, app=APP, markets=MARKETS, logging_yaml=LOGGING, discord=DISCORD, sheets=SHEETS
):
    directory = tmp_path / "config"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "app.yaml").write_text(app)
    (directory / "markets.yaml").write_text(markets)
    (directory / "logging.yaml").write_text(logging_yaml)
    (directory / "discord.yaml").write_text(discord)
    (directory / "sheets.yaml").write_text(sheets)
    return directory


def test_merges_four_files_and_expands_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNALS_PATH", str(tmp_path / "signals.jsonl"))
    monkeypatch.setenv("STORAGE_BACKEND", "jsonl")
    monkeypatch.setenv("OANDA_API_TOKEN", "tok-123")
    directory = write_config_dir(tmp_path)

    config = load_config(str(directory), env_file=tmp_path / "missing.env")

    assert config.environment == "test"
    assert config.scheduler.tick_seconds == 30
    assert config.storage.dedup_window_seconds == 900
    assert config.storage.backend == "jsonl"
    assert config.resolve_path(config.storage.signal_history_path) == tmp_path / "signals.jsonl"
    assert config.providers["oanda"]["api_token"] == "tok-123"
    assert config.markets["crypto"].normalized_symbols() == ["BTCUSDT", "ETHUSDT"]
    assert config.markets["forex"].enabled is False
    assert config.scanner_overrides["CXS002_VOLUME_SPIKE"]["timeframe"] == "5m"
    assert config.logging.level == "DEBUG"
    assert config.logging.format == "json"
    assert config.logging.loggers["httpx"] == "ERROR"
    assert config.discord.username == "ASTA-TEST"
    assert config.webhook_env("crypto") == "DISCORD_WEBHOOK_CRYPTO"
    assert config.channel_label("crypto") == "#cryptic-test"
    assert config.project_root == tmp_path
    assert config.sheets.enabled is True
    assert config.sheets.driver == "csv"
    assert config.sheets.batch_size == 50
    assert config.sheets.auto_sync is False


def test_missing_config_dir_raises(tmp_path):
    with pytest.raises(ConfigurationError):
        load_config(str(tmp_path / "nope"))


def test_invalid_storage_backend_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNALS_PATH", "data/history/signals.jsonl")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("OANDA_API_TOKEN", "")
    directory = write_config_dir(tmp_path)
    with pytest.raises(ConfigurationError):
        load_config(str(directory), env_file=tmp_path / "missing.env")


def test_dry_run_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNALS_PATH", "data/history/signals.jsonl")
    monkeypatch.setenv("STORAGE_BACKEND", "jsonl")
    monkeypatch.setenv("OANDA_API_TOKEN", "")
    monkeypatch.setenv("ASTA_DRY_RUN", "1")
    directory = write_config_dir(tmp_path)
    config = load_config(str(directory), env_file=tmp_path / "missing.env")
    assert config.dry_run is True


def test_location_defaults_are_safe():
    from asta.config import AstaConfig

    config = AstaConfig()
    assert config.scheduler.tick_seconds == 60
    assert config.storage.backend == "jsonl"
    assert config.webhook_env("forex") == "DISCORD_WEBHOOK_FOREX"
    assert config.channel_label("forex") == "#forex-signals"
