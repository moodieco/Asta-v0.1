# Stockbit MCP — evaluasi & integrasi

Status: **OFF secara default.** Sidecar tidak ikut instalasi, tidak pernah
dijalankan ASTA, dan bukan tipe provider yang bisa dipilih. Tahap 1 (sidecar)
dan tahap 2 (klien Python) ada di repo sebagai kode opt-in; login Stockbit
belum dilakukan (butuh pemilik akun), jadi kalaupun sidecar dijalankan semua
tool masih menjawab "No Stockbit session stored".

## Sakelar OFF — apa yang menjaganya

Empat hal, semuanya diperiksa test `tests/unit/stock/test_stockbit_off_by_default.py`:

1. `stockbit` **bukan** tipe provider. `PROVIDER_TYPES` = binance, mt5, oanda,
   yahoo; `providers.stock.type: stockbit` gagal keras dengan
   `ConfigurationError` alih-alih diam-diam mengaktifkan sesuatu.
2. `build_providers()` tidak pernah menyentuh Stockbit — provider `stock` tetap
   `StockProvider` (Yahoo).
3. `config/app.yaml` tidak punya blok `providers.stockbit`; `config/markets.yaml`
   hanya mengatur scanner.
4. Tidak ada autostart: `asta`, `asta serve`, dan launcher tidak memanggil
   `scripts/start_stockbit_mcp.sh`. Satu-satunya jalan menyalakan sidecar adalah
   menjalankan skrip itu sendiri (atau `node dist/bin/stockbit-mcp.js`), dan
   yang mengonsumsinya hanya `scripts/stockbit_check.py`.

Cek cepat bahwa memang mati:

```bash
lsof -nP -iTCP:8787 -sTCP:LISTEN   # tidak ada output = sidecar mati
ps aux | grep -c "[s]tockbit-mcp"  # 0
```

## Yang dievaluasi

1. `github.com/api-evangelist/stockbit` — **ditolak.** Isi repo hanya `README.md` +
   `.gitignore` (6 KB, bahasa: kosong, 1★, 2 commit). Tidak ada kode, OpenAPI, SDK,
   maupun artefak mesin-terbaca; README-nya sendiri menyatakan Stockbit tidak
   menerbitkan API developer publik dan "this repository contains no software".
   Tidak ada yang bisa diintegrasikan.

2. `github.com/SorataBaka/New-Composite-API` — **ditolak (mati).** Kode terakhir
   1 Agt 2021 (commit setelahnya cuma workflow CodeQL), 0 rilis, 0 tag, README 379 B,
   nol test, 16★. Instance publiknya `compositeapi.harjuno.xyz` **NXDOMAIN** —
   subdomain sudah tidak ada, jadi tidak ada endpoint untuk dikonsumsi. Kalaupun
   dijalankan sendiri: login lewat `https://api.stockbit.com/v2.4/login?user=…&password=…`
   (password di query string, host/versi API lama yang sudah tidak dipakai — versi
   sekarang di host `exodus` + sesi browser), bearer disimpan di MongoDB via
   mongoose 5, rate limit 40 req / 5 menit, satu simbol max 4 karakter per request.
   Datanya hanya `/company/{symbol}` (harga terakhir, change, volume, orderbook,
   indexes) — **tidak ada OHLC history/bars**, jadi tidak bisa memenuhi kontrak
   `MarketDataProvider.fetch_candles`. Dependency 2021 (axios 0.21.1, express 4.17,
   mongoose 5, puppeteer 10 yang bahkan tidak pernah di-import). Kalah di semua
   aspek dibanding poin 3, dengan sumber upstream yang sama.

