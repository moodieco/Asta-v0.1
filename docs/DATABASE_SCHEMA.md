# Storage schema

Two interchangeable backends behind the same interface (`append`, `load_all`, `tail`,
`count`, `recorded_after`, `stats`): SQLite (current deployment) and JSONL. Select with
`config/app.yaml: storage.backend`. Migrate existing JSONL rows with
`scripts/migrate_history.py` (idempotent, keeps original timestamps).

## SQLite

File: `data/history/asta.db` (WAL mode, created on startup, no migrations needed).

```sql
CREATE TABLE signals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id     TEXT    NOT NULL UNIQUE,   -- sha1(dedup_key + timestamp)[:12]
    scanner_id    TEXT    NOT NULL,
    scanner_name  TEXT    NOT NULL,
    market        TEXT    NOT NULL,          -- forex | crypto | stock
    symbol        TEXT    NOT NULL,
    timeframe     TEXT    NOT NULL,
    signal_type   TEXT    NOT NULL,          -- long | short
    confidence    REAL    NOT NULL,
    price         REAL,
    reason        TEXT    NOT NULL,
    strategy      TEXT    NOT NULL DEFAULT '',
    indicators    TEXT    NOT NULL DEFAULT '{}',  -- JSON
    metadata      TEXT    NOT NULL DEFAULT '{}',  -- JSON
    created_at    TEXT    NOT NULL,          -- signal time, ISO-8601 UTC
    recorded_at   TEXT    NOT NULL           -- insert time, ISO-8601 UTC
);
CREATE INDEX idx_signals_scanner ON signals(scanner_id, created_at DESC);
CREATE INDEX idx_signals_market  ON signals(market, created_at DESC);
CREATE INDEX idx_signals_symbol  ON signals(symbol, timeframe, created_at DESC);
```

`signal_id` is unique: re-inserting the same signal is ignored (`INSERT` → `IntegrityError`
→ `False`), which is the storage-level backstop for the in-memory dedup cache.

### Repository API (`storage/repositories/signal_repository.py`)

| Method | Returns |
|---|---|
| `save(signal)` | `True` if inserted, `False` if duplicate |
| `save_many(signals)` | number inserted |
| `count()` | total rows |
| `recent(limit)` | newest rows as dicts, JSON columns decoded |
| `by_market(market, limit)` / `by_scanner(id, limit)` | filtered rows |
| `last_timestamp(scanner_id, symbol)` | `datetime` or `None` |
| `stats()` | `{"market:scanner_id": count}` |

### Typical queries

```sql
-- signals per scanner today
SELECT scanner_id, COUNT(*) FROM signals
WHERE created_at >= date('now') GROUP BY scanner_id ORDER BY 2 DESC;

-- last signal per symbol
SELECT symbol, MAX(created_at) FROM signals GROUP BY symbol;

-- confidence distribution per market
SELECT market, ROUND(AVG(confidence), 3), COUNT(*) FROM signals GROUP BY market;
```

## JSONL

File: `data/history/signals.jsonl`, one JSON object per accepted signal, flushed and
`fsync`ed on append. Fields mirror the table (`timestamp`, `indicators`, `metadata`).
Useful for grep/tail and for replaying into SQLite later.

## Data directory

```
data/
├── cache/     reserved for future on-disk candle cache (currently in-memory TTL)
├── history/   signals.jsonl and/or asta.db
└── logs/      asta.log (rotating: 5 MB × 3)
```

`data/` is gitignored. Retention is manual for V0.1; prune with
`DELETE FROM signals WHERE created_at < date('now','-90 day')` or truncate the JSONL.
