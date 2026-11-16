import { useCallback, useEffect, useRef, useState } from "react"
import { EMPTY_META, type Dataset, type Meta, type Signal } from "@/lib/metrics"

/* ------------------------------------------------------------------ *
 * Share token + access level
 * ------------------------------------------------------------------ */

const TOKEN =
  typeof window !== "undefined"
    ? new URLSearchParams(window.location.search).get("token") ?? ""
    : ""

export type AccessLevel = "editor" | "viewer"

export function authHeaders(extra?: HeadersInit): HeadersInit {
  const base: HeadersInit = { Accept: "application/json" }
  if (TOKEN) (base as Record<string, string>)["X-ASTA-Token"] = TOKEN
  return { ...base, ...(extra ?? {}) }
}

/* ------------------------------------------------------------------ *
 * Shapes returned by the ASTA dashboard API (all read-only).
 * ------------------------------------------------------------------ */

export interface Health {
  status: string
  version: string
  pid: number
  uptimeSeconds: number
  database: { available: boolean; signals: number }
  environment: string
  dryRun: boolean
  scanners: number
  enabledScanners: number
  cycles: number | null
  lastCycleAt: string | null
  storage: { backend: string; records: number | null }
  web: { host: string; port: number; webDir: string }
}

export interface ConfigScanner {
  id: string
  name: string
  market: string
  timeframe: string
  enabled: boolean
}

export interface ConfigInfo {
  available?: boolean
  environment: string
  dryRun: boolean
  storage: { backend: string }
  web: { host: string; port: number }
  markets: Record<string, { enabled: boolean; symbols: number }>
  providers: Record<string, { type: string; configured: boolean }>
  scanners: ConfigScanner[]
  channels: string[]
}

export interface WebhookInfo {
  env: string
  label: string
  configured: boolean
  masked: string
}

export interface SetupInfo {
  available: boolean
  complete: boolean
  completedAt: string | null
  updatedAt: string | null
  steps: Record<string, Record<string, unknown>>
  completedSteps: string[]
  webhooks: Record<string, WebhookInfo>
  channels: { market: string; env: string; label: string }[]
  providers: Record<
    string,
    { type: string; configured: boolean; terminalUrlConfigured: boolean; tokenConfigured: boolean }
  >
  markets: Record<string, { enabled: boolean; symbols: string[] }>
  scanners: ConfigScanner[]
  system: {
    dbPath: string
    dbExists: boolean
    host: string
    port: number
    environment: string
    root: string
  }
}

export interface LogLine {
  at: string
  level: "error" | "warning" | string
  module: string
  message: string
}

export interface SystemInfo {
  available?: boolean
  version: string
  pid: number
  startedAt: string
  uptimeSeconds: number
  loadAvg: number[] | null
  cpuPct: number | null
  rssBytes: number | null
  threads: number
  database: { path: string; sizeBytes: number; available: boolean; signals: number | null }
  logs: {
    path: string
    available: boolean
    sizeBytes?: number
    errors: number
    warnings: number
    sampledLines?: number
    recent: LogLine[]
  }
  cycles: number | null
  lastCycleAt: string | null
  storage: { backend: string; records: number | null }
  scanners: { total: number | null; enabled: number | null }
  environment: string
  dryRun: boolean
  web: { host: string; port: number; webDir: string }
}

/* ------------------------------------------------------------------ *
 * Fetch helpers
 * ------------------------------------------------------------------ */

export class ApiError extends Error {
  status: number
  constructor(message: string, status = 0) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      headers: authHeaders(init?.headers),
    })
  } catch (error) {
    throw new ApiError(
      `Cannot reach the ASTA engine (${path}). ${error instanceof Error ? error.message : ""}`.trim(),
    )
  }
  if (!response.ok) {
    throw new ApiError(`GET ${path} → ${response.status} ${response.statusText}`, response.status)
  }
  return (await response.json()) as T
}

export async function apiSend<T>(path: string, method: "POST" | "DELETE" = "POST", body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    throw new ApiError(
      `Cannot reach the ASTA engine (${path}). ${error instanceof Error ? error.message : ""}`.trim(),
    )
  }
  if (!response.ok) {
    let detail: string = response.statusText
    try {
      const parsed = (await response.json()) as { error?: string; detail?: string }
      detail = parsed.error ?? parsed.detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(`${method} ${path} → ${response.status} ${detail}`, response.status)
  }
  return (await response.json()) as T
}

export async function fetchSignals(init?: RequestInit): Promise<Dataset> {
  const payload = await apiGet<{ meta?: Meta; signals?: Signal[] }>("/api/signals", init)
  if (!Array.isArray(payload.signals)) throw new ApiError("unexpected payload from /api/signals")
  return { meta: payload.meta ?? EMPTY_META, signals: payload.signals }
}

