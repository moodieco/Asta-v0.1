# Signal specification

The contract every scanner obeys, and the rules the pipeline applies to it.

## Lifecycle

```
candle close ──► scanner.evaluate ──► Signal ──► validator ──► dedup ──► storage ──► Discord
                                                 │              │
                                                 └─ reject ─────┴─ duplicate
```

## Object

```json
{
  "scanner_id": "CXS002_VOLUME_SPIKE",
  "scanner_name": "Volume Spike",
  "market": "crypto",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "signal_type": "long",
  "confidence": 0.88,
  "price": 104250.5,
  "reason": "Volume spike 5.2x the 20-bar average on a bullish candle (+3.00% body, 98% of range).",
  "timestamp": "2026-11-13T20:15:00Z",
  "strategy": "Volume Spike",
  "indicators": {"volume_ratio": 5.2, "body_ratio": 0.98},
  "metadata": {"volume_period": 20}
}
```

| Field | Rule |
|---|---|
| `scanner_id` | must match the producing scanner; `scan()` verifies it |
| `market` | one of `forex`, `crypto`, `stock`; must equal the scanner's market |
| `symbol` | upper-case in the signal; provider normalises per broker |
| `timeframe` | canonical (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, …) |
| `signal_type` | `long` or `short` only |
| `confidence` | `0 <= c <= 1`, clamped by `build_signal`, 3 decimals |
| `reason` | human readable, ≥ 10 chars, must explain *why* (used in the embed) |
| `price` | last close of the evaluated candle (or the level that triggered it) |
| `timestamp` | UTC; signal age must be ≤ `validator.max_signal_age_seconds` |
| `indicators` | finite floats only; rendered in the alert |

Derived: `dedup_key = market:scanner_id:SYMBOL:timeframe:signal_type`,
`signal_id = sha1(dedup_key + timestamp)[:12]`.

## Validation codes

| Code | Condition |
|---|---|
| `missing_scanner` | empty `scanner_id` |
| `missing_symbol` | empty `symbol` |
| `bad_timeframe` | timeframe not in the supported set |
| `low_confidence` | below `validator.min_confidence` |
| `bad_confidence` | not finite or > 1 |
| `weak_reason` | shorter than 10 characters |
| `bad_price` | ≤ 0 or not finite |
| `stale_signal` | older than `max_signal_age_seconds` |
| `future_signal` | more than 120 s ahead of now (clock skew guard) |
| `bad_indicator` | non-finite indicator value |

## Deduplication

* Key ignores price and confidence — only direction matters.
* Window: `min(2 × timeframe, storage.dedup_window_seconds)`; default max 3600 s.
* Register happens *before* delivery; if validation failed the claim is released.
* Deduplicated signals are counted in `signals_rejected`, never stored, never sent.

## Confidence

A heuristic ranking score derived from strategy-specific evidence
(divergence strength, EMA separation, volume ratio, ATR distance). It is **not** a
probability and has not been calibrated against outcomes; a backtest is a V0.2 item.

## Alert rendering

Discord embed: title `🟢 LONG · BTCUSDT · 15M` (or `🔴 SHORT`), description = `reason`,
green/red colour, fields Market/Scanner/Strategy/Confidence/Price/Time/Indicators,
footer `ASTA V0.1 · <scanner name> · <scanner id>`, timestamp = signal time.
Sample and test alerts are explicitly labelled (`🧪 SAMPLE`, `🧪 ASTA TEST ALERT`).
