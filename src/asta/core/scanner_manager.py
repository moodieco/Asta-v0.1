"""Runs scanners over symbols and funnels the results into the signal pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from asta.core.scanner_base import ScannerBase
from asta.core.signal_model import Market, Signal
from asta.utils.exceptions import AstaError
from asta.utils.logger import get_logger
from asta.utils.time_utils import utcnow


@dataclass
class CycleReport:
    """Result of one scan cycle (one tick of the scheduler)."""

    started_at: datetime
    finished_at: Optional[datetime] = None
    scanners_run: int = 0
    contexts_built: int = 0
    signals_detected: int = 0
    signals_accepted: int = 0
    signals_rejected: int = 0
    signals_delivered: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if not self.finished_at:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, object]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": round(self.duration_seconds, 3),
            "scanners_run": self.scanners_run,
            "contexts_built": self.contexts_built,
            "signals_detected": self.signals_detected,
            "signals_accepted": self.signals_accepted,
            "signals_rejected": self.signals_rejected,
            "signals_delivered": self.signals_delivered,
            "errors": list(self.errors),
        }


class ScannerManager:
    """Holds scanner instances and executes them."""

    def __init__(self, market_manager, signal_manager, scanners: Optional[List[ScannerBase]] = None):
        self.market_manager = market_manager
        self.signal_manager = signal_manager
        self.logger = get_logger("asta.scanner_manager")
        self._scanners: Dict[str, ScannerBase] = {}
        for scanner in scanners or []:
            self.add(scanner)

    # -- collection management -------------------------------------------
    def add(self, scanner: ScannerBase) -> None:
        self._scanners[scanner.id] = scanner

    def remove(self, scanner_id: str) -> None:
        self._scanners.pop(scanner_id, None)

    def get(self, scanner_id: str) -> ScannerBase:
        return self._scanners[scanner_id]

    def all(self) -> List[ScannerBase]:
        return [self._scanners[key] for key in sorted(self._scanners)]

    def enabled(self, market: Optional[Market] = None) -> List[ScannerBase]:
        scanners = [s for s in self.all() if s.enabled]
        if market is not None:
            scanners = [s for s in scanners if s.market == market]
        return scanners

    def __len__(self) -> int:
        return len(self._scanners)

    # -- execution --------------------------------------------------------
    def run_scanner(self, scanner: ScannerBase, symbol: str) -> List[Signal]:
        context = self.market_manager.build_context(scanner, symbol)
        return scanner.scan(context)

    def run_cycle(
        self,
        scanner_ids: Optional[List[str]] = None,
        markets: Optional[List[Market]] = None,
    ) -> CycleReport:
        report = CycleReport(started_at=utcnow())
        started = time.perf_counter()

        scanners = self.all() if scanner_ids is None else [
            self._scanners[sid] for sid in scanner_ids if sid in self._scanners
        ]
        if markets:
            allowed = set(markets)
            scanners = [s for s in scanners if s.market in allowed]

        for scanner in scanners:
            if not scanner.enabled:
                continue
            if not self.market_manager.is_enabled(scanner.market):
                continue
            symbols = scanner.symbols or self.market_manager.symbols_for(scanner.market)
            if not symbols:
                report.errors.append("{}: no symbols configured".format(scanner.id))
                continue
            report.scanners_run += 1

            for symbol in symbols:
                try:
                    signals = self.run_scanner(scanner, symbol)
                except AstaError as exc:
                    report.errors.append("{} {}: {}".format(scanner.id, symbol, exc))
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

                outcome = self.signal_manager.process(signals)
                report.signals_accepted += len(outcome.accepted)
                report.signals_rejected += len(outcome.rejected)
                report.signals_delivered += outcome.delivered
                report.errors.extend(outcome.delivery_errors)

        report.finished_at = utcnow()
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
