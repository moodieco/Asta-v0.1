"""Intraday liquidity + momentum screen, shared implementation.

The screen answers one question: *which names are moving today with enough
turnover to be tradable?* Everything is measured on **today's** bars in the
exchange timezone, so the same rule set can be evaluated any number of times
during the session — repeat alerts are the pipeline's problem (dedup), not the
strategy's.

    price     last close >= ``min_price`` (100 IDR: the 1-rupiah tick floor)
    volume    today's share volume > ``min_volume`` (1,000,000)
    value     sum(close * volume) today > ``min_value`` (1,000,000,000 IDR)
    change    last close vs the previous session close > ``min_change_pct``
    levels    long only: stop 2% below, target 5% above, both tick-rounded
    expiry    ``session_end`` (before the exchange closes), not a bar count

Net foreign buy/sell is **not** part of the rule set: the Yahoo-backed stock
provider publishes OHLCV only, and the exchange's own foreign-flow feed is not
reachable without credentials. Every signal therefore carries ``foreign_note``
telling the operator to check that number by hand before acting.

Value is ``sum(close * volume)`` over today's bars — an approximation of the
exchange's traded value (which uses each trade's own price) and typically
within a few percent.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from datetime import time as dtime
from typing import List, Tuple
from zoneinfo import ZoneInfo

from asta.core.signal_model import Candle, ScanContext, SignalType
from asta.core.strategy import Strategy, StrategyResult
from asta.markets.strategies.asia_range_breakout import parse_hhmm

NOTE_FOREIGN_FLOW = (
    "Net Foreign Buy/Sell belum difilter (provider tidak menyediakannya) - "
    "perlu cek ulang di Net Foreign Buy/Sell, harus diatas 0"
)


def idx_tick(price: float) -> float:
    """IDX fractional tick size for the price band containing ``price``."""
    if price < 200:
        return 1.0
    if price < 500:
        return 2.0
    if price < 2000:
        return 5.0
    if price < 5000:
        return 10.0
    return 25.0


def round_to_tick(price: float, tick: float, up: bool) -> float:
    """Round to a valid order price: stops floor, targets ceil."""
    if tick <= 0:
        return round(price, 4)
    steps = price / tick
    steps = math.ceil(steps) if up else math.floor(steps)
    return round(max(steps, 1) * tick, 4)


def local_time(timestamp: datetime, zone: ZoneInfo) -> datetime:
    return timestamp.astimezone(zone)


class LiquidityMomentumStrategy(Strategy):
    name = "Liquidity Momentum"
    default_params = {
        "timezone": "Asia/Jakarta",
        # first pass of the day and the time exit before the close (exchange time)
        "session_start": "09:30",
        "session_end": "15:45",
        # screens
        "min_price": 100.0,
        "min_volume": 1_000_000.0,
        "min_value": 1_000_000_000.0,
        "min_change_pct": 0.0,
        # risk geometry
        "stop_pct": 0.02,
        "take_profit_pct": 0.05,
        # a name that has not printed a bar for this long is halted or dead
        "max_bar_age_minutes": 30,
        "min_confidence": 0.50,
        "min_candles": 30,
        # one alert per symbol per session
        "dedup_window_seconds": 25_200,
    }

    # -- helpers ----------------------------------------------------------
    def _zone(self) -> ZoneInfo:
        return ZoneInfo(str(self.param("timezone")))

    def _bounds(self, day: date, zone: ZoneInfo) -> Tuple[datetime, datetime]:
        start = datetime.combine(day, parse_hhmm(self.param("session_start")), tzinfo=zone)
        end = datetime.combine(day, parse_hhmm(self.param("session_end")), tzinfo=zone)
        return start, end

    def _today_split(self, candles: List[Candle], zone: ZoneInfo, day: date):
        midnight = datetime.combine(day, dtime(0, 0), tzinfo=zone)
        today = [c for c in candles if c.timestamp.astimezone(zone) >= midnight]
        older = [c for c in candles if c.timestamp.astimezone(zone) < midnight]
        return today, older

    def _confidence(self, volume_today: float, value_today: float, change_pct: float) -> float:
        """Turnover and momentum lift a 0.50 base by up to +0.30."""
        volume_rel = min(volume_today / max(float(self.param("min_volume")), 1.0) - 1.0, 1.0)
        value_rel = min(value_today / max(float(self.param("min_value")), 1.0) - 1.0, 1.0)
        momentum = min(change_pct / 10.0, 1.0)
        score = 0.50 + 0.10 * max(volume_rel, 0.0) + 0.10 * max(value_rel, 0.0) + 0.10 * max(momentum, 0.0)
        return round(min(max(score, 0.0), 0.95), 3)

    # -- evaluation -------------------------------------------------------
    def evaluate(self, context: ScanContext) -> List[StrategyResult]:
        context.require(int(self.param("min_candles")))
        zone = self._zone()
        now = context.now.astimezone(zone)
        if now.weekday() >= 5:
            return []  # exchange closed

        start, end = self._bounds(now.date(), zone)
        if not (start <= now < end):
            return []  # before the first pass, or past the time exit

        # Never look past ``now``: a replay hands us the whole file, and using
        # bars the scanner could not have seen would silently peek ahead.
        candles = [candle for candle in context.candles if candle.timestamp <= context.now]
        today, older = self._today_split(candles, zone, now.date())
        if not today or not older:
            return []  # no prints today, or no previous close to measure against

        prev_close = older[-1].close
        if prev_close <= 0:
            return []

        last = today[-1]
        age_minutes = (now - last.timestamp.astimezone(zone)).total_seconds() / 60.0
        if age_minutes > float(self.param("max_bar_age_minutes")):
            return []  # suspended or not trading right now

        price = last.close
        volume_today = sum(candle.volume for candle in today)
        value_today = sum(candle.close * candle.volume for candle in today)
        change_pct = (price / prev_close - 1.0) * 100.0

        if price < float(self.param("min_price")):
            return []
        if volume_today <= float(self.param("min_volume")):
            return []
        if value_today <= float(self.param("min_value")):
            return []
        if change_pct <= float(self.param("min_change_pct")):
            return []

        confidence = self._confidence(volume_today, value_today, change_pct)
        if confidence < float(self.param("min_confidence")):
            return []

        tick = idx_tick(price)
        stop_loss = round_to_tick(price * (1.0 - float(self.param("stop_pct"))), tick, up=False)
        take_profit = round_to_tick(price * (1.0 + float(self.param("take_profit_pct"))), tick, up=True)
        if not (stop_loss < price < take_profit):
            return []

        reason = (
            "{symbol} lolos screen likuiditas+momentum IHSG: "
            "price {price:,.0f} >= {min_price:,.0f}; "
            "volume {volume:,.0f} > {min_volume:,.0f}; "
            "value {value:,.0f} > {min_value:,.0f}; "
            "change +{change:.2f}% > 0. "
            "NOTE: {note}"
        ).format(
            symbol=context.symbol.upper(),
            price=price,
            min_price=float(self.param("min_price")),
            volume=volume_today,
            min_volume=float(self.param("min_volume")),
            value=value_today,
            min_value=float(self.param("min_value")),
            change=change_pct,
            note=NOTE_FOREIGN_FLOW,
        )

        return [
            StrategyResult(
                signal_type=SignalType.LONG,
                confidence=confidence,
                reason=reason,
                indicators={
                    "price": round(price, 4),
                    "prev_close": round(prev_close, 4),
                    "change_pct": round(change_pct, 3),
                    "volume_today": round(volume_today, 2),
                    "value_today": round(value_today, 2),
                },
                metadata={
                    "session_date": now.date().isoformat(),
                    "bars_today": len(today),
                    "foreign_net": None,
                    "foreign_note": NOTE_FOREIGN_FLOW,
                    "screener": "idx_liquidity_momentum",
                },
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                expires_at=end,
            )
        ]


def session_label(zone_name: str, start: str, end: str) -> str:
    """``Asia/Jakarta 09:30-15:45`` — used by scanners for their description."""
    return "{} {}-{}".format(zone_name, start, end)


__all__ = [
    "LiquidityMomentumStrategy",
    "NOTE_FOREIGN_FLOW",
    "idx_tick",
    "round_to_tick",
    "session_label",
]
