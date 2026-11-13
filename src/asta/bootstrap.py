"""Composition root: config -> providers -> services -> scheduler.

Nothing else constructs concrete collaborators; everything is wired here so
tests can swap one piece (a stub provider, a fake notifier).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from asta.config import AstaConfig, load_config
from asta.core.deduplication import DeduplicationStore
from asta.core.event_bus import Event, EventBus
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
from asta.integrations.sheets.sync import SheetSyncService, build_sheet_writer
from asta.providers import build_providers
from asta.providers.base import MarketDataProvider
from asta.services.analysis_service import AnalysisService
from asta.services.data_service import DataService
from asta.services.notification_service import NotificationService
from asta.storage import build_signal_history
from asta.storage.cache import TTLCache
from asta.utils.logger import configure_logging, get_logger


class AstaApp:
    """One instance == one running ASTA deployment."""

    def __init__(
        self,
        config: AstaConfig,
        registry: Optional[ScannerRegistry] = None,
        providers: Optional[Dict[Market, MarketDataProvider]] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.config = config
        self.registry = registry
        self.providers = providers
        self.event_bus = event_bus or EventBus()
        self.logger = get_logger("asta.app")

        self.market_manager: Optional[MarketManager] = None
        self.data_service: Optional[DataService] = None
        self.analysis: Optional[AnalysisService] = None
        self.notifications: Optional[NotificationService] = None
        self.sheet_sync: Optional[SheetSyncService] = None
        self.history = None
        self.scheduler: Optional[ScannerScheduler] = None

    # -- construction -----------------------------------------------------
    @classmethod
    def from_config(
        cls,
        config_dir: Optional[str] = None,
        dry_run: Optional[bool] = None,
        registry: Optional[ScannerRegistry] = None,
        providers: Optional[Dict[Market, MarketDataProvider]] = None,
        event_bus: Optional[EventBus] = None,
    ) -> "AstaApp":
        config = load_config(config_dir)
        if dry_run is not None:
            config.dry_run = bool(dry_run)
        return cls(config, registry=registry, providers=providers, event_bus=event_bus)

    def build(self) -> "AstaApp":
        self._configure_logging()
        providers = self.providers or build_providers(self.config.providers)

        market_manager = MarketManager(
            providers,
            self.config.markets,
            defaults=MarketManager.load_defaults(),
            universes=MarketManager.load_universes(),
        )
        data_service = DataService(market_manager)

        history = build_signal_history(
            backend=self.config.storage.backend,
            jsonl_path=self.config.resolve_path(self.config.storage.signal_history_path),
            sqlite_path=self.config.resolve_path(self.config.storage.sqlite_path),
            enabled=self.config.storage.enabled,
        )
        sheet_sync = self._build_sheet_sync(history)
        deduplication = DeduplicationStore(
            window_seconds=self.config.storage.dedup_window_seconds,
            cache=TTLCache(default_ttl=self.config.storage.dedup_window_seconds),
        )
        seeded = deduplication.warm_from_history(history.tail(1000))

        validator = SignalValidator(
            min_confidence=self.config.validator.min_confidence,
            max_age_seconds=self.config.validator.max_signal_age_seconds,
        )

        channels = ChannelConfig.from_env(channels=self.config.discord.channels)
        router = DiscordRouter(channels, dry_run=self.config.dry_run)
        alert_manager = AlertManager(router, dry_run=self.config.dry_run)
        notifications = NotificationService(alert_manager, channels, dry_run=self.config.dry_run)

        signal_manager = SignalManager(
            validator=validator,
            deduplication=deduplication,
            history=history,
            notifier=notifications,
        )

        registry = self.registry or ScannerRegistry()
        if not registry.classes:
            registry.discover()
        scanners = registry.build_all(registry.load_configs(), self.config.scanner_overrides)
        scanner_manager = ScannerManager(scanners)

        self._subscribe_event_logging()
        if sheet_sync is not None and self.config.sheets.auto_sync:
            self.event_bus.subscribe(
                "cycle.completed", lambda event: sheet_sync.sync_once()
            )
        analysis = AnalysisService(scanner_manager, signal_manager, data_service, self.event_bus)
        scheduler = ScannerScheduler(
            analysis,
            tick_seconds=self.config.scheduler.tick_seconds,
            respect_timeframe=self.config.scheduler.respect_timeframe,
        )

        self.market_manager = market_manager
        self.data_service = data_service
        self.analysis = analysis
        self.notifications = notifications
        self.history = history
        self.sheet_sync = sheet_sync
        self.registry = registry
        self.scheduler = scheduler

        self.logger.info(
            "ASTA ready",
            extra={
                "environment": self.config.environment,
                "scanners": len(scanner_manager),
                "markets": [m.value for m in Market if market_manager.is_enabled(m)],
                "dry_run": self.config.dry_run,
                "storage": self.config.storage.backend,
                "dedup_seeded": seeded,
                "webhooks": [m.value for m in channels.configured_markets()],
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

    def _build_sheet_sync(self, history) -> Optional[SheetSyncService]:
        if not self.config.sheets.enabled:
            return None
        writer = build_sheet_writer(self.config.sheets, self.config.project_root)
        return SheetSyncService(
            writer,
            history,
            self.config.resolve_path(self.config.sheets.state_path),
            batch_size=self.config.sheets.batch_size,
        )

    def _configure_logging(self) -> None:
        settings = self.config.logging
        log_file = settings.file
        configure_logging(
            level=settings.level,
            fmt=settings.format,
            logger_levels=settings.loggers,
            log_file=str(self.config.resolve_path(log_file)) if log_file else None,
            max_bytes=settings.max_bytes,
            backup_count=settings.backup_count,
            force=True,
        )

    def _subscribe_event_logging(self) -> None:
        def log_event(event: Event) -> None:
            level = self.logger.debug if event.name in ("cycle.started", "cycle.completed") else self.logger.info
            level("event", extra=event.to_dict())

        self.event_bus.subscribe("*", log_event)

    # -- runtime ----------------------------------------------------------
    def require_built(self) -> AnalysisService:
        if self.analysis is None:
            self.build()
        assert self.analysis is not None
        return self.analysis

    def run_once(
        self,
        markets: Optional[List[Market]] = None,
        scanner_ids: Optional[List[str]] = None,
    ) -> CycleReport:
        return self.require_built().run_cycle(scanner_ids=scanner_ids, markets=markets)

    async def run_forever(self, stop_event: Optional[asyncio.Event] = None) -> None:
        self.require_built()
        assert self.scheduler is not None
        await self.scheduler.run_forever(stop_event=stop_event)

    def run(self) -> None:
        try:
            asyncio.run(self.run_forever())
        except KeyboardInterrupt:  # pragma: no cover - interactive
            self.logger.info("interrupted, shutting down")

    # -- operator helpers -------------------------------------------------
    def send_test_alerts(self) -> List[Dict[str, object]]:
        self.require_built()
        assert self.notifications is not None
        return self.notifications.send_test_alerts()

    def send_sample_alerts(self) -> List[Dict[str, object]]:
        self.require_built()
        assert self.notifications is not None and self.data_service is not None
        enabled = [m for m in Market if self.data_service.is_enabled(m)]
        return self.notifications.send_sample_alerts(self.data_service.symbols, markets=enabled)

    def sync_sheet(self) -> Dict[str, Any]:
        """Export new signals to the configured spreadsheet."""
        self.require_built()
        if self.sheet_sync is None:
            return {"enabled": False, "appended": 0}
        return self.sheet_sync.sync_once()

    def scanner_inventory(self) -> List[dict]:
        return self.require_built().inventory()

    def health(self) -> dict:
        self.require_built()
        assert self.data_service is not None and self.history is not None
        return {
            "environment": self.config.environment,
            "dry_run": self.config.dry_run,
            "scanners": len(self.require_built()),
            "enabled_scanners": len(
                [s for s in self.require_built().enabled() if self.data_service.is_enabled(s.market)]
            ),
            "providers": self.data_service.health(),
            "webhooks": [m.value for m in self.notifications.channels.configured_markets()]
            if self.notifications
            else [],
            "storage": {
                "backend": self.config.storage.backend,
                "path": str(self.history.path) if getattr(self.history, "path", None) else None,
                "records": self.history.count(),
            },
            "data_cache": self.data_service.cache_stats(),
            "sheets": self.sheet_sync.status() if self.sheet_sync else {"enabled": False},
            "events": len(self.event_bus.history),
        }

    def close(self) -> None:
        for provider in (self.providers or {}).values():
            try:
                provider.close()
            except Exception:  # noqa: BLE001 - shutdown must not raise
                pass
        if self.sheet_sync is not None:
            self.sheet_sync.close()
        if self.notifications is not None:
            try:
                self.notifications.alert_manager.router.client.close()
            except Exception:  # noqa: BLE001
                pass