3. `github.com/INo-xious/stockbit-mcp` — **dipakai.** Server MCP (bukan library
   Python) untuk data IDX: quote, orderbook, top movers, bandarmology/broker
   summary, fundamentals, patterns, screener, news/stream, dan baca-saja portofolio.
   Build ini **tidak** punya eksekusi order uang nyata (dihapus, fail-closed).

   | Aspek | Nilai |
   | --- | --- |
   | Bahasa / build | TypeScript, Node 22+ (`engines.node` = 22 karena `src/auth/cdp.ts` butuh global WebSocket) |
   | Rilis | npm `stockbit-mcp`, tag v1.4.1, MIT, 60★, 23 fork |
   | Uji | 1.632 lulus / 0 gagal, plus `smoke` (41 tool profil `core`, 152 profil `all`) |
   | Aktivitas | 291 commit, commit terakhir 12 Nov 2026 |
   | Transport | `stdio` (default) atau `http` stateless Streamable HTTP di `127.0.0.1:8787/mcp` |
   | Auth | login browser interaktif sekali (`stockbit-auth login`) atau `import-har`; sesi di OS Keychain / file AES-256-GCM; refresh-token **berotasi** |

## Kenapa cocok secara teknis

ASTA sudah punya klien MCP sendiri di `src/asta/providers/mcp/client.py`
(stateless Streamable HTTP + Bearer token, `initialize` / `tools/list` /
`tools/call`), dan pola pembungkusan yang sama sudah dipakai
`src/asta/providers/forex/mt5/client.py`. Mode HTTP stockbit-mcp menyajikan bentuk
protokol yang identik, jadi tidak perlu klien baru.

Prasyarat di mesin ini terpenuhi: Node v22.19.0, npm 10.9.3, Google Chrome terpasang.

## Temuan yang mengubah rencana: tidak ada OHLCV

Diverifikasi terhadap sidecar yang benar-benar berjalan (profil `all`, 152 tool):
satu-satunya tool seri harga adalah `chart_series`, `intraday_prices`, dan
`prices_batch` — **tidak ada tool bars/OHLCV**. Dokumentasi tool-nya sendiri
menyatakan untuk route harian: close datang sebagai `value` sementara
open/high/low/volume datang kosong dan volume `null`. Artinya setiap candle akan
flat dan bervolume nol.

Karena itu **tahap 2 versi awal (provider candle `MarketDataProvider`) dibatalkan**:
membangunnya berarti memberi seluruh indikator di repo ini seri yang terlihat wajar
tapi salah — persis yang ditolak `providers/base.py`. `providers.stock.type` tetap
`yahoo`; Stockbit masuk sebagai klien konteks, bukan pengganti candle.
`StockbitClient.fetch_candles()` sengaja selalu melempar error supaya salah pasang
gagal dengan keras, bukan diam-diam.

## Yang sudah terpasang

### Sidecar (tahap 1, opsional — bukan bagian instalasi)

Prasyarat: **Node >= 22** (`engines.node` di package.json sidecar; `src/auth/cdp.ts`
butuh `WebSocket` global) dan npm. Di mesin ini terpasang Node v22.19.0 / npm 10.9.3.

```bash
git clone https://github.com/INo-xious/stockbit-mcp third_party/stockbit-mcp
cd third_party/stockbit-mcp && npm ci && npm run build
npm run smoke                      # 41 tools / 6 prompts (core), 152/8 (all)
```

Langkah di atas sudah dijalankan ulang pada build yang ada (v1.4.1, commit
`b5c2376`) dan lolos: `smoke OK — default: 41 tools, 6 prompts · all: 152 tools, 8
prompts`. Binari hasil build: `dist/bin/stockbit-mcp.js` dan
`dist/bin/stockbit-auth.js` (sesuai `bin` di package.json).

Dijalankan lewat `scripts/start_stockbit_mcp.sh` — membuat token base64url 32 byte
sekali dan menyimpannya di `third_party/.stockbit-mcp-token` (mode 0600), lalu
mengekspor `STOCKBIT_MCP_TRANSPORT=http`:

```bash
scripts/start_stockbit_mcp.sh                    # -> http://127.0.0.1:8787/mcp
STOCKBIT_TOOLS=all scripts/start_stockbit_mcp.sh # seluruh surface
```

