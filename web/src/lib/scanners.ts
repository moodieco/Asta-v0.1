import type { ConfigScanner, SetupInfo, SystemInfo } from "@/lib/api"
import { isClosed, isWin, statsOf, type Signal } from "@/lib/metrics"

export type ScannerHealth = "running" | "warning" | "error" | "stopped"

export interface MarketMeta {
  label: string
  tone: "info" | "mint" | "warn"
  soft: string
  text: string
}

export const MARKETS: Record<string, MarketMeta> = {
  stock: { label: "Stocks", tone: "info", soft: "bg-info-soft", text: "text-info" },
  crypto: { label: "Crypto", tone: "mint", soft: "bg-mint-soft", text: "text-mint" },
  forex: { label: "Forex", tone: "warn", soft: "bg-warn-soft", text: "text-warn" },
}

export function marketMeta(market: string): MarketMeta {
  return MARKETS[market] ?? { label: market, tone: "info", soft: "bg-surface-3", text: "text-dim" }
}

export interface ScannerRow {
  id: string
  name: string
  market: string
  timeframe: string
  enabled: boolean
  version: string
  universe: string[]
  covered: string[]
  lastScan: string | null
  firstSignal: string | null
  totalSignals: number
  openSignals: number
  closedSignals: number
  wins: number
  losses: number
  winRate: number
  netR: number
  expectancy: number
  health: ScannerHealth
  healthLabel: string
  errors: number
}

export const APP_VERSION = "0.1.0"

export function buildScannerRows({
  scanners,
  setup,
  system,
  signals,
  overrides,
}: {
  scanners: ConfigScanner[]
  setup: SetupInfo | null
  system: SystemInfo | null
  signals: Signal[]
  overrides: Record<string, boolean>
}): ScannerRow[] {
  const recentErrors = (system?.logs?.recent ?? []).filter((line) => line.level === "error")
  const engineUp = Boolean(system && system.available !== false)
  const now = Date.now()

  return scanners.map((scanner) => {
    const own = signals.filter(
      (s) => s.scannerId === scanner.id || (!s.scannerId && s.scanner === scanner.name),
    )
    const closed = own.filter(isClosed)
    const wins = own.filter(isWin).length
    const stats = statsOf(own)
    const enabled = overrides[scanner.id] ?? scanner.enabled
    const sorted = [...own].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    const lastScan = sorted[0]?.createdAt ?? null
    const firstSignal = sorted.length ? sorted[sorted.length - 1].createdAt : null
    const universe = setup?.markets?.[scanner.market]?.symbols ?? []
    const covered = [...new Set(own.map((s) => s.symbol))].sort()
    const errors = recentErrors.filter(
      (line) => line.message.includes(scanner.id) || line.module.includes(scanner.id),
    ).length
    const staleHours = lastScan ? (now - new Date(lastScan).getTime()) / 3_600_000 : null

    let health: ScannerHealth = "running"
    let healthLabel = "Running"
    if (!enabled) {
      health = "stopped"
      healthLabel = "Disabled"
    } else if (!engineUp) {
      health = "warning"
      healthLabel = "Engine offline"
    } else if (errors > 0) {
      health = "error"
      healthLabel = `${errors} error${errors > 1 ? "s" : ""}`
    } else if (!lastScan) {
      health = "warning"
      healthLabel = "Idle · no signals"
    } else if (staleHours !== null && staleHours > 36) {
      health = "warning"
      healthLabel = "No recent scan"
    }

    return {
      id: scanner.id,
      name: scanner.name,
      market: scanner.market,
      timeframe: scanner.timeframe,
      enabled,
      version: APP_VERSION,
      universe,
      covered,
      lastScan,
      firstSignal,
      totalSignals: own.length,
      openSignals: own.filter((s) => s.status === "open").length,
      closedSignals: closed.length,
      wins,
      losses: closed.length - wins,
      winRate: stats.winRate,
      netR: stats.netR,
      expectancy: stats.expectancy,
      health,
      healthLabel,
      errors,
    }
  })
}

/* ---------------------------------------------------------------- *
 * Activity: signals per day for a scanner (real rows only)
 * ---------------------------------------------------------------- */

export interface ActivityDay {
  day: string
  signals: number
  closed: number
  netR: number
}

export function activitySeries(signals: Signal[], days = 14): ActivityDay[] {
  const out: ActivityDay[] = []
  const today = new Date()
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today.getTime() - i * 86_400_000)
    const key = d.toISOString().slice(0, 10)
    const rows = signals.filter((s) => s.createdAt.slice(0, 10) === key)
    out.push({
      day: key,
      signals: rows.length,
      closed: rows.filter(isClosed).length,
      netR: rows.filter(isClosed).reduce((acc, s) => acc + (s.realizedR ?? 0), 0),
    })
  }
  return out
}

export function symbolCoverage(signals: Signal[]): { symbol: string; total: number; winRate: number; netR: number }[] {
  const map = new Map<string, Signal[]>()
  for (const s of signals) {
    const arr = map.get(s.symbol)
    if (arr) arr.push(s)
    else map.set(s.symbol, [s])
  }
  return [...map.entries()]
    .map(([symbol, rows]) => {
      const stats = statsOf(rows)
      return { symbol, total: rows.length, winRate: stats.winRate, netR: stats.netR }
    })
    .sort((a, b) => b.total - a.total)
}
