"""Discord embed payloads for signals."""

from __future__ import annotations

from typing import Any, Dict

from asta.core.signal_model import Signal, SignalType
from asta.utils.time_utils import isoformat

LONG_COLOR = 0x2ECC71
SHORT_COLOR = 0xE74C3C
MARKET_EMOJI = {"forex": "💱", "crypto": "🪙", "stock": "📈"}


def format_price(value: float) -> str:
    abs_value = abs(float(value))
    if abs_value >= 1000:
        return "{:,.2f}".format(value)
    if abs_value >= 1:
        return "{:.4f}".format(value)
    if abs_value >= 0.01:
        return "{:.5f}".format(value)
    return "{:.8f}".format(value)


def build_signal_embed(signal: Signal) -> Dict[str, Any]:
    color = LONG_COLOR if signal.signal_type is SignalType.LONG else SHORT_COLOR
    emoji = MARKET_EMOJI.get(signal.market.value, "📊")

    title = "{} {} · {} · {}".format(
        signal.signal_type.emoji, signal.signal_type.label, signal.symbol, signal.timeframe.upper()
    )

    fields = [
        {"name": "Market", "value": "{} {}".format(emoji, signal.market.label), "inline": True},
        {"name": "Scanner", "value": signal.scanner_id, "inline": True},
        {"name": "Strategy", "value": signal.strategy or signal.scanner_name, "inline": True},
        {"name": "Confidence", "value": "{:.0f}%".format(signal.confidence * 100), "inline": True},
    ]
    if signal.price is not None:
        fields.append({"name": "Price", "value": format_price(signal.price), "inline": True})
    fields.append({"name": "Time", "value": isoformat(signal.timestamp), "inline": True})

    if signal.indicators:
        rendered = ", ".join(
            "{}={}".format(key, _short_number(value))
            for key, value in list(signal.indicators.items())[:6]
        )
        fields.append({"name": "Indicators", "value": rendered[:1024], "inline": False})

    return {
        "title": title[:256],
        "description": signal.reason[:4096],
        "color": color,
        "fields": fields,
        "footer": {
            "text": "ASTA V0.1 · {} · {}".format(signal.scanner_name, signal.scanner_id)[:2048]
        },
        "timestamp": isoformat(signal.timestamp),
    }


def build_payload(signal: Signal, username: str = "ASTA") -> Dict[str, Any]:
    return {"username": username, "embeds": [build_signal_embed(signal)]}


def _short_number(value: float) -> str:
    value = float(value)
    if value == int(value):
        return str(int(value))
    if abs(value) >= 100:
        return "{:.1f}".format(value)
    return "{:.3f}".format(value)
