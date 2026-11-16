# ASTA Web API

The dashboard is served by `asta serve` on `127.0.0.1:4310` (see `config/app.yaml` →
`web:`). One process runs the scanner (asyncio loop, main thread) and this HTTP
server (socket thread). Loopback access is open; when `web.bind: 0.0.0.0` (the
default) the dashboard is reachable from the LAN and every non-loopback request
must present a share token (editor or view-only) issued at `/api/share`.

Reads are SQLite `mode=ro` connections, so a browser poll can never block the
scanner's writer (WAL is enabled). Writes (scanner install / uninstall / restore /
test alert) touch the scanner library on disk, not the signal database.

## Endpoints

`GET /healthz` is the one **unauthenticated** path: `200 {"ok": true}`. Hosting
platforms (Render, Fly, k8s) must be able to probe liveness without a share
token, and it returns no data.

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `status`, `version`, `pid`, `uptimeSeconds`, `database{available,signals}`, `environment`, `dryRun`, `scanners`, `enabledScanners`, `cycles`, `lastCycleAt`, `storage{backend,records}`, `web{host,port,webDir}` |
| GET | `/api/meta` | aggregates: `total`, `closed`, `open`, `wins`, `losses`, `winRate`, `expectancyR`, `netR`, `profitFactor`, `firstSignal`, `lastSignal`, `generatedAt` |
| GET | `/api/facets` | distinct `scanners`, `markets`, `timeframes` |
| GET | `/api/config` | sanitized setup: environment, storage backend, web host/port, markets, provider types, scanners, channel env names. **Never secrets.** |
| GET | `/api/setup` | setup state for the in-dashboard wizard: `complete`, `completedAt`, per-step summaries, `webhooks` (env name + `configured` + `masked`), providers, market universes, scanner inventory, `system{dbPath,host,port,environment,root}`. **Masked values only — never a full webhook URL.** |
| GET | `/api/system` | live process metrics: `uptimeSeconds`, `cpuPct` (sampled), `rssBytes`, `loadAvg`, `threads`, `database{path,sizeBytes,available,signals}`, `logs{path,errors,warnings,recent[]}`, `scanners{total,enabled}`, `cycles`, `lastCycleAt`, `web` |
| GET | `/api/signals` | `{meta, signals[], total, offset, hasMore, generatedAt}` |
| GET | `/api/signals/<id\|signal_id>` | one signal (404 when absent) |
| GET | `/api/access` | `{access}` — `editor` or `viewer` (drives read-only UI) |
| GET | `/api/scanners/library` | `{available, installed[], trash[], history[], root, trashRoot}` |
| GET | `/api/alerts/log` | `{entries[]}` — recorded test/sample deliveries |
| GET | `/api/share` | `{enabled, editorUrl, viewUrl, editorToken, viewerToken, lanIps}` |

### Write endpoints (editor token / loopback only — viewers get 403)

| Method | Path | Body → effect |
|---|---|---|
| POST | `/api/scanners/install` | `{name, market, version, source, sourceName, timeframes, description, dependencies, sha256}` → writes the bundle into `data/scanners/<market>/<id>/` and returns its manifest |
| POST | `/api/scanners/<id>/uninstall` | `{reason}` → moves the folder to `data/scanners/.trash/<id>/` |
| POST | `/api/scanners/<id>/restore` | — → moves it back out of the recycle bin |
| POST | `/api/scanners/<id>/purge` | — → permanently deletes it from the recycle bin |
| POST | `/api/scanners/<id>/set-enabled` | `{enabled}` → writes the scanner's `enabled` (user scanner `config.yaml`, or `markets.yaml` for built-ins; restart to apply) |
| POST | `/api/alerts/test` | `{market?}` → sends a labelled test to every configured webhook (or one) and records the result |
| POST | `/api/alerts/sample` | `{market?}` → sends a labelled sample signal card |
| POST | `/api/share/regenerate` | — → rotates both share tokens |

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
