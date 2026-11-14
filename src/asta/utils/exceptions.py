"""Exception hierarchy for ASTA.

Everything raised by ASTA code derives from :class:`AstaError`, so the
scheduler and the signal manager can separate "expected" failures from bugs.
"""


class AstaError(Exception):
    """Base class for all ASTA errors."""

    def __init__(self, message: str, **context):
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:  # pragma: no cover - trivial
        if not self.context:
            return self.message
        details = ", ".join("{}={}".format(k, v) for k, v in sorted(self.context.items()))
        return "{} ({})".format(self.message, details)


class ConfigurationError(AstaError):
    """Invalid or missing configuration."""


class ProviderError(AstaError):
    """A market data provider failed (network, auth, bad payload)."""


class InsufficientDataError(AstaError):
    """Not enough candles to evaluate a scanner."""


class ScannerError(AstaError):
    """A scanner raised while evaluating a symbol."""


class SignalValidationError(AstaError):
    """A candidate signal did not survive validation."""


class DiscordError(AstaError):
    """Discord delivery failed."""
