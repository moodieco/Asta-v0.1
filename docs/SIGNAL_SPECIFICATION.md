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
| `stop_loss` / `take_profit` | structural (pivot, breakout level) or ATR-based levels |
| `risk_reward` | `abs(target-entry)/abs(entry-stop)`, rounded to 2 dp |
| `risk_pct` | stop distance as % of entry, bounded by the risk config |
| `atr` | ATR at signal time (14 periods by default) |
| `levels_source` | `structure` when a setup level was used, `atr` otherwise |
| `expires_at` | signal time + `max_bars` × timeframe |
| `status` | `open` → `hit_tp` / `hit_sl` / `expired` |
| `source` | `live` (scheduler) or `backfill` (historical replay) |

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
| `incomplete_levels` | only one of stop/target present |
| `bad_levels` | long needs stop < entry < target (short mirrored) |
| `bad_risk` | stop distance outside 0–10% of entry |

## Deduplication

* Key ignores price and confidence — only direction matters.
* Window: `min(2 × timeframe, storage.dedup_window_seconds)`; default max 3600 s.
* Register happens *before* delivery; if validation failed the claim is released.
* Deduplicated signals are counted in `signals_rejected`, never stored, never sent.

## Risk levels

Computed in `core/risk.py`:

* **Stop** — structural when the setup provides one (RSI divergence pivot, breakout
  level, pullback swing), otherwise `1.5 × ATR(14)`.
* **Target** — `reward_ratio` (default 2R) beyond entry, or an explicit target.
* **Expiry** — `max_bars` (default 48) candles after the signal.
* Rejected when the stop is on the wrong side, closer than 0.1% or farther than 5%.

Outcomes are scored by replaying subsequent candles (`outcome_for_signal`):
target first → `hit_tp` (+1R), stop first → `hit_sl` (-1R), neither within
`expires_at` → `expired` (0R). If one candle touches both, the stop wins.

## Confidence

A heuristic ranking score derived from strategy-specific evidence
(divergence strength, EMA separation, volume ratio, ATR distance). It is **not** a
probability and has not been calibrated against outcomes; a backtest is a V0.2 item.

## Alert rendering

Discord embed: title `🟢 LONG · BTCUSDT · 15M` (or `🔴 SHORT`), description = `reason`,
green/red colour, fields Market/Scanner/Strategy/Confidence/Price/Time/Indicators,
footer `ASTA V0.1 · <scanner name> · <scanner id>`, timestamp = signal time.
Sample and test alerts are explicitly labelled (`🧪 SAMPLE`, `🧪 ASTA TEST ALERT`).
