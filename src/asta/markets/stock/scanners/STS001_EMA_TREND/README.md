# EMA Trend (STS001_EMA_TREND)

Daily EMA(20)/EMA(50) cross that must agree with the EMA(200) trend.

## Entry conditions

- EMA20 crossed EMA50 within `cross_lookback` (3) daily bars.
- Trend alignment is mandatory (`require_trend_alignment: true`): a bullish cross requires
  price above EMA200, a bearish cross requires price below it.
- Confidence ≥ 0.55.

## Parameters (config.yaml)

| Param | Default | Meaning |
|---|---|---|
| `fast_period` / `slow_period` | 20 / 50 | EMA pair |
| `trend_period` | 200 | Trend filter |
| `cross_lookback` | 3 | Validity window after the cross |
| `require_trend_alignment` | true | Reject counter-trend crosses |
| `min_confidence` | 0.55 | Signals below this are dropped |

## When it stays quiet

Cross against the long trend (common in V-bottoms), or no cross at all.

## Output

One `Signal` per detected setup: `scanner_id=STS001_EMA_TREND`, market `stock`,
timeframe `1d`. Confidence is a heuristic score in `[0, 1]`, not a calibrated
probability — treat it as a ranking, not a guarantee.
