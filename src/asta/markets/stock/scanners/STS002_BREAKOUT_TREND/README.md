# Breakout Trend (STS002_BREAKOUT_TREND)

40-bar high/low breakout on daily bars with volume confirmation and gap context.

## Entry conditions

- Daily close beyond the previous 40 bars' high/low by at least `buffer_pct` (0.5%).
- Volume ≥ `min_volume_ratio` (1.3) × the 20-bar average.
- EMA(100) agreement required; price within 3 ATR of the level.
- Reports `gap_pct` (overnight gap) as context in the alert.

## Parameters (config.yaml)

| Param | Default | Meaning |
|---|---|---|
| `breakout_lookback` | 40 | Range measured |
| `buffer_pct` | 0.005 | Extra distance beyond the level |
| `min_volume_ratio` | 1.3 | Volume confirmation |
| `max_distance_atr` | 3.0 | Anti-chase cap |
| `min_confidence` | 0.55 | Signals below this are dropped |

## When it stays quiet

Range-bound price, breakout on average volume, or a gap already extended past the level.

## Output

One `Signal` per detected setup: `scanner_id=STS002_BREAKOUT_TREND`, market `stock`,
timeframe `1d`. Confidence is a heuristic score in `[0, 1]`, not a calibrated
probability — treat it as a ranking, not a guarantee.
