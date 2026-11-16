"""Configuration loading.

Four files, one model::

    config/app.yaml       runtime, scheduler, validator, storage, providers
    config/markets.yaml   enabled markets, symbol universe, scanner overrides
    config/logging.yaml   logging level/format/file
    config/discord.yaml   channel -> webhook env var mapping

Environment variables are expanded (``${VAR}``) and ``.env`` is loaded first, so
secrets never live in YAML.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from asta.core.market_manager import MarketSettings
from asta.utils.exceptions import ConfigurationError
from asta.utils.time_utils import normalize_timeframe

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")
DEFAULT_WEBHOOK_ENV = {
    "forex": "DISCORD_WEBHOOK_FOREX",
    "crypto": "DISCORD_WEBHOOK_CRYPTO",
    "stock": "DISCORD_WEBHOOK_STOCK",
}


class SchedulerSettings(BaseModel):
    tick_seconds: int = 60
    respect_timeframe: bool = True

    @field_validator("tick_seconds")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("tick_seconds must be positive")
        return value


class ValidatorSettings(BaseModel):
    min_confidence: float = 0.35
    max_signal_age_seconds: int = 3600
    require_levels: bool = True


class StorageSettings(BaseModel):
    backend: str = "jsonl"
    signal_history_path: str = "data/history/signals.jsonl"
    sqlite_path: str = "data/history/asta.db"
    dedup_window_seconds: int = 3600
    enabled: bool = True

    @field_validator("backend")
    @classmethod
    def _known_backend(cls, value: str) -> str:
        backend = str(value).strip().lower()
        if backend not in ("jsonl", "sqlite"):
            raise ValueError("storage.backend must be 'jsonl' or 'sqlite'")
        return backend


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = "text"
    file: Optional[str] = None
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 3
    loggers: Dict[str, str] = Field(default_factory=dict)

    @field_validator("format")
    @classmethod
    def _known_format(cls, value: str) -> str:
        fmt = str(value).strip().lower()
        if fmt not in ("text", "json"):
            raise ValueError("logging.format must be 'text' or 'json'")
        return fmt


class WebSettings(BaseModel):
    """Local dashboard listener.

    ``host`` is the address shown in URLs; ``bind`` is the address the socket
    actually listens on. ``bind: 0.0.0.0`` lets other devices on the LAN reach
    the dashboard — those remote requests are gated by the share tokens (see
    ``asta.web.share``), while loopback stays open for the machine owner.
    """

    host: str = "127.0.0.1"
    port: int = 4310
    open_browser: bool = True
    bind: str = "127.0.0.1"

    @field_validator("port")
    @classmethod
    def _valid_port(cls, value: int) -> int:
        if not (1 <= int(value) <= 65535):
            raise ValueError("web.port must be between 1 and 65535")
        return int(value)

    @field_validator("host")
    @classmethod
    def _known_host(cls, value: str) -> str:
        host = str(value).strip() or "127.0.0.1"
        if host not in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
            raise ValueError("web.host must be a loopback address or 0.0.0.0")
        return host

    @field_validator("bind")
    @classmethod
    def _known_bind(cls, value: str) -> str:
        bind = str(value).strip() or "127.0.0.1"
        if bind not in ("127.0.0.1", "0.0.0.0"):
            raise ValueError("web.bind must be '127.0.0.1' or '0.0.0.0'")
        return bind


class SetupSettings(BaseModel):
    """Quick-setup bookkeeping (never holds a secret - those live in .env)."""

    state_path: str = "config/setup_state.json"


class DiscordChannelSettings(BaseModel):
    env: str
    label: str = ""


class DiscordSettings(BaseModel):
    username: str = "ASTA"
    channels: Dict[str, DiscordChannelSettings] = Field(default_factory=dict)

    @classmethod
    def default(cls) -> "DiscordSettings":
        return cls(
            channels={
                market: DiscordChannelSettings(env=env, label="#{}-signals".format(market))
                for market, env in DEFAULT_WEBHOOK_ENV.items()
            }
        )


class AstaConfig(BaseModel):
    environment: str = "development"
    dry_run: bool = False
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    validator: ValidatorSettings = Field(default_factory=ValidatorSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    setup: SetupSettings = Field(default_factory=SetupSettings)
    providers: Dict[str, Any] = Field(default_factory=dict)
    markets: Dict[str, MarketSettings] = Field(default_factory=dict)
    scanner_overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    config_dir: Optional[str] = None

    @property
    def source_path(self) -> Optional[str]:
        if not self.config_dir:
            return None
        app = Path(self.config_dir) / "app.yaml"
        return str(app) if app.exists() else None

    @property
    def project_root(self) -> Path:
        if self.config_dir:
            return Path(self.config_dir).resolve().parent
        return Path.cwd()

    def resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        # Hosted deploys mount a volume outside the checkout; ``data/...`` then
        # resolves under ASTA_DATA_DIR so history, scanner library and the alert
        # log survive a redeploy.
        data_root = (os.environ.get("ASTA_DATA_DIR") or "").strip()
        if data_root and path.parts and path.parts[0] == "data":
            return Path(data_root).expanduser() / Path(*path.parts[1:])
        return self.project_root / path

    def market_settings(self) -> Dict[str, MarketSettings]:
        return dict(self.markets)

    def webhook_env(self, market: str) -> str:
        channel = self.discord.channels.get(market)
        return channel.env if channel else DEFAULT_WEBHOOK_ENV.get(market, "")

    def channel_label(self, market: str) -> str:
        channel = self.discord.channels.get(market)
        return channel.label if channel and channel.label else "#{}-signals".format(market)


def load_dotenv(path: Optional[Path] = None, override: bool = False) -> Dict[str, str]:
    """Tiny ``.env`` reader (KEY=VALUE, ``#`` comments). No dependency needed."""
    env_path = Path(path) if path else Path.cwd() / ".env"
    loaded: Dict[str, str] = {}
    if not env_path.exists():
        return loaded
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda match: os.environ.get(match.group(1), ""), value)
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    return value


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError("invalid YAML in {}: {}".format(path, exc)) from exc
    if not isinstance(data, dict):
        raise ConfigurationError("{} must contain a mapping".format(path))
    return data


