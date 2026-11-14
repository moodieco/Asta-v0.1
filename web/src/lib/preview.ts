import { useSyncExternalStore } from "react"

/*
 * Preview layer.
 *
 * ASTA's HTTP API is read-only and exposes signals + runtime state only. The
 * installer, alert delivery log and version history have no backend yet, so
 * those screens run on this local, clearly-labelled preview store. Nothing here
 * claims to be live: every value is tagged `sample` and the UI renders a
 * "Preview" chip next to it. Actions persist to localStorage so the flows can be
 * exercised end to end without inventing a server API.
 */

export type Market = "stock" | "crypto" | "forex"
export type UploadStatus = "installed" | "failed" | "validated" | "superseded"

export interface UploadRecord {
  id: string
  name: string
  scannerId: string
  market: Market
  version: string
  uploadedAt: string
  status: UploadStatus
  sizeBytes: number
  timeframes: string[]
  description: string
  dependencies: string[]
  changes: string[]
  compatibility: string
  sample: true
}

export interface AlertLogEntry {
  id: string
  market: Market
  at: string
  symbol: string
  scanner: string
  status: "delivered" | "failed"
  detail: string
  sample: true
}

export interface PreviewState {
  enabledOverrides: Record<string, boolean>
  uploads: UploadRecord[]
  alertLog: AlertLogEntry[]
  webhookDrafts: Record<string, string>
  acknowledged: Record<string, boolean>
}

/* ---------------------------------------------------------------- *
 * Deterministic seed (same preview on every reload, no flicker)
 * ---------------------------------------------------------------- */

function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const DAY = 86_400_000
const now = Date.now()
const daysAgo = (n: number, hour = 9) => {
  const d = new Date(now - n * DAY)
  d.setHours(hour, (n * 7) % 60, 0, 0)
  return d.toISOString()
}

