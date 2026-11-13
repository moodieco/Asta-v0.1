# RSI Divergence (FXS001_RSI_DIVERGENCE)

Detects regular (classic) divergence between price swing pivots and Wilder RSI on forex majors.

## Entry conditions

- Two confirmed pivot lows (`pivot_span=2`) within `max_pivot_age` bars of the latest candle.
- Bullish: the second low is **lower** in price while RSI makes a **higher** low (`min_rsi_delta=1.5`).
- Bearish: the second high is **higher** in price while RSI makes a **lower** high.
- Confidence ≥ `min_confidence` (0.55). Higher when the pivot RSI is beyond the 35/65 band.

## Parameters (config.yaml)

| Param | Default | Meaning |
|---|---|---|
| `rsi_period` | 14 | Wilder RSI length |
| `lookback` | 120 | Candles inspected per evaluation |
| `pivot_span` | 2 | Bars on each side of a pivot |
| `min_rsi_delta` | 1.5 | Minimum RSI divergence in points |
| `max_pivot_age` | 12 | How recent the second pivot must be |
| `oversold` / `overbought` | 35 / 65 | Confidence bonus thresholds |
| `min_confidence` | 0.55 | Signals below this are dropped |

## When it stays quiet

No divergence, stale pivot, or confidence below threshold. Forex tick volume is broker
dependent, so this scanner does **not** require volume confirmation.

## Output

One `Signal` per detected setup: `scanner_id=FXS001_RSI_DIVERGENCE`, market `forex`,
timeframe `1h`. Confidence is a heuristic score in `[0, 1]`, not a calibrated
probability — treat it as a ranking, not a guarantee.