/* ------------------------------------------------------------------ *
 * Offline cache: the signal history must still open when the engine is
 * down, so the last good dataset is kept in localStorage.
 * ------------------------------------------------------------------ */

const CACHE_KEY = "asta.dashboard.snapshot.v1"

interface CachedSnapshot {
  at: string
  dataset: Dataset
}

export function readCache(): CachedSnapshot | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as CachedSnapshot
    if (!parsed || !Array.isArray(parsed.dataset?.signals)) return null
    return parsed
  } catch {
    return null
  }
}

export function writeCache(dataset: Dataset): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ at: new Date().toISOString(), dataset }))
  } catch {
    /* quota exceeded — the dashboard still works, it just cannot go offline */
  }
}

/* ------------------------------------------------------------------ *
 * One hook for the whole app: signals + health + config + setup + system.
 * Signals are the slow resource (1 request returns the full history), so
 * they poll every 60s while health/system poll every 20s.
 * ------------------------------------------------------------------ */

export interface AppData {
  dataset: Dataset | null
  snapshotAt: string | null
  loading: boolean
  error: string | null
  cached: boolean
  health: Health | null
  healthError: string | null
  config: ConfigInfo | null
  setup: SetupInfo | null
  system: SystemInfo | null
  systemError: string | null
  lastRefresh: number
  refresh: () => void
}

export function useAppData(): AppData {
  const cached = useRef<CachedSnapshot | null>(readCache())
  const [dataset, setDataset] = useState<Dataset | null>(cached.current?.dataset ?? null)
  const [snapshotAt, setSnapshotAt] = useState<string | null>(cached.current?.at ?? null)
  const [isCached, setIsCached] = useState(Boolean(cached.current))
  const [loading, setLoading] = useState(!cached.current)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [config, setConfig] = useState<ConfigInfo | null>(null)
  const [setup, setSetup] = useState<SetupInfo | null>(null)
  const [system, setSystem] = useState<SystemInfo | null>(null)
  const [systemError, setSystemError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  const [lastRefresh, setLastRefresh] = useState(Date.now())

  const refresh = useCallback(() => setTick((n) => n + 1), [])

  useEffect(() => {
    let alive = true

    const loadSignals = () => {
      fetchSignals()
        .then((next) => {
          if (!alive) return
          setDataset(next)
          setSnapshotAt(new Date().toISOString())
          setIsCached(false)
          setError(null)
          writeCache(next)
        })
        .catch((err: unknown) => {
          if (!alive) return
          setError(err instanceof Error ? err.message : String(err))
          if (!cached.current) setLoading(false)
        })
        .finally(() => {
          if (alive) setLoading(false)
        })
    }

    const loadLive = () => {
      apiGet<Health>("/api/health")
        .then((next) => {
          if (!alive) return
          setHealth(next)
          setHealthError(null)
        })
        .catch((err: unknown) => {
          if (!alive) return
          setHealth(null)
          setHealthError(err instanceof Error ? err.message : String(err))
        })
      apiGet<SystemInfo>("/api/system")
        .then((next) => {
          if (!alive) return
          setSystem(next)
          setSystemError(null)
        })
        .catch((err: unknown) => {
          if (!alive) return
          setSystemError(err instanceof Error ? err.message : String(err))
        })
      apiGet<ConfigInfo>("/api/config")
        .then((next) => alive && setConfig(next))
        .catch(() => undefined)
      apiGet<SetupInfo>("/api/setup")
        .then((next) => alive && setSetup(next))
        .catch(() => undefined)
    }

    loadSignals()
    loadLive()
    setLastRefresh(Date.now())

    const signalTimer = setInterval(loadSignals, 60_000)
    const liveTimer = setInterval(loadLive, 20_000)
    return () => {
      alive = false
      clearInterval(signalTimer)
      clearInterval(liveTimer)
    }
  }, [tick])

  return {
    dataset,
    snapshotAt,
    loading,
    error,
    cached: isCached,
    health,
    healthError,
    config,
    setup,
    system,
    systemError,
    lastRefresh,
    refresh,
  }
}

/* ------------------------------------------------------------------ *
 * Small formatters that need bytes / durations
 * ------------------------------------------------------------------ */

export function fmtBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return "—"
  if (bytes < 1024) return `${bytes} B`
  const units = ["KB", "MB", "GB", "TB"]
  let value = bytes / 1024
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds < 0) return "—"
  const s = Math.floor(seconds)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s % 60}s`
  return `${s}s`
}