const BASE_UPLOADS: UploadRecord[] = [
  {
    id: "up_cxs004_010",
    name: "EMA Pullback",
    scannerId: "CXS004_EMA_PULLBACK",
    market: "crypto",
    version: "0.1.0",
    uploadedAt: daysAgo(9, 11),
    status: "installed",
    sizeBytes: 18_432,
    timeframes: ["1h", "4h"],
    description: "Pulls back to the 20/50 EMA stack and fires on the reclaim candle.",
    dependencies: ["asta-core>=0.1"],
    changes: ["Initial drop", "Structure-based stop from the last swing low"],
    compatibility: "ASTA 0.1.x · core >= 0.1",
    sample: true,
  },
  {
    id: "up_sts002_010",
    name: "Breakout Trend",
    scannerId: "STS002_BREAKOUT_TREND",
    market: "stock",
    version: "0.1.0",
    uploadedAt: daysAgo(12, 15),
    status: "installed",
    sizeBytes: 15_104,
    timeframes: ["1d"],
    description: "Daily range breakout confirmed by relative volume and trend slope.",
    dependencies: ["asta-core>=0.1"],
    changes: ["Initial drop"],
    compatibility: "ASTA 0.1.x · core >= 0.1",
    sample: true,
  },
  {
    id: "up_cxs002_011",
    name: "Volume Spike",
    scannerId: "CXS002_VOLUME_SPIKE",
    market: "crypto",
    version: "0.1.1",
    uploadedAt: daysAgo(16, 10),
    status: "installed",
    sizeBytes: 12_880,
    timeframes: ["15m"],
    description: "Fires when volume expands past 3× the rolling mean on a closed candle.",
    dependencies: ["asta-core>=0.1", "indicators.volume"],
    changes: ["Spike multiplier is now configurable", "Skip candles still forming"],
    compatibility: "ASTA 0.1.x · core >= 0.1",
    sample: true,
  },
  {
    id: "up_cxs002_010",
    name: "Volume Spike",
    scannerId: "CXS002_VOLUME_SPIKE",
    market: "crypto",
    version: "0.1.0",
    uploadedAt: daysAgo(31, 14),
    status: "superseded",
    sizeBytes: 12_100,
    timeframes: ["15m"],
    description: "First release of the volume expansion scanner.",
    dependencies: ["asta-core>=0.1"],
    changes: ["Initial drop"],
    compatibility: "ASTA 0.1.0",
    sample: true,
  },
  {
    id: "up_fxs002_010",
    name: "EMA Crossover",
    scannerId: "FXS002_EMA_CROSSOVER",
    market: "forex",
    version: "0.1.0",
    uploadedAt: daysAgo(21, 8),
    status: "installed",
    sizeBytes: 16_240,
    timeframes: ["1h"],
    description: "20/50 EMA cross with a 100-period trend filter on the MT5 feed.",
    dependencies: ["asta-core>=0.1", "mt5-bridge"],
    changes: ["Initial drop", "Session-aware warmup"],
    compatibility: "ASTA 0.1.x · MT5 bridge",
    sample: true,
  },
  {
    id: "up_fxs001_010",
    name: "RSI Divergence",
    scannerId: "FXS001_RSI_DIVERGENCE",
    market: "forex",
    version: "0.1.0",
    uploadedAt: daysAgo(24, 16),
    status: "installed",
    sizeBytes: 14_560,
    timeframes: ["1h"],
    description: "Regular bullish/bearish divergence against the 120-bar lookback.",
    dependencies: ["asta-core>=0.1", "mt5-bridge"],
    changes: ["Initial drop"],
    compatibility: "ASTA 0.1.x · MT5 bridge",
    sample: true,
  },
  {
    id: "up_sts001_010",
    name: "EMA Trend",
    scannerId: "STS001_EMA_TREND",
    market: "stock",
    version: "0.1.0",
    uploadedAt: daysAgo(18, 9),
    status: "installed",
    sizeBytes: 11_980,
    timeframes: ["1d"],
    description: "Rides the daily 20/50 EMA trend with gap-aware entries.",
    dependencies: ["asta-core>=0.1"],
    changes: ["Initial drop"],
    compatibility: "ASTA 0.1.x · core >= 0.1",
    sample: true,
  },
  {
    id: "up_cxs003_012",
    name: "Breakout Trend",
    scannerId: "CXS003_BREAKOUT_TREND",
    market: "crypto",
    version: "0.1.2",
    uploadedAt: daysAgo(6, 13),
    status: "failed",
    sizeBytes: 17_002,
    timeframes: ["1h"],
    description: "30-bar breakout with ATR-scaled stops.",
    dependencies: ["asta-core>=0.1"],
    changes: ["Experimental ATR trailing stop"],
    compatibility: "requires core >= 0.2 (not installed)",
    sample: true,
  },
  {
    id: "up_cxs003_011",
    name: "Breakout Trend",
    scannerId: "CXS003_BREAKOUT_TREND",
    market: "crypto",
    version: "0.1.1",
    uploadedAt: daysAgo(20, 11),
    status: "installed",
    sizeBytes: 16_640,
    timeframes: ["1h"],
    description: "Breakout of the 30-bar range, confirmed by trend slope.",
    dependencies: ["asta-core>=0.1"],
    changes: ["Lookback now configurable", "Reject breakouts against the trend"],
    compatibility: "ASTA 0.1.x · core >= 0.1",
    sample: true,
  },
  {
    id: "up_cxs001_010",
    name: "RSI Divergence",
    scannerId: "CXS001_RSI_DIVERGENCE",
    market: "crypto",
    version: "0.1.0",
    uploadedAt: daysAgo(28, 10),
    status: "installed",
    sizeBytes: 13_760,
    timeframes: ["1h"],
    description: "Divergence between price pivots and RSI on a fixed 1h cadence.",
    dependencies: ["asta-core>=0.1"],
    changes: ["Initial drop"],
    compatibility: "ASTA 0.1.x · core >= 0.1",
    sample: true,
  },
]

const ALERT_SEED: { market: Market; symbol: string; scanner: string; failed: boolean; hours: number }[] = [
  { market: "crypto", symbol: "BTCUSDT", scanner: "Breakout Trend", failed: false, hours: 1 },
  { market: "crypto", symbol: "SOLUSDT", scanner: "RSI Divergence", failed: false, hours: 3 },
  { market: "stock", symbol: "NVDA", scanner: "EMA Trend", failed: false, hours: 5 },
  { market: "forex", symbol: "EUR_USD", scanner: "EMA Crossover", failed: true, hours: 7 },
  { market: "crypto", symbol: "ETHUSDT", scanner: "Volume Spike", failed: false, hours: 9 },
  { market: "crypto", symbol: "BNBUSDT", scanner: "Breakout Trend", failed: false, hours: 13 },
  { market: "stock", symbol: "AAPL", scanner: "Breakout Trend", failed: false, hours: 16 },
  { market: "forex", symbol: "USD_JPY", scanner: "RSI Divergence", failed: false, hours: 19 },
  { market: "crypto", symbol: "XRPUSDT", scanner: "EMA Pullback", failed: true, hours: 23 },
  { market: "stock", symbol: "TSLA", scanner: "EMA Trend", failed: false, hours: 27 },
  { market: "forex", symbol: "GBP_USD", scanner: "EMA Crossover", failed: false, hours: 31 },
  { market: "crypto", symbol: "SOLUSDT", scanner: "Breakout Trend", failed: false, hours: 35 },
  { market: "stock", symbol: "MSFT", scanner: "Breakout Trend", failed: false, hours: 40 },
  { market: "crypto", symbol: "BTCUSDT", scanner: "Volume Spike", failed: false, hours: 44 },
]

