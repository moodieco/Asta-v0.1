"""Configuration loading: YAML + .env + ``${VAR}`` expansion."""

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


class StorageSettings(BaseModel):
    signal_history_path: str = "data/signal_history.jsonl"
    dedup_window_seconds: int = 3600
    enabled: bool = True


class AstaConfig(BaseModel):
    environment: str = "development"
    log_level: str = "INFO"
    dry_run: bool = False
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    validator: ValidatorSettings = Field(default_factory=ValidatorSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    providers: Dict[str, Any] = Field(default_factory=dict)
    markets: Dict[str, MarketSettings] = Field(default_factory=dict)
    scanner_overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    source_path: Optional[str] = None

    @property
    def project_root(self) -> Path:
        if self.source_path:
            path = Path(self.source_path).resolve()
            return path.parent.parent if path.parent.name == "config" else path.parent
        return Path.cwd()

    def resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.project_root / path

    def market_settings(self) -> Dict[str, MarketSettings]:
        return dict(self.markets)


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


def _coerce_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def load_config(path: Optional[str] = None, env_file: Optional[Path] = None) -> AstaConfig:
    """Load ``config/asta.yaml`` with environment overrides."""
    load_dotenv(env_file)
    raw_path = path or os.getenv("ASTA_CONFIG") or "config/asta.yaml"
    resolved = Path(raw_path).expanduser()
    if not resolved.is_absolute():
        resolved = Path.cwd() / resolved
    if not resolved.exists():
        raise ConfigurationError("config file not found: {}".format(resolved))

    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError("invalid YAML in {}: {}".format(resolved, exc)) from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("config root must be a mapping")

    raw = _expand_env(raw)
    # Runtime overrides win over the file.
    if os.getenv("ASTA_LOG_LEVEL"):
        raw["log_level"] = os.environ["ASTA_LOG_LEVEL"]
    if os.getenv("ASTA_DRY_RUN") and _coerce_bool(os.environ["ASTA_DRY_RUN"]):
        raw["dry_run"] = True
    if "markets" in raw:
        raw["markets"] = {
            str(key).lower(): value for key, value in (raw.get("markets") or {}).items()
        }

    try:
        config = AstaConfig(**raw)
    except Exception as exc:  # noqa: BLE001 - pydantic error surface
        raise ConfigurationError("invalid config {}: {}".format(resolved, exc)) from exc
    config.source_path = str(resolved)
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
