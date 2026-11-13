"""Timeframe parsing and UTC time helpers."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

UTC = timezone.utc

TIMEFRAME_SECONDS: Dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
    "1w": 604800,
}

#: Aliases accepted from config files / scanner ids.
_TIMEFRAME_ALIASES: Dict[str, str] = {
    "m1": "1m",
    "m5": "5m",
    "m15": "15m",
    "m30": "30m",
    "h1": "1h",
    "h4": "4h",
    "d1": "1d",
    "w1": "1w",
    "60m": "1h",
    "240m": "4h",
}


def utcnow() -> datetime:
    """Timezone-aware current time."""
    return datetime.now(UTC)


def normalize_timeframe(timeframe: str) -> str:
    """Return the canonical timeframe string (``H1`` -> ``1h``)."""
    if not timeframe:
        raise ValueError("timeframe must not be empty")
    key = str(timeframe).strip().lower()
    key = _TIMEFRAME_ALIASES.get(key, key)
    if key not in TIMEFRAME_SECONDS:
        raise ValueError(
            "unsupported timeframe {!r}; supported: {}".format(timeframe, ", ".join(sorted(TIMEFRAME_SECONDS)))
        )
    return key


def timeframe_to_seconds(timeframe: str) -> int:
    return TIMEFRAME_SECONDS[normalize_timeframe(timeframe)]


def timeframe_to_delta(timeframe: str) -> timedelta:
    return timedelta(seconds=timeframe_to_seconds(timeframe))


def ensure_utc(value: datetime) -> datetime:
    """Attach UTC to naive datetimes (market data is always UTC in ASTA)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_stale(timestamp: datetime, max_age_seconds: int, now: datetime = None) -> bool:
    now = now or utcnow()
    age = (now - ensure_utc(timestamp)).total_seconds()
    return age > max_age_seconds or age < -60  # allow 60s clock skew


def short_datetime(timestamp: datetime) -> str:
    """Compact display form: ``2026-11-13 22:17`` (UTC, minute precision)."""
    return ensure_utc(timestamp).strftime("%Y-%m-%d %H:%M")


def isoformat(timestamp: datetime) -> str:
    return ensure_utc(timestamp).isoformat().replace("+00:00", "Z")


def human_age(timestamp: datetime, now: datetime = None) -> str:
    now = now or utcnow()
    seconds = int((now - ensure_utc(timestamp)).total_seconds())
    if seconds < 60:
        return "{}s ago".format(max(seconds, 0))
    if seconds < 3600:
        return "{}m ago".format(seconds // 60)
    if seconds < 86400:
        return "{}h ago".format(seconds // 3600)
    return "{}d ago".format(seconds // 86400)


def trading_bucket(timestamp: datetime, timeframe: str) -> Tuple[datetime, datetime]:
    """Return (start, end) of the candle bucket containing ``timestamp``."""
    seconds = timeframe_to_seconds(timeframe)
    stamp = int(ensure_utc(timestamp).timestamp())
    start = stamp - (stamp % seconds)
    return datetime.fromtimestamp(start, tz=UTC), datetime.fromtimestamp(start + seconds, tz=UTC)


def parse_datetime(value: str) -> datetime:
    """Parse the ISO timestamps returned by OANDA / Yahoo into aware UTC."""
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    # OANDA returns nanosecond precision which fromisoformat rejects on 3.9/3.10.
    if "." in raw:
        head, _, tail = raw.partition(".")
        digits = ""
        rest = ""
        for index, char in enumerate(tail):
            if char.isdigit():
                digits += char
            else:
                rest = tail[index:]
                break
        raw = head + "." + (digits + "000000")[:6] + rest
    parsed = datetime.fromisoformat(raw)
    return ensure_utc(parsed)
