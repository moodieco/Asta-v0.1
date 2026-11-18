# Momentum Scalp (STS004_MOMENTUM_SCALP)

Flags liquid IDX stocks that closed up with a volume surge; fixed 2% stop, 5% target.

## Entry conditions
- Close >= 100
- Volume MA5 >= 10M shares
- Value MA5 (close x volume) >= 10B IDR
- Price change vs previous close >= 2%
- Volume change vs previous bar >= 30%

## Parameters (config.yaml)
| Param | Default | Meaning |
|---|---|---|
| min_price | 100 | Minimum close |
| ma_period | 5 | MA length for volume and value |
| min_volume_ma | 10,000,000 | Minimum volume MA (shares) |
| min_value_ma | 10,000,000,000 | Minimum traded-value MA (IDR) |
| min_price_change_pct | 2.0 | Minimum price change (%) |
| min_volume_change_pct | 30.0 | Minimum volume change (%) |
| stop_loss_pct | 2.0 | Stop distance from entry (%) |
| take_profit_pct | 5.0 | Target distance from entry (%) |
| min_confidence | 0.55 | Minimum confidence |

## When it stays quiet
Any filter fails, or fewer than 6 daily candles exist.

## Output
One `Signal` per detected setup: `scanner_id=STS004_MOMENTUM_SCALP`, market `stock`, timeframe `1d`.
Confidence is a heuristic score in `[0, 1]`, not a calibrated probability.
