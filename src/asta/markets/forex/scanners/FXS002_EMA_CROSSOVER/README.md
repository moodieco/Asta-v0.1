# EMA Crossover (FXS002_EMA_CROSSOVER)

EMA(20) crossing EMA(50) with EMA(200) as trend context, on forex majors.

## Entry conditions

- The fast/slow EMA pair crossed within the last `cross_lookback` candles.
- Separation between the EMAs ≥ `min_separation_pct` (0.05%).
- `require_trend_alignment` is `false` by default: a cross against the EMA200 still fires
  but with lower confidence.

## Parameters (config.yaml)

| Param | Default | Meaning |
|---|---|---|
| `fast_period` / `slow_period` | 20 / 50 | EMA pair |
| `trend_period` | 200 | Trend filter EMA |
| `cross_lookback` | 3 | Bars after the cross where a signal is still valid |
| `min_separation_pct` | 0.0005 | Minimum EMA separation |
| `min_confidence` | 0.5 | Signals below this are dropped |

## When it stays quiet

Flat market (EMAs never cross), cross older than `cross_lookback`, or EMAs still
overlapping after the cross.

## Output

One `Signal` per detected setup: `scanner_id=FXS002_EMA_CROSSOVER`, market `forex`,
timeframe `1h`. Confidence is a heuristic score in `[0, 1]`, not a calibrated
probability — treat it as a ranking, not a guarantee.
