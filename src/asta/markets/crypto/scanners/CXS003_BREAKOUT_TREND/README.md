# Breakout Trend (CXS003_BREAKOUT_TREND)

Range breakout that must agree with the trend, on rising volume, without chasing.

## Entry conditions

- Close beyond the previous `breakout_lookback` (30) bars' high/low, plus `buffer_pct` (0.2%).
- Volume ≥ `min_volume_ratio` (1.2) × the 20-bar average.
- Price within `max_distance_atr` (2.5) × ATR14 of the breakout level — beyond that it is chasing.
- EMA(100) agreement is required by default.

## Parameters (config.yaml)

| Param | Default | Meaning |
|---|---|---|
| `breakout_lookback` | 30 | Range measured |
| `buffer_pct` | 0.002 | Extra distance beyond the level |
| `trend_period` | 100 | Trend filter EMA |
| `min_volume_ratio` | 1.2 | Volume expansion floor |
| `max_distance_atr` | 2.5 | Anti-chase cap |
| `min_confidence` | 0.55 | Signals below this are dropped |

## When it stays quiet

Inside the range, breakout against the trend, thin volume, or price already extended
more than 2.5 ATR past the level.

## Output

One `Signal` per detected setup: `scanner_id=CXS003_BREAKOUT_TREND`, market `crypto`,
timeframe `1h`. Confidence is a heuristic score in `[0, 1]`, not a calibrated
probability — treat it as a ranking, not a guarantee.
