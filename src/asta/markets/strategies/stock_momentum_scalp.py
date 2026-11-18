"""Stock (IDX) tuning of the momentum scalp: liquid names, 2% SL / 5% TP."""

from asta.markets.strategies.momentum_scalp import MomentumScalpStrategy


class StockMomentumScalpStrategy(MomentumScalpStrategy):
    default_params = {
        **MomentumScalpStrategy.default_params,
        "min_price": 100.0,
        "min_volume_ma": 10_000_000.0,
        "min_value_ma": 10_000_000_000.0,
        "min_price_change_pct": 2.0,
        "min_volume_change_pct": 30.0,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 5.0,
    }