Token wajib 32–256 karakter base64url (`/^[A-Za-z0-9_-]{32,256}$/` di
`src/mcp/http.ts`); nilai pendek ditolak saat startup (`STOCKBIT_MCP_TOKEN is
required for HTTP`). Diuji ulang pada dokumen ini: tanpa header Bearer endpoint
menjawab `401`; dengan Bearer, `initialize` menjawab `protocolVersion
2025-06-18` / `serverInfo.name=stockbit`, dan `tools/list` mengembalikan **41**
tool (profil default). Yang wajib di header: `accept: application/json,
text/event-stream` — tanpa itu sidecar membalas JSON-RPC error `Not Acceptable:
Client must accept both application/json and text/event-stream`.

`third_party/stockbit-mcp/` dan file token ada di `.gitignore`.

### Klien Python (tahap 2, sudah direvisi)

`src/asta/providers/stock/stockbit/` — `StockbitClient` membungkus
`asta.providers.mcp.MCPClient` (jalur yang sama dengan MT5), dengan method bernama
untuk `status`, `quote`, `orderbook`, `price_bands`, `broker_summary`,
`bandar_detector`, `broker_activity`, `keystats`, `financials`, `ratios`,
`market_session`, `top_movers`, `news`, `chart_series`, `daily_closes`.

Detail yang dijaga:

- simbol dinormalisasi ke ticker IDX (`bbri.jk` → `BBRI`);
- argumen `None` dibuang, jadi tool tidak menerima field kosong;
- `chart_series` hanya menerima jendela kalender `1w/1m/3m/ytd/1y/3y/5y` — `1D`
  ditolak lokal karena upstream menjawab 200 + seri kosong;
- `broker_summary`/`bandar_detector` hanya menerima `LATEST`, `YESTERDAY`,
  `LAST_7_DAYS`, `LAST_3_MONTHS`, `YEAR_TO_DATE`;
- error tool dibongkar dari envelope sidecar sehingga yang muncul
  `quote: No Stockbit session stored.` dengan `kind=auth`, bukan repr MCP;
- URL/token jatuh ke `STOCKBIT_MCP_URL` / `STOCKBIT_MCP_TOKEN`.

Belum diregistrasi di `_provider_classes` dan tidak ada blok `providers.stock.type:
stockbit` — sengaja, karena kontraknya `fetch_candles` dan itu tidak bisa dipenuhi.

### Alat periksa

```bash
scripts/start_stockbit_mcp.sh &
python scripts/stockbit_check.py --tools        # daftar tool sidecar
python scripts/stockbit_check.py BBRI TLKM      # status, quote, band, broker, keystats
```

Read-only: tidak ada tool tulis yang dipanggil.

### Test offline

`tests/unit/stock/test_stockbit_client.py` — 21 test, tanpa sidecar dan tanpa akun:
normalisasi simbol, pembuangan argumen kosong, validasi jendela/period,
pembongkaran error, dan penolakan `fetch_candles`.

## Langkah yang tersisa (pemilik akun)

1. Login sekali di mesin ini:

   ```bash
   cd third_party/stockbit-mcp
   node dist/bin/stockbit-auth.js login        # buka browser, ketik sendiri
   # alternatif tanpa GUI: import HAR dari browser biasa
   node dist/bin/stockbit-auth.js import-har ~/login.har --shred
   node dist/bin/stockbit-auth.js status
   ```

2. Jalankan `python scripts/stockbit_check.py BBRI` → quote/bandarmology harus
   keluar angkanya, bukan `kind=auth`.

3. Opsional: `npm run verify:tools -- --live` di sidecar (read-only sweep).

## Batasan yang tetap berlaku

- **Login manual, bukan otomatis.** Password/OTP diketik di halaman Stockbit sendiri
  oleh pemilik akun; tidak pernah lewat agen. Timeout login 15 menit.
- **Tanpa GUI tidak bisa login.** Headless diblokir Cloudflare; UI wajib. Untuk
  Ubuntu server: Xvfb + VNC, atau `import-har` dari browser di mesin lain.
