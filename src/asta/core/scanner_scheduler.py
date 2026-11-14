"""Time based orchestration for scanner cycles.

The pipeline itself is synchronous (providers, Discord, storage all use plain
blocking IO). The scheduler is the only async component: it ticks on a fixed
interval and runs each cycle in a worker thread so one slow exchange request
never blocks the event loop.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Optional

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_manager import CycleReport
from asta.utils.logger import get_logger
from asta.utils.time_utils import timeframe_to_seconds, utcnow


class ScannerScheduler:
    def __init__(
        self,
        manager,
        tick_seconds: int = 60,
        respect_timeframe: bool = True,
        logger=None,
    ):
        if tick_seconds <= 0:
            raise ValueError("tick_seconds must be positive")
        self.manager = manager
        self.tick_seconds = int(tick_seconds)
        self.respect_timeframe = respect_timeframe
        self.logger = logger or get_logger("asta.scheduler")
        self._last_run: Dict[str, float] = {}
        self._cycles = 0
        self.last_cycle_at: Optional[str] = None

    @property
    def cycles(self) -> int:
        """Completed cycles - surfaced by the dashboard status endpoint."""
        return self._cycles

    # -- due calculation --------------------------------------------------
    def _interval_for(self, scanner: ScannerBase) -> float:
        """How often a scanner should run.

        Half the timeframe, floored at the tick interval: on ``1h`` candles
        there is no point re-scanning every minute.
        """
        if not self.respect_timeframe:
            return float(self.tick_seconds)
        try:
            half = timeframe_to_seconds(scanner.timeframe) / 2.0
        except ValueError:
            half = float(self.tick_seconds)
        return max(float(self.tick_seconds), half)

    def due_scanners(self, now: Optional[float] = None) -> List[str]:
        now = time.monotonic() if now is None else now
        due: List[str] = []
        for scanner in self.manager.enabled():
            last = self._last_run.get(scanner.id)
            if last is None or (now - last) >= self._interval_for(scanner):
                due.append(scanner.id)
        return due

    def mark_ran(self, scanner_ids: List[str], now: Optional[float] = None) -> None:
        now = time.monotonic() if now is None else now
        for scanner_id in scanner_ids:
            self._last_run[scanner_id] = now

    # -- cycles -----------------------------------------------------------
    async def run_once(self) -> CycleReport:
        scanner_ids = self.due_scanners()
        if not scanner_ids:
            self.logger.debug("nothing due this tick")
            return CycleReport(started_at=utcnow(), finished_at=utcnow())
        self.mark_ran(scanner_ids)
        loop = asyncio.get_running_loop()
        report = await loop.run_in_executor(None, self.manager.run_cycle, scanner_ids)
        self._cycles += 1
        self.last_cycle_at = utcnow().isoformat()
        return report

    async def run_forever(self, stop_event: Optional[asyncio.Event] = None, max_cycles: Optional[int] = None) -> None:
        stop_event = stop_event or asyncio.Event()
        self.logger.info(
            "scheduler started",
            extra={"tick_seconds": self.tick_seconds, "scanners": len(self.manager)},
        )
        try:
            while not stop_event.is_set():
                try:
                    await self.run_once()
                except Exception:  # noqa: BLE001 - keep the loop alive
                    self.logger.exception("cycle crashed")
                if max_cycles is not None and self._cycles >= max_cycles:
                    break
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.tick_seconds)
                except asyncio.TimeoutError:
                    continue
        finally:
            self.logger.info("scheduler stopped", extra={"cycles": self._cycles})
