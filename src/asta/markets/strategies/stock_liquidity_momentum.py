"""IDX tuning of the liquidity + momentum screen (the BPJS scanner).

The rule set is generic — see :mod:`asta.markets.strategies.liquidity_momentum`
— and this subclass only pins the Indonesian numbers: the 100-rupiah price
floor, 1M shares, IDR 1B of turnover, 2% stop, 5% target, and the 09:30-15:45
WIB session. Net foreign flow is still missing on purpose; the generic strategy
attaches the note.
"""

from asta.markets.strategies.liquidity_momentum import (
    NOTE_FOREIGN_FLOW,
    LiquidityMomentumStrategy,
)

__all__ = ["NOTE_FOREIGN_FLOW", "StockLiquidityMomentumStrategy"]


class StockLiquidityMomentumStrategy(LiquidityMomentumStrategy):
    name = "Liquidity Momentum"
    default_params = {
        **LiquidityMomentumStrategy.default_params,
        "timezone": "Asia/Jakarta",
        "session_start": "09:30",  # first pass, WIB
        "session_end": "15:45",  # time exit before the IDX close
        "min_price": 100.0,  # 1-rupiah tick floor
        "min_volume": 1_000_000.0,  # shares traded today
        "min_value": 1_000_000_000.0,  # IDR traded today
        "min_change_pct": 0.0,  # must be up on the day
        "stop_pct": 0.02,
        "take_profit_pct": 0.05,
        # 5m bars over 1.5 sessions: enough history for the previous close
        "min_candles": 90,
    }
