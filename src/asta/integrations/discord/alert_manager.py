"""Alert manager: the only Discord-aware part of the signal pipeline."""

from __future__ import annotations

from typing import Iterable, List

from asta.core.signal_model import Signal
from asta.integrations.discord.client import DeliveryResult
from asta.integrations.discord.discord_router import DiscordRouter
from asta.utils.logger import get_logger


class AlertManager:
    def __init__(self, router: DiscordRouter, dry_run: bool = False):
        self.router = router
        self.dry_run = bool(dry_run or router.dry_run)
        self.logger = get_logger("asta.alerts")
        self._sent = 0
        self._failed = 0

    def dispatch(self, signal: Signal) -> DeliveryResult:
        result = self.router.route(signal)
        if result.ok:
            self._sent += 1
        else:
            self._failed += 1
            self.logger.error(
                "alert not delivered",
                extra={"signal": signal.summary(), "error": result.error},
            )
        return result

    def dispatch_many(self, signals: Iterable[Signal]) -> List[DeliveryResult]:
        return [self.dispatch(signal) for signal in signals]

    def stats(self) -> dict:
        return {"sent": self._sent, "failed": self._failed, "dry_run": self.dry_run}
