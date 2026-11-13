"""Scanner collection and cycle reporting.

Running scanners used to live here; orchestration now belongs to
:class:`asta.services.analysis_service.AnalysisService`. This class only owns
the scanner instances and the results contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from asta.core.scanner_base import ScannerBase
from asta.core.signal_model import Market
from asta.utils.logger import get_logger
from asta.utils.time_utils import utcnow


@dataclass
class CycleReport:
    """Result of one scan cycle (one tick of the scheduler)."""

    started_at: datetime = field(default_factory=utcnow)
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
    """Holds scanner instances, filters them, and reports what is configured."""

    def __init__(self, scanners: Optional[List[ScannerBase]] = None):
        self.logger = get_logger("asta.scanner_manager")
        self._scanners: Dict[str, ScannerBase] = {}
        for scanner in scanners or []:
            self.add(scanner)

    def add(self, scanner: ScannerBase) -> None:
        self._scanners[scanner.id] = scanner

    def remove(self, scanner_id: str) -> None:
        self._scanners.pop(scanner_id, None)

    def get(self, scanner_id: str) -> ScannerBase:
        return self._scanners[scanner_id]

    def all(self) -> List[ScannerBase]:
        return [self._scanners[key] for key in sorted(self._scanners)]

    def enabled(self, market: Optional[Market] = None) -> List[ScannerBase]:
        scanners = [scanner for scanner in self.all() if scanner.enabled]
        if market is not None:
            scanners = [scanner for scanner in scanners if scanner.market == market]
        return scanners

    def select(
        self, scanner_ids: Optional[List[str]] = None, markets: Optional[List[Market]] = None
    ) -> List[ScannerBase]:
        scanners = self.all() if scanner_ids is None else [
            self._scanners[sid] for sid in scanner_ids if sid in self._scanners
        ]
        if markets:
            allowed = set(markets)
            scanners = [scanner for scanner in scanners if scanner.market in allowed]
        return scanners

    def __len__(self) -> int:
        return len(self._scanners)
