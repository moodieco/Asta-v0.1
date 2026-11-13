"""Historical replay: run a scanner over past candles and persist the signals.

Used by ``scripts/backfill_history.py`` and available for future backtests. The
replay is deliberately identical to the live path: same scanner code, same
validator, same risk levels, same dedup window — only the clock is historical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from asta.core.risk import outcome_for_signal
from asta.core.scanner_base import ScannerBase
from asta.core.signal_model import Candle, ScanContext, Signal
from asta.core.signal_validator import SignalValidator
from asta.storage.repositories.signal_repository import SignalRepository
from asta.utils.exceptions import AstaError
from asta.utils.logger import get_logger
from asta.utils.time_utils import timeframe_to_seconds

WINDOW_FLOOR = 10


@dataclass
class ReplayStats:
    scanner_id: str
    symbol: str
    timeframe: str
    candles: int
    raw: int = 0
    saved: int = 0
    rejected: int = 0
    outcomes: Dict[str, int] = field(default_factory=dict)


def _dedup_seconds(timeframe: str, max_window: Optional[int] = None) -> float:
    """Two candles of cooldown; ``max_window`` applies the live cap when given."""
    try:
        window = max(timeframe_to_seconds(timeframe) * 2, 60)
    except ValueError:
        window = max_window or 3600
    return float(min(window, max_window) if max_window else window)


def replay_scanner(
    scanner: ScannerBase,
    symbol: str,
    candles: List[Candle],
    validator: Optional[SignalValidator] = None,
    source: str = "backfill",
    dedup_seconds: Optional[int] = None,
) -> List[Signal]:
    """Slide a candle window over history and return validated, deduplicated signals."""
    validator = validator or SignalValidator()
    window = max(scanner.min_candles, WINDOW_FLOOR)
    if len(candles) <= window:
        return []

    dedup_window = float(dedup_seconds or _dedup_seconds(scanner.timeframe))
    last_seen: Dict[str, Candle] = {}
    signals: List[Signal] = []
    logger = get_logger("asta.backtest")

    for index in range(window - 1, len(candles)):
        context = ScanContext(
            market=scanner.market,
            symbol=symbol,
            timeframe=scanner.timeframe,
            candles=candles[index - window + 1 : index + 1],
            scanner_id=scanner.id,
            now=candles[index].timestamp,
        )
        try:
            found = scanner.scan(context)
        except AstaError as exc:
            logger.debug("replay skip", extra={"scanner_id": scanner.id, "error": str(exc)})
            continue
        for signal in found:
            signal = signal.model_copy(update={"source": source})
            # validate against the signal's own clock: otherwise every historical
            # signal would be rejected as "stale" by the live age check
            if not validator.validate(signal, now=signal.timestamp).valid:
                continue
            key = signal.dedup_key
            previous = last_seen.get(key)
            if previous is not None and (
                signal.timestamp - previous.timestamp
            ).total_seconds() < dedup_window:
                continue
            last_seen[key] = signal
            signals.append(signal)
    return signals


def backfill_scanner(
    scanner: ScannerBase,
    symbol: str,
    candles: List[Candle],
    repository: SignalRepository,
    validator: Optional[SignalValidator] = None,
    source: str = "backfill",
    dedup_seconds: Optional[int] = None,
) -> ReplayStats:
    """Persist replayed signals and immediately score them against later candles."""
    validator = validator or SignalValidator()
    stats = ReplayStats(
        scanner_id=scanner.id,
        symbol=symbol,
        timeframe=scanner.timeframe,
        candles=len(candles),
    )
    signals = replay_scanner(
        scanner, symbol, candles, validator, source=source, dedup_seconds=dedup_seconds
    )
    stats.raw = len(signals)

    for signal in signals:
        if not repository.save(signal):
            stats.rejected += 1
            continue
        stats.saved += 1
        if signal.stop_loss is None or signal.take_profit is None or signal.price is None:
            continue
        later = [candle for candle in candles if candle.timestamp > signal.timestamp]
        outcome = outcome_for_signal(
            signal.signal_type.value,
            signal.price,
            signal.stop_loss,
            signal.take_profit,
            later,
            signal.expires_at,
        )
        stats.outcomes[outcome["status"]] = stats.outcomes.get(outcome["status"], 0) + 1
        if outcome["status"] != "open":
            repository.update_outcome(
                signal.signal_id,
                outcome["status"],
                outcome["closed_at"],
                outcome["realized_r"],
                outcome["bars_held"],
            )
    return stats
