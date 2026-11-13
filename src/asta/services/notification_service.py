"""Notification service: signal alerts plus labelled connectivity tests."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from asta.core.signal_model import Market, Signal, SignalType
from asta.integrations.discord.alert_manager import AlertManager
from asta.integrations.discord.channel_config import ChannelConfig
from asta.integrations.discord.client import DeliveryResult
from asta.integrations.discord.embed_builder import build_test_payload
from asta.utils.exceptions import AstaError
from asta.utils.logger import get_logger


class NotificationService:
    def __init__(
        self,
        alert_manager: AlertManager,
        channels: ChannelConfig,
        dry_run: bool = False,
    ):
        self.alert_manager = alert_manager
        self.channels = channels
        self.dry_run = bool(dry_run)
        self.logger = get_logger("asta.notifications")

    # -- pipeline hook ----------------------------------------------------
    def dispatch(self, signal: Signal) -> DeliveryResult:
        return self.alert_manager.dispatch(signal)

    def dispatch_many(self, signals: List[Signal]) -> List[DeliveryResult]:
        return [self.dispatch(signal) for signal in signals]

    # -- operator tools ---------------------------------------------------
    def send_test_alerts(self) -> List[Dict[str, object]]:
        results: List[Dict[str, object]] = []
        for market in Market:
            webhook = self.channels.webhook_for(market)
            if not webhook:
                continue
            if self.dry_run:
                results.append({"market": market.value, "ok": True, "dry_run": True})
                continue
            try:
                outcome = self.alert_manager.router.client.post(
                    webhook, build_test_payload(market, channel_label=self.channels.label_for(market))
                )
            except AstaError as exc:
                results.append({"market": market.value, "ok": False, "error": str(exc)})
                continue
            results.append(
                {
                    "market": market.value,
                    "ok": outcome.ok,
                    "status": outcome.status_code,
                    "attempts": outcome.attempts,
                    "error": outcome.error,
                }
            )
        return results

    def send_sample_alerts(
        self,
        symbols_for: Callable[[Market], List[str]],
        markets: Optional[List[Market]] = None,
    ) -> List[Dict[str, object]]:
        results: List[Dict[str, object]] = []
        for market in markets or list(Market):
            if not self.channels.has(market):
                continue
            symbols = symbols_for(market) or ["SAMPLE"]
            signal = Signal(
                scanner_id="{}_SAMPLE_ALERT".format(market.value.upper()[:2]),
                scanner_name="Sample Alert",
                market=market,
                symbol=symbols[0],
                timeframe="1d" if market is Market.STOCK else "1h",
                signal_type=SignalType.LONG,
                reason=(
                    "Sample signal card: this is what a real {} alert looks like — scanner id, "
                    "symbol, timeframe, confidence, reason and indicators. "
                    "No live scan produced this message.".format(market.label)
                ),
                confidence=0.76,
                price=100.0,
                strategy="Sample",
                indicators={"rsi": 38.4, "volume_ratio": 2.1},
                metadata={"sample": True},
            )
            try:
                outcome = self.alert_manager.router.route_sample(signal)
            except AstaError as exc:
                results.append({"market": market.value, "ok": False, "error": str(exc)})
                continue
            results.append(
                {
                    "market": market.value,
                    "ok": outcome.ok,
                    "status": outcome.status_code,
                    "error": outcome.error,
                }
            )
        return results

    def stats(self) -> Dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "configured_channels": [m.value for m in self.channels.configured_markets()],
            **self.alert_manager.stats(),
        }