- **Access token 24 jam, refresh token berotasi & single-use (~7 hari).** Menganggur
  >7 hari = login ulang. Membuka stockbit.com di profil browser yang sama ikut
  memutar refresh token — itu alasan `reflock.ts` ada.
- **Store terikat mesin.** Key file fallback macOS/Linux = `scrypt(hostname +
  username + "stockbit-mcp/v1")`, tanpa override env — `~/.stockbit` tidak bisa
  dipindah antar mesin.
- **API privat & undocumented.** README proyek menyatakan API dapat berubah dan tidak
  menjamin akses otomatis diizinkan oleh ToS Stockbit. Tool bisa rusak sewaktu-waktu;
  perlakukan kegagalan sebagai `ProviderError`, bukan data kosong.
- **Satu akun per proses.** Kredensial, store, paper ledger, dan browser chart
  dibagi antar koneksi; token Bearer bukan pemisah pengguna.

## Tahap 3 — pengayaan sinyal (usulan, belum dieksekusi)

Prinsipnya: pengayaan **tidak pernah** mengubah apakah sinyal terbit, arahnya, atau
confidence-nya. Ia hanya menempelkan konteks, dan kalau gagal, diabaikan.

**Titik sisip.** `SignalManager.process`, tepat setelah validasi + dedupe lolos dan
sebelum `history.append` / `notifier.dispatch`. Dengan begitu sinyal yang tersimpan dan
yang terkirim membawa konteks yang sama, sementara sinyal yang ditolak tidak membayar
satu request pun.

**Komponen.**

1. `src/asta/core/signal_enricher.py` — protokol `Enricher` (`enrich(signal) -> dict | None`)
   dan `StockbitEnricher` yang memanggil `broker_summary(period="LAST_7_DAYS")`,
   `bandar_detector`, dan `price_bands`, lalu meringkasnya ke
   `signal.metadata["stockbit"]`:
   `net_foreign_idr`, `bandar.bias`/`score`, `broker_top` (kode + net lots),
   `fetched_at`, dan `degraded: true` bila ada tool yang gagal — bedakan "flat" dari
   "tidak tahu".
2. `SignalManager(..., enricher=None)`; `try/except` hanya menulis log. `Signal` sudah
   mutable dengan `metadata: Dict[str, Any]`, jadi tidak perlu model baru.
3. Config, default mati sehingga perilaku sekarang tidak berubah:

   ```yaml
   providers:
     stockbit:
       enabled: false
       url: http://127.0.0.1:8787/mcp
       token: ${STOCKBIT_MCP_TOKEN}
       enrich_markets: [stock]
       cache_seconds: 300
       timeout_seconds: 30
   ```

4. Cache in-memory per simbol (`cache_seconds`, default 300) supaya satu scan 10 simbol
   tidak menembak upstream 10 kali.
5. Renderer Discord menampilkan blok "Stockbit context" **hanya kalau ada** — sinyal
   tanpa konteks tetap memakai format sekarang.
6. Test offline dengan stub enricher: (a) enricher melempar → sinyal tetap lolos dan
   terkirim; (b) enricher mengembalikan dict → `metadata["stockbit"]` terisi. Tanpa akun,
   tanpa sidecar.

**Sengaja tidak termasuk:** menggugurkan sinyal berdasarkan foreign flow atau
bandarmology. Itu mengubah sinyal mana yang terbit — keputusan terpisah, bukan bagian
dari pengayaan.

**Alternatif lebih murah** kalau pipeline tidak mau disentuh: `scripts/stockbit_report.py`
yang mengirim digest bandarmology harian ke Discord, mandiri tanpa `SignalManager`.

## Gate verifikasi

```bash
cd web && npx tsc -p tsconfig.json --noEmit && npm run build
pytest -q                                          # 295 passed
ruff check src tests scripts                       # All checks passed
PYTHONPATH=src python scripts/validate_config.py   # 0 error, 0 warning
```

Frontend tidak berubah di pekerjaan ini, jadi gate web tidak dijalankan.
