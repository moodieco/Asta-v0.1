"""Application wiring: config -> providers -> scanners -> pipeline -> alerts."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Dict, List, Optional

from asta.config import AstaConfig, load_config
from asta.core.deduplication import DeduplicationStore
from asta.core.market_manager import MarketManager
from asta.core.scanner_manager import CycleReport, ScannerManager
from asta.core.scanner_registry import ScannerRegistry
from asta.core.scanner_scheduler import ScannerScheduler
from asta.core.signal_manager import SignalManager
from asta.core.signal_model import Market
from asta.core.signal_validator import SignalValidator
from asta.integrations.discord.alert_manager import AlertManager
from asta.integrations.discord.channel_config import ChannelConfig
from asta.integrations.discord.discord_router import DiscordRouter
from asta.providers import build_providers
from asta.providers.base import MarketDataProvider
from asta.storage.cache import TTLCache
from asta.storage.signal_history import SignalHistory
from asta.utils.exceptions import AstaError
from asta.utils.logger import configure_logging, get_logger


class AstaApp:
    """Composition root. One instance == one running ASTA deployment."""

    def __init__(
        self,
        config: AstaConfig,
        registry: Optional[ScannerRegistry] = None,
        providers: Optional[Dict[Market, MarketDataProvider]] = None,
        alert_manager=None,
    ):
        self.config = config
        self.registry = registry
        self.providers = providers
        self._alert_manager_override = alert_manager
        self.logger = get_logger("asta.app")

        self.market_manager: Optional[MarketManager] = None
        self.signal_manager: Optional[SignalManager] = None
        self.scanner_manager: Optional[ScannerManager] = None
        self.scheduler: Optional[ScannerScheduler] = None
        self.history: Optional[SignalHistory] = None
        self.alert_manager = None

    # -- construction -----------------------------------------------------
    @classmethod
    def from_config(
        cls,
        path: Optional[str] = None,
        dry_run: Optional[bool] = None,
        registry: Optional[ScannerRegistry] = None,
        providers: Optional[Dict[Market, MarketDataProvider]] = None,
    ) -> "AstaApp":
        config = load_config(path)
        if dry_run is not None:
            config.dry_run = bool(dry_run)
        return cls(config, registry=registry, providers=providers)

    def build(self) -> "AstaApp":
        configure_logging(self.config.log_level)
        providers = self.providers or build_providers(self.config.providers)

        market_manager = MarketManager(providers, self.config.markets)
        history = SignalHistory(
            self.config.resolve_path(self.config.storage.signal_history_path),
            enabled=self.config.storage.enabled,
        )
        deduplication = DeduplicationStore(
            window_seconds=self.config.storage.dedup_window_seconds,
            cache=TTLCache(default_ttl=self.config.storage.dedup_window_seconds),
        )
        validator = SignalValidator(
            min_confidence=self.config.validator.min_confidence,
            max_age_seconds=self.config.validator.max_signal_age_seconds,
        )

        router = DiscordRouter(ChannelConfig.from_env(), dry_run=self.config.dry_run)
        alert_manager = self._alert_manager_override or AlertManager(router, dry_run=self.config.dry_run)
        signal_manager = SignalManager(
            validator=validator,
            deduplication=deduplication,
            history=history,
            alert_manager=alert_manager,
        )

        registry = self.registry or ScannerRegistry()
        if not registry.classes:
            registry.discover()
        configs = registry.load_configs()
        scanners = registry.build_all(configs, self.config.scanner_overrides)

        scanner_manager = ScannerManager(market_manager, signal_manager, scanners)
        scheduler = ScannerScheduler(
            scanner_manager,
            tick_seconds=self.config.scheduler.tick_seconds,
            respect_timeframe=self.config.scheduler.respect_timeframe,
        )

        self.market_manager = market_manager
        self.history = history
        self.alert_manager = alert_manager
        self.signal_manager = signal_manager
        self.registry = registry
        self.scanner_manager = scanner_manager
        self.scheduler = scheduler

        self.logger.info(
            "ASTA ready",
            extra={
                "environment": self.config.environment,
                "scanners": len(scanner_manager),
                "markets": [market.value for market in Market if market_manager.is_enabled(market)],
                "dry_run": self.config.dry_run,
                "webhooks": router.configured_markets(),
            },
        )
        for market in Market:
            provider = providers.get(market)
            if provider is not None and not provider.is_configured():
                self.logger.warning(
                    "provider not configured - market will be skipped",
                    extra={"market": market.value, "provider": provider.name},
                )
        return self

    # -- runtime ----------------------------------------------------------
    def require_built(self) -> ScannerManager:
        if self.scanner_manager is None:
            self.build()
        assert self.scanner_manager is not None
        return self.scanner_manager

    def run_once(
        self,
        markets: Optional[List[Market]] = None,
        scanner_ids: Optional[List[str]] = None,
    ) -> CycleReport:
        manager = self.require_built()
        return manager.run_cycle(scanner_ids=scanner_ids, markets=markets)

    async def run_forever(self, stop_event: Optional[asyncio.Event] = None) -> None:
        self.require_built()
        assert self.scheduler is not None
        await self.scheduler.run_forever(stop_event=stop_event)

    def run(self) -> None:
        try:
            asyncio.run(self.run_forever())
        except KeyboardInterrupt:  # pragma: no cover - interactive
            self.logger.info("interrupted, shutting down")

    def scanner_inventory(self) -> List[dict]:
        manager = self.require_built()
        return [scanner.describe() for scanner in manager.all()]

    def health(self) -> dict:
        manager = self.require_built()
        assert self.market_manager is not None
        return {
            "environment": self.config.environment,
            "dry_run": self.config.dry_run,
            "scanners": len(manager),
            "enabled_scanners": len(manager.enabled()),
            "providers": self.market_manager.health(),
            "webhooks": sorted(self.alert_manager.router.configured_markets()) if self.alert_manager else [],
            "signal_history": {
                "path": str(self.history.path) if self.history and self.history.path else None,
                "records": self.history.count() if self.history else 0,
            },
        }

    def close(self) -> None:
        for provider in (self.providers or {}).values():
            try:
                provider.close()
            except Exception:  # noqa: BLE001 - shutdown must not raise
                pass
        if self.alert_manager is not None and getattr(self.alert_manager, "router", None):
            try:
                self.alert_manager.router.client.close()
            except Exception:  # noqa: BLE001
                pass
