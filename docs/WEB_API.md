# ASTA Web API

The dashboard is served by `asta serve` on `127.0.0.1:4310` (see `config/app.yaml` →
`web:`). One process runs the scanner (asyncio loop, main thread) and this HTTP
server (socket thread). **The API is read-only and unauthenticated** — it binds
loopback only; never set `web.host: 0.0.0.0` on a shared machine.

Every endpoint opens its own SQLite connection in `mode=ro`, so a browser poll can
never block the scanner's writer (WAL is enabled).

## Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `status`, `version`, `pid`, `uptimeSeconds`, `database{available,signals}`, `environment`, `dryRun`, `scanners`, `enabledScanners`, `cycles`, `lastCycleAt`, `storage{backend,records}`, `web{host,port,webDir}` |
| GET | `/api/meta` | aggregates: `total`, `closed`, `open`, `wins`, `losses`, `winRate`, `expectancyR`, `netR`, `profitFactor`, `firstSignal`, `lastSignal`, `generatedAt` |
| GET | `/api/facets` | distinct `scanners`, `markets`, `timeframes` |
| GET | `/api/config` | sanitized setup: environment, storage backend, web host/port, markets, provider types, scanners, channel env names. **Never secrets.** |
| GET | `/api/signals` | `{meta, signals[], total, offset, hasMore, generatedAt}` |
| GET | `/api/signals/<id\|signal_id>` | one signal (404 when absent) |

### `/api/signals` query parameters

| Param | Values | Default |
|---|---|---|
| `status` | `hit_tp`, `hit_sl`, `open`, `all` | all |
| `scanner` | exact `scanner_name` | all |
| `market` | `crypto`, `stock`, `forex` | all |
| `timeframe` | `15m`, `1h`, `1d`, … | all |
| `q` | substring of symbol / scanner / reason (case-insensitive) | — |
| `sort` | `newest`, `oldest`, `best`, `worst`, `confidence` | `newest` |
| `limit` | int (`-1`/omitted = all rows) | all |
| `offset` | int | 0 |

Responses are gzip-compressed when the client sends `Accept-Encoding: gzip`
(1405 signals ≈ 950 KB raw → ≈ 110 KB gzipped).

### Signal shape

```json
{
  "id": 1474,
  "signalId": "b5d23006df02",
  "scannerId": "CXS003_BREAKOUT_TREND",
  "scanner": "Breakout Trend",
  "market": "crypto",
  "symbol": "BNBUSDT",
  "timeframe": "1h",
  "side": "short",
  "confidence": 0.806,
  "price": 615.9,
  "stopLoss": 618.63,
  "takeProfit": 610.42,
  "riskReward": 2.0,
  "riskPct": 0.445,
  "atr": 6.24,
  "levelsSource": "structure",
  "status": "open",
  "realizedR": null,
  "barsHeld": null,
  "createdAt": "2026-11-14T04:15:18.477405Z",
  "closedAt": null,
  "expiresAt": "2026-11-16T03:00:00Z",
  "strategy": "Breakout Trend",
  "reason": "Bearish breakout: …",
  "source": "live",
  "indicators": {}
}
```

## Static files

`web/dist/` is served from the same origin. Unknown non-`/api` paths return
`index.html` (SPA routing). Hashed assets under `/assets/` are immutable-cached;
`index.html` is `no-cache`. If the build is missing, `/` returns `503` with the
build command in the body.

## Frontend development

```bash
cd web
npm install
npm run dev        # http://localhost:5173, proxies /api -> 127.0.0.1:4310
npm run build      # writes web/dist, served by `asta serve`
```

Vite binds `localhost` over IPv6 on macOS: use `localhost:5173`, not
`127.0.0.1:5173`, unless you pass `--host 127.0.0.1`.

## CLI

```bash
asta serve [--port 4310] [--host 127.0.0.1] [--no-browser] [--dry-run]
asta status        # JSON: running, url, config, server health
```
