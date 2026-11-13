# RSI Divergence (CXS001_RSI_DIVERGENCE)

RSI divergence on crypto pairs with wider RSI bands (30/70) and a volume-expansion gate.

## Entry conditions

- Two confirmed price pivots with RSI divergence (`min_rsi_delta=2.0`).
- Volume of the latest candle ≥ `min_volume_ratio` (1.0) × the 20-bar average — divergence
  without participation is ignored.
- Confidence ≥ `min_confidence` (0.55).

## Parameters (config.yaml)

| Param | Default | Meaning |
|---|---|---|
| `rsi_period` | 14 | Wilder RSI length |
| `lookback` | 120 | Candles inspected |
| `min_rsi_delta` | 2.0 | Minimum RSI divergence |
| `oversold` / `overbought` | 30 / 70 | Confidence bonus thresholds |
| `volume_confirm` | true | Require volume expansion |
| `min_volume_ratio` | 1.0 | Volume expansion floor |
| `min_confidence` | 0.55 | Signals below this are dropped |

## When it stays quiet

Divergence exists but volume is flat (this is the most common rejection: a real
divergence at 0.26x volume is deliberately ignored), or the pivot is too old.

## Output

One `Signal` per detected setup: `scanner_id=CXS001_RSI_DIVERGENCE`, market `crypto`,
timeframe `1h`. Confidence is a heuristic score in `[0, 1]`, not a calibrated
probability — treat it as a ranking, not a guarantee.