def _coerce_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def load_config(
    config_dir: Optional[str] = None,
    env_file: Optional[Path] = None,
    require: bool = True,
) -> AstaConfig:
    """Load the four config files and merge them into :class:`AstaConfig`."""
    load_dotenv(env_file)
    raw_dir = config_dir or os.getenv("ASTA_CONFIG_DIR") or "config"
    directory = Path(raw_dir).expanduser()
    if not directory.is_absolute():
        directory = Path.cwd() / directory
    if not directory.is_dir():
        if require:
            raise ConfigurationError("config directory not found: {}".format(directory))
        return AstaConfig()

    app = _read_yaml(directory / "app.yaml")
    markets = _read_yaml(directory / "markets.yaml")
    logging_cfg = _read_yaml(directory / "logging.yaml")
    discord_cfg = _read_yaml(directory / "discord.yaml")

    merged: Dict[str, Any] = dict(app)
    merged["markets"] = {
        str(key).lower(): value for key, value in (markets.get("markets") or {}).items()
    }
    merged["scanner_overrides"] = markets.get("scanner_overrides") or {}
    if logging_cfg:
        merged["logging"] = logging_cfg
    if discord_cfg:
        merged["discord"] = discord_cfg

    merged = _expand_env(merged)
    if os.getenv("ASTA_LOG_LEVEL"):
        merged.setdefault("logging", {})
        merged["logging"] = {**merged["logging"], "level": os.environ["ASTA_LOG_LEVEL"]}
    if os.getenv("ASTA_DRY_RUN") and _coerce_bool(os.environ["ASTA_DRY_RUN"]):
        merged["dry_run"] = True

    try:
        config = AstaConfig(**merged)
    except Exception as exc:  # noqa: BLE001 - surface pydantic errors
        raise ConfigurationError("invalid config in {}: {}".format(directory, exc)) from exc
    config.config_dir = str(directory)
    return config


def validate_scanner_timeframes(config: AstaConfig) -> List[str]:
    """Return scanner ids whose overridden timeframe is invalid (defensive)."""
    bad: List[str] = []
    for scanner_id, overrides in (config.scanner_overrides or {}).items():
        timeframe = overrides.get("timeframe")
        if timeframe is None:
            continue
        try:
            normalize_timeframe(str(timeframe))
        except ValueError:
            bad.append(scanner_id)
    return bad
