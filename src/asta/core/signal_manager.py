"""Signal pipeline: validate -> deduplicate -> persist -> notify."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from asta.core.deduplication import DeduplicationStore
from asta.core.signal_model import Signal
from asta.core.signal_validator import SignalValidator
from asta.storage.signal_history import SignalHistory
from asta.utils.exceptions import DiscordError
from asta.utils.logger import get_logger


@dataclass
class ProcessOutcome:
    accepted: List[Signal] = field(default_factory=list)
    rejected: List[Tuple[Signal, str]] = field(default_factory=list)
    delivered: int = 0
    delivery_errors: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.accepted) + len(self.rejected)


class SignalManager:
    def __init__(
        self,
        validator: SignalValidator,
        deduplication: DeduplicationStore,
        history: Optional[SignalHistory] = None,
        notifier=None,
        logger=None,
    ):
        self.validator = validator
        self.deduplication = deduplication
        self.history = history
        self.notifier = notifier
        self.logger = logger or get_logger("asta.signal_manager")
        self._accepted_total = 0
        self._rejected_total = 0

    def process(self, signals: List[Signal]) -> ProcessOutcome:
        outcome = ProcessOutcome()
        for signal in signals:
            validation = self.validator.validate(signal)
            if not validation.valid:
                outcome.rejected.append((signal, validation.reason))
                self._rejected_total += 1
                self.logger.warning(
                    "signal rejected",
                    extra={"signal": signal.summary(), "reason": validation.reason},
                )
                continue

            is_new, remaining = self.deduplication.check_and_register(signal)
            if not is_new:
                outcome.rejected.append(
                    (signal, "duplicate ({}s left in window)".format(int(remaining or 0)))
                )
                self._rejected_total += 1
                self.logger.info("signal deduplicated", extra={"signal": signal.summary()})
                continue

            outcome.accepted.append(signal)
            self._accepted_total += 1
            if self.history is not None:
                try:
                    self.history.append(signal)
                except OSError as exc:
                    self.logger.error("failed to persist signal", extra={"error": str(exc)})

            if self.notifier is not None:
                try:
                    result = self.notifier.dispatch(signal)
                    if getattr(result, "ok", False) or getattr(result, "dry_run", False):
                        outcome.delivered += 1
                    else:
                        outcome.delivery_errors.append(
                            "{} delivery failed: {}".format(signal.summary(), getattr(result, "error", "unknown"))
                        )
                except DiscordError as exc:
                    outcome.delivery_errors.append(str(exc))
                    self.logger.error("notification failed", extra={"error": str(exc)})

        return outcome

    def stats(self) -> dict:
        return {
            "accepted_total": self._accepted_total,
            "rejected_total": self._rejected_total,
            "dedup_cache_size": self.deduplication.size(),
        }
