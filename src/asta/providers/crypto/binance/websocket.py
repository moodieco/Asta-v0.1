"""Optional Binance websocket stream (V0.2 realtime path).

REST polling is enough for V0.1, but the stream is wired here so the data
service can switch later without changing scanner code. Parsing is a pure
function and is unit tested; the socket itself is exercised only in production.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from asta.core.signal_model import Candle
from asta.providers.crypto.binance.client import BinanceClient


@dataclass(frozen=True)
class KlineEvent:
    symbol: str
    interval: str
    candle: Candle
    closed: bool


def parse_kline_message(payload: Union[str, Dict[str, Any]]) -> Optional[KlineEvent]:
    """Turn a ``kline`` stream message into a :class:`KlineEvent`.

    Returns ``None`` for frames that are not kline events.
    """
    data: Any = payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    if "data" in data and isinstance(data["data"], dict):
        data = data["data"]
    if data.get("e") != "kline":
        return None
    kline = data.get("k") or {}
    try:
        candle = Candle(
            timestamp=datetime.fromtimestamp(int(kline["t"]) / 1000, tz=timezone.utc),
            open=float(kline["o"]),
            high=float(kline["h"]),
            low=float(kline["l"]),
            close=float(kline["c"]),
            volume=float(kline["v"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    return KlineEvent(
        symbol=str(data.get("s", "")).upper(),
        interval=str(kline.get("i", "")),
        candle=candle,
        closed=bool(kline.get("x", False)),
    )


async def stream_klines(
    symbols: List[str],
    interval: str = "1m",
    base: str = "wss://stream.binance.com:9443",
    max_events: Optional[int] = None,
) -> AsyncIterator[KlineEvent]:
    """Yield kline events. Requires the optional ``websockets`` dependency."""
    try:
        import websockets  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "websocket streaming needs the optional dependency: pip install 'asta[stream]'"
        ) from exc

    url = BinanceClient.stream_url(symbols, interval=interval, base=base)
    delivered = 0
    async with websockets.connect(url) as socket:  # pragma: no branch - network path
        async for message in socket:
            event = parse_kline_message(message)
            if event is None:
                continue
            yield event
            delivered += 1
            if max_events is not None and delivered >= max_events:
                return
