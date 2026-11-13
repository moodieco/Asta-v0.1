# EMA Pullback (CXS004_EMA_PULLBACK)

Trend-following continuation: after a shallow pullback inside an established trend,
trade the first candle that reclaims the fast EMA.

## Entry conditions

- Price above EMA(100) for longs (below for shorts) — trend filter.
- 10-bar slope of close ≥ `min_slope` (0.05%/bar) in the trend direction.
- Within the last `pullback_lookback` (6) bars, RSI(14) printed a value inside the
  pullback band `rsi_min..rsi_max` (38..52 for longs; 48..62 mirrored for shorts).
- Trigger candle is directional (body ≥ 30% of range) and closes back above EMA(20)
  (below for shorts).
- Confidence ≥ `min_confidence` (0.55).

## Parameters

| Param | Default | Meaning |
|---|---|---|
| `fast_period` | 20 | Reclaim EMA |
| `trend_period` | 100 | Trend EMA |
| `rsi_period` | 14 | RSI length |
| `rsi_min` / `rsi_max` | 38 / 52 | Pullback band |
| `pullback_lookback` | 6 | Bars to look back for the RSI reset |
| `min_body_ratio` | 0.3 | Minimum body / range on the trigger candle |
| `min_slope` | 0.0005 | Minimum trend slope (fraction per bar) |
| `min_confidence` | 0.55 | Signals below this are dropped |

## When it stays quiet

No trend, pullback too deep (RSI below 38 = possible reversal), RSI never reset,
or the trigger candle is a doji.

## Output

`scanner_id=CXS004_EMA_PULLBACK`, market `crypto`, timeframe `1h`. Indicators include
RSI, the pullback RSI low, EMA20/EMA100, slope and body ratio.
