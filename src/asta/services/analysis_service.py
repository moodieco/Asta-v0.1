"""Analysis orchestration: scanners -> validation -> dedup -> persistence -> alerts."""

from __future__ import annotations

import time
from typing import List, Optional

from asta.core.event_bus import EventBus
from asta.core.scanner_manager import CycleReport, ScannerManager
from asta.core.signal_manager import SignalManager
from asta.core.signal_model import Market
from asta.services.data_service import DataService
from asta.utils.exceptions import AstaError
from asta.utils.logger import get_logger
from asta.utils.time_utils import utcnow


class AnalysisService:
    def __init__(
        self,
        scanner_manager: ScannerManager,
        signal_manager: SignalManager,
        data_service: DataService,
        event_bus: Optional[EventBus] = None,
    ):
        self.scanners = scanner_manager
        self.signals = signal_manager
        self.data = data_service
        self.events = event_bus or EventBus()
        self.logger = get_logger("asta.analysis")

    # -- inspection -------------------------------------------------------
    def enabled(self, market: Optional[Market] = None) -> list:
        return self.scanners.enabled(market)

    def all(self) -> list:
        return self.scanners.all()

    def inventory(self) -> list:
        return [scanner.describe() for scanner in self.scanners.all()]

    def __len__(self) -> int:
        return len(self.scanners)

    # -- execution --------------------------------------------------------
    def run_cycle(
        self,
        scanner_ids: Optional[List[str]] = None,
        markets: Optional[List[Market]] = None,
    ) -> CycleReport:
        report = CycleReport(started_at=utcnow())
        started = time.perf_counter()
        self.events.publish("cycle.started", markets=[m.value for m in markets or []])

        for scanner in self.scanners.select(scanner_ids=scanner_ids, markets=markets):
            if not scanner.enabled or not self.data.is_enabled(scanner.market):
                continue
            symbols = scanner.symbols or self.data.symbols(scanner.market)
            if not symbols:
                report.errors.append("{}: no symbols configured".format(scanner.id))
                continue
            report.scanners_run += 1

            for symbol in symbols:
                try:
                    context = self.data.build_context(scanner, symbol)
                    signals = scanner.scan(context)
                except AstaError as exc:
                    report.errors.append("{} {}: {}".format(scanner.id, symbol, exc))
                    self.events.publish(
                        "scan.failed", scanner_id=scanner.id, symbol=symbol, error=str(exc)
                    )
                    self.logger.warning(
                        "scan failed",
                        extra={"scanner_id": scanner.id, "symbol": symbol, "error": str(exc)},
                    )
                    continue
                except Exception as exc:  # noqa: BLE001 - never break the cycle
                    report.errors.append("{} {}: unexpected {}".format(scanner.id, symbol, exc))
                    self.logger.exception(
                        "unexpected scanner failure",
                        extra={"scanner_id": scanner.id, "symbol": symbol},
                    )
                    continue

                report.contexts_built += 1
                report.signals_detected += len(signals)
                if not signals:
                    continue

                for signal in signals:
                    self.events.publish(
                        "signal.detected",
                        scanner_id=signal.scanner_id,
                        market=signal.market.value,
                        symbol=signal.symbol,
                        signal_type=signal.signal_type.value,
                        confidence=signal.confidence,
                    )

                outcome = self.signals.process(signals)
                report.signals_accepted += len(outcome.accepted)
                report.signals_rejected += len(outcome.rejected)
                report.signals_delivered += outcome.delivered
                report.errors.extend(outcome.delivery_errors)

                for signal in outcome.accepted:
                    self.events.publish(
                        "signal.accepted",
                        scanner_id=signal.scanner_id,
                        market=signal.market.value,
                        symbol=signal.symbol,
                        signal_type=signal.signal_type.value,
                    )

        report.finished_at = utcnow()
        self.events.publish("cycle.completed", **report.to_dict())
        self.logger.info(
            "cycle finished",
            extra={
                "duration_s": round(time.perf_counter() - started, 2),
                "scanners": report.scanners_run,
                "detected": report.signals_detected,
                "accepted": report.signals_accepted,
                "errors": len(report.errors),
            },
        )
        return report