const BASE_ALERTS: AlertLogEntry[] = ALERT_SEED.map((row, index) => ({
  id: `al_${index + 1}`,
  market: row.market,
  at: new Date(now - row.hours * 3_600_000).toISOString(),
  symbol: row.symbol,
  scanner: row.scanner,
  status: row.failed ? "failed" : "delivered",
  detail: row.failed
    ? "Discord answered 429 — rate limited, retry scheduled"
    : "Delivered to the market channel",
  sample: true,
}))

/* ---------------------------------------------------------------- *
 * Store
 * ---------------------------------------------------------------- */

const KEY = "asta.preview.v1"

function initial(): PreviewState {
  return {
    enabledOverrides: {},
    uploads: BASE_UPLOADS,
    alertLog: BASE_ALERTS,
    webhookDrafts: {},
    acknowledged: {},
  }
}

function load(): PreviewState {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return initial()
    const parsed = JSON.parse(raw) as Partial<PreviewState>
    return {
      enabledOverrides: parsed.enabledOverrides ?? {},
      uploads: Array.isArray(parsed.uploads) && parsed.uploads.length ? parsed.uploads : BASE_UPLOADS,
      alertLog: Array.isArray(parsed.alertLog) && parsed.alertLog.length ? parsed.alertLog : BASE_ALERTS,
      webhookDrafts: parsed.webhookDrafts ?? {},
      acknowledged: parsed.acknowledged ?? {},
    }
  } catch {
    return initial()
  }
}

let state: PreviewState = load()
const listeners = new Set<() => void>()

function commit(next: PreviewState) {
  state = next
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* preview state is optional */
  }
  listeners.forEach((fn) => fn())
}

function subscribe(fn: () => void) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function usePreview(): PreviewState {
  return useSyncExternalStore(subscribe, () => state, () => state)
}

export const previewActions = {
  setScannerEnabled(scannerId: string, enabled: boolean) {
    commit({ ...state, enabledOverrides: { ...state.enabledOverrides, [scannerId]: enabled } })
  },
  addUpload(record: UploadRecord) {
    commit({ ...state, uploads: [record, ...state.uploads] })
  },
  setUploadStatus(id: string, status: UploadStatus) {
    commit({
      ...state,
      uploads: state.uploads.map((row) => (row.id === id ? { ...row, status } : row)),
    })
  },
  removeUpload(id: string) {
    commit({ ...state, uploads: state.uploads.filter((row) => row.id !== id) })
  },
  saveWebhookDraft(market: string, value: string) {
    commit({ ...state, webhookDrafts: { ...state.webhookDrafts, [market]: value } })
  },
  retryAlert(id: string) {
    commit({
      ...state,
      alertLog: state.alertLog.map((row) =>
        row.id === id
          ? { ...row, status: "delivered", at: new Date().toISOString(), detail: "Retried — delivered" }
          : row,
      ),
    })
  },
  retryAllFailed(market: string) {
    commit({
      ...state,
      alertLog: state.alertLog.map((row) =>
        row.market === market && row.status === "failed"
          ? { ...row, status: "delivered", at: new Date().toISOString(), detail: "Retried — delivered" }
          : row,
      ),
    })
  },
  acknowledge(key: string) {
    commit({ ...state, acknowledged: { ...state.acknowledged, [key]: true } })
  },
  reset() {
    commit(initial())
  },
}

/* ---------------------------------------------------------------- *
 * Helpers shared by the pages
 * ---------------------------------------------------------------- */

export function alertStats(entries: AlertLogEntry[]) {
  const delivered = entries.filter((e) => e.status === "delivered").length
  const failed = entries.length - delivered
  return {
    total: entries.length,
    delivered,
    failed,
    successRate: entries.length ? (delivered / entries.length) * 100 : 0,
    lastDelivered: entries.find((e) => e.status === "delivered")?.at ?? null,
  }
}

export function versionChain(uploads: UploadRecord[], scannerId: string): UploadRecord[] {
  return uploads
    .filter((row) => row.scannerId === scannerId)
    .sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt))
}

const rng = mulberry32(20261114)
export function nextUploadId(prefix = "up"): string {
  return `${prefix}_${Math.floor(rng() * 1e6).toString(36)}_${Date.now().toString(36).slice(-4)}`
}
