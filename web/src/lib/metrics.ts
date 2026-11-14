export type Status = "hit_tp" | "hit_sl" | "open" | "expired" | string

export interface Signal {
  id: number
  signalId: string
  scannerId: string
  scanner: string
  market: string
  symbol: string
  timeframe: string
  side: "long" | "short" | string
  confidence: number | null
  price: number | null
  stopLoss: number | null
  takeProfit: number | null
  riskReward: number | null
  riskPct: number | null
  atr: number | null
  levelsSource: string
  status: Status
  realizedR: number | null
  barsHeld: number | null
  createdAt: string
  closedAt: string | null
  expiresAt: string | null
  strategy: string
  reason: string
  source: string
  indicators: Record<string, unknown>
}

export interface Meta {
  generatedAt: string
  source: string
  total: number
  closed: number
  open: number
  wins: number
  losses: number
  winRate: number
  expectancyR: number
  netR: number
  profitFactor: number | null
  firstSignal: string | null
  lastSignal: string | null
}

export interface Dataset {
  meta: Meta
  signals: Signal[]
}

export const EMPTY_META: Meta = {
  generatedAt: new Date().toISOString(),
  source: "api",
  total: 0,
  closed: 0,
  open: 0,
  wins: 0,
  losses: 0,
  winRate: 0,
  expectancyR: 0,
  netR: 0,
  profitFactor: null,
  firstSignal: null,
  lastSignal: null,
}

/**
 * The dashboard is served by `asta serve`, so the browser talks to the same
 * origin it was loaded from. One request returns the whole history; every
 * aggregate below is computed client-side, which is what makes the range switch
 * and table filters instant.
 */
