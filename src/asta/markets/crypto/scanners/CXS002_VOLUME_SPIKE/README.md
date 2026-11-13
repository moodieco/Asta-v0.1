# Volume Spike (CXS002_VOLUME_SPIKE)

Flags a candle whose volume is an outlier versus its recent average, with a directional body.

## Entry conditions

- Volume ≥ `spike_multiplier` (3.0) × the average of the previous `volume_period` candles.
- Body ≥ `min_body_ratio` (35%) of the candle range — a doji on huge volume is indecision.
- Direction: bullish body → LONG, bearish body → SHORT.
- Adds `volume_percentile` (0-100) so you can see how extreme the bar is.

## Parameters (config.yaml)

| Param | Default | Meaning |
|---|---|---|
| `volume_period` | 20 | Volume average window |
| `spike_multiplier` | 3.0 | Outlier threshold |
| `min_body_ratio` | 0.35 | Minimum body / range |
| `min_confidence` | 0.5 | Signals below this are dropped |

## When it stays quiet

Volume in line with the 20-bar average, or a high-volume doji.

## Output

One `Signal` per detected setup: `scanner_id=CXS002_VOLUME_SPIKE`, market `crypto`,
timeframe `15m`. Confidence is a heuristic score in `[0, 1]`, not a calibrated
probability — treat it as a ranking, not a guarantee.