export async function fetchDataset(init?: RequestInit): Promise<Dataset> {
  const response = await fetch("/api/signals", {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    throw new Error(`GET /api/signals -> ${response.status} ${response.statusText}`)
  }
  const payload = (await response.json()) as Partial<Dataset> & { meta?: Meta }
  if (!payload || !Array.isArray(payload.signals)) {
    throw new Error("unexpected payload from /api/signals")
  }
  return { meta: payload.meta ?? EMPTY_META, signals: payload.signals }
}

export const isClosed = (s: Signal) => (s.status === "hit_tp" || s.status === "hit_sl") && s.realizedR !== null
export const isWin = (s: Signal) => isClosed(s) && (s.realizedR as number) > 0

export interface Stats {
  n: number
  open: number
  closed: number
  wins: number
  losses: number
  winRate: number
  netR: number
  expectancy: number
  profitFactor: number | null
  avgWin: number
  avgLoss: number
  bestR: number
  worstR: number
  avgBars: number | null
  maxWinStreak: number
  maxLossStreak: number
  maxDrawdownR: number
}

export function statsOf(signals: Signal[]): Stats {
  const closed = signals.filter(isClosed).sort(
    (a, b) => new Date(a.closedAt ?? a.createdAt).getTime() - new Date(b.closedAt ?? b.createdAt).getTime(),
  )
  const wins = closed.filter(isWin)
  const losses = closed.filter((s) => !isWin(s))
  const netR = closed.reduce((acc, s) => acc + (s.realizedR as number), 0)
  const grossWin = wins.reduce((acc, s) => acc + (s.realizedR as number), 0)
  const grossLoss = Math.abs(losses.reduce((acc, s) => acc + (s.realizedR as number), 0))
  const avgWin = wins.length ? grossWin / wins.length : 0
  const avgLoss = losses.length ? -grossLoss / losses.length : 0

  let cum = 0
  let peak = 0
  let maxDD = 0
  let winStreak = 0
  let lossStreak = 0
  let maxWinStreak = 0
  let maxLossStreak = 0
  for (const s of closed) {
    const r = s.realizedR as number
    cum += r
    peak = Math.max(peak, cum)
    maxDD = Math.max(maxDD, peak - cum)
    if (r > 0) {
      winStreak += 1
      lossStreak = 0
      maxWinStreak = Math.max(maxWinStreak, winStreak)
    } else {
      lossStreak += 1
      winStreak = 0
      maxLossStreak = Math.max(maxLossStreak, lossStreak)
    }
  }

  const bars = closed.filter((s) => s.barsHeld !== null).map((s) => s.barsHeld as number)

  return {
    n: signals.length,
    open: signals.filter((s) => s.status === "open").length,
    closed: closed.length,
    wins: wins.length,
    losses: losses.length,
    winRate: closed.length ? (wins.length / closed.length) * 100 : 0,
    netR,
    expectancy: closed.length ? netR / closed.length : 0,
    profitFactor: grossLoss > 0 ? grossWin / grossLoss : null,
    avgWin,
    avgLoss,
    bestR: closed.length ? Math.max(...closed.map((s) => s.realizedR as number)) : 0,
    worstR: closed.length ? Math.min(...closed.map((s) => s.realizedR as number)) : 0,
    avgBars: bars.length ? bars.reduce((a, b) => a + b, 0) / bars.length : null,
    maxWinStreak,
    maxLossStreak,
    maxDrawdownR: maxDD,
  }
}

export interface EquityPoint {
  t: string
  cum: number
  r: number
  symbol: string
  index: number
}

export function equityCurve(signals: Signal[]): EquityPoint[] {
  const closed = signals
    .filter(isClosed)
    .sort(
      (a, b) => new Date(a.closedAt ?? a.createdAt).getTime() - new Date(b.closedAt ?? b.createdAt).getTime(),
    )
  let cum = 0
  return closed.map((s, i) => {
    const r = s.realizedR as number
    cum += r
    return { t: s.closedAt ?? s.createdAt, cum, r, symbol: s.symbol, index: i + 1 }
  })
}

export function drawdownSeries(curve: EquityPoint[]) {
  let peak = 0
  return curve.map((p) => {
    peak = Math.max(peak, p.cum)
    return { t: p.t, dd: p.cum - peak }
  })
}

export interface RBucket {
  label: string
  from: number
  to: number
  count: number
  isWin: boolean
}

export function rBuckets(signals: Signal[]): RBucket[] {
  const closed = signals.filter(isClosed)
  const buckets: RBucket[] = [
    { label: "≤ -1R", from: -Infinity, to: -1, count: 0, isWin: false },
    { label: "-1 → -0.5R", from: -1, to: -0.5, count: 0, isWin: false },
    { label: "-0.5 → 0R", from: -0.5, to: 0, count: 0, isWin: false },
    { label: "0 → 0.5R", from: 0, to: 0.5, count: 0, isWin: true },
    { label: "0.5 → 1R", from: 0.5, to: 1, count: 0, isWin: true },
    { label: "1 → 1.5R", from: 1, to: 1.5, count: 0, isWin: true },
    { label: "1.5 → 2R", from: 1.5, to: 2, count: 0, isWin: true },
    { label: "≥ 2R", from: 2, to: Infinity, count: 0, isWin: true },
  ]
  for (const s of closed) {
    const r = s.realizedR as number
    const b = buckets.find((b) => r > b.from && r <= b.to) ?? buckets[0]
    b.count += 1
  }
  return buckets
}

export interface GroupRow extends Stats {
  key: string
  label: string
}

export function groupStats(
  signals: Signal[],
  keyFn: (s: Signal) => string,
  labelFn: (key: string) => string = (k) => k,
): GroupRow[] {
  const groups = new Map<string, Signal[]>()
  for (const s of signals) {
    const k = keyFn(s) || "—"
    const arr = groups.get(k)
    if (arr) arr.push(s)
    else groups.set(k, [s])
  }
  return [...groups.entries()]
    .map(([key, arr]) => ({ key, label: labelFn(key), ...statsOf(arr) }))
    .sort((a, b) => b.netR - a.netR)
}

export interface DayCell {
  day: string
  n: number
  netR: number
  wins: number
  losses: number
  open: number
}

export function dailyStats(signals: Signal[]): Map<string, DayCell> {
  const map = new Map<string, DayCell>()
  for (const s of signals) {
    const day = s.createdAt.slice(0, 10)
    const cell = map.get(day) ?? { day, n: 0, netR: 0, wins: 0, losses: 0, open: 0 }
    cell.n += 1
    if (s.status === "open") cell.open += 1
    if (isClosed(s)) {
      const r = s.realizedR as number
      cell.netR += r
      if (r > 0) cell.wins += 1
      else cell.losses += 1
    }
    map.set(day, cell)
  }
  return map
}

export interface Calibration {
  label: string
  n: number
  winRate: number
  expectancy: number
  mid: number
}

export function calibration(signals: Signal[]): Calibration[] {
  const closed = signals.filter(isClosed)
  const edges = [0, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 1.0001]
  const rows: Calibration[] = []
  for (let i = 0; i < edges.length - 1; i++) {
    const lo = edges[i]
    const hi = edges[i + 1]
    const inBucket = closed.filter((s) => {
      const c = s.confidence ?? 0
      return c >= lo && c < hi
    })
    if (!inBucket.length) continue
    const wins = inBucket.filter(isWin).length
    rows.push({
      label: `${Math.round(lo * 100)}–${Math.round(hi * 100)}%`,
      mid: (lo + Math.min(hi, 1)) / 2,
      n: inBucket.length,
      winRate: (wins / inBucket.length) * 100,
      expectancy: inBucket.reduce((a, s) => a + (s.realizedR as number), 0) / inBucket.length,
    })
  }
  return rows
}

export function uniqueValues(signals: Signal[], pick: (s: Signal) => string): string[] {
  return [...new Set(signals.map(pick).filter(Boolean))].sort()
}

export function lastNDays(n: number): string[] {
  const out: string[] = []
  const today = new Date()
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    out.push(d.toISOString().slice(0, 10))
  }
  return out
}
