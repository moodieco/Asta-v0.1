import { useMemo } from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { cn } from "@/lib/utils"
import { fmtR } from "@/lib/format"
import type { Calibration, DayCell, EquityPoint, GroupRow, RBucket } from "@/lib/metrics"

/* Pastel chart palette, aligned with the design tokens in index.css. */
export const CHART = {
  up: "#17b890",
  upSoft: "rgba(23,184,144,0.16)",
  down: "#f4677f",
  downSoft: "rgba(244,103,127,0.14)",
  blue: "#5b8def",
  blueSoft: "rgba(91,141,239,0.16)",
  yellow: "#e9b356",
  yellowSoft: "rgba(233,179,86,0.18)",
  pink: "#ef8bbb",
  pinkSoft: "rgba(239,139,187,0.16)",
  violet: "#a394f0",
  violetSoft: "rgba(163,148,240,0.16)",
  grid: "#eef2f7",
  axis: "#9aa7b8",
  zero: "#dde4ee",
}

const UP = CHART.up
const DOWN = CHART.down
const GRID = CHART.grid
const AXIS = CHART.axis

const tickStyle = { fill: AXIS, fontSize: 10, fontFamily: "ui-sans-serif, system-ui" }

function TipShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-2.5 py-2 text-[11px] shadow-[var(--shadow-pop)]">
      {children}
    </div>
  )
}

/* ---------------- Equity curve ---------------- */
export function EquityChart({ data, height = 260 }: { data: EquityPoint[]; height?: number }) {
  const last = data.length ? data[data.length - 1].cum : 0
  const stroke = last >= 0 ? UP : DOWN
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
        <defs>
          <linearGradient id="eq-up" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={UP} stopOpacity={0.26} />
            <stop offset="70%" stopColor={UP} stopOpacity={0.05} />
            <stop offset="100%" stopColor={UP} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="eq-down" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={DOWN} stopOpacity={0.05} />
            <stop offset="100%" stopColor={DOWN} stopOpacity={0.24} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} strokeDasharray="3 4" vertical={false} />
        <XAxis
          dataKey="index"
          tick={tickStyle}
          tickLine={false}
          axisLine={{ stroke: CHART.zero }}
          minTickGap={40}
          tickFormatter={(v) => `#${v}`}
        />
        <YAxis tick={tickStyle} tickLine={false} axisLine={false} width={52} tickFormatter={(v) => `${v}R`} />
        <ReferenceLine y={0} stroke={CHART.zero} strokeDasharray="4 4" />
        <Tooltip
          cursor={{ stroke: CHART.zero, strokeDasharray: "4 4" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const p = payload[0].payload as EquityPoint
            return (
              <TipShell>
                <div className="mb-1 font-medium text-ink">
                  Trade #{p.index} · {p.symbol}
                </div>
                <div className="flex items-center justify-between gap-3 text-faint">
                  <span>Closed R</span>
                  <span className={cn("tabnum", p.r >= 0 ? "text-up" : "text-down")}>{fmtR(p.r)}</span>
                </div>
                <div className="flex items-center justify-between gap-3 text-faint">
                  <span>Cumulative</span>
                  <span className="tabnum text-ink">{fmtR(p.cum)}</span>
                </div>
                <div className="mt-1 text-[10px] text-faint">
                  {new Date(p.t).toISOString().slice(0, 16).replace("T", " ")}Z
                </div>
              </TipShell>
            )
          }}
        />
        <Area
          type="monotone"
          dataKey="cum"
          stroke={stroke}
          strokeWidth={1.8}
          fill={last >= 0 ? "url(#eq-up)" : "url(#eq-down)"}
          isAnimationActive={false}
          dot={false}
          activeDot={{ r: 3, fill: stroke, stroke: "#ffffff", strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

/* ---------------- R distribution ---------------- */
export function RDistribution({ buckets, height = 190 }: { buckets: RBucket[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={buckets} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 4" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ ...tickStyle, fontSize: 9 }}
          tickLine={false}
          axisLine={{ stroke: CHART.zero }}
          interval={0}
        />
        <YAxis tick={tickStyle} tickLine={false} axisLine={false} width={40} />
        <Tooltip
          cursor={{ fill: "rgba(16,24,40,0.03)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const b = payload[0].payload as RBucket
            return (
              <TipShell>
                <div className="text-ink">{b.label}</div>
                <div className="tabnum text-faint">{b.count} trades</div>
              </TipShell>
            )
          }}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {buckets.map((b) => (
            <Cell key={b.label} fill={b.isWin ? "rgba(23,184,144,0.55)" : "rgba(244,103,127,0.5)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ---------------- Per-scanner performance ---------------- */
export function ScannerBars({ rows, height }: { rows: GroupRow[]; height?: number }) {
  const data = useMemo(() => rows.filter((r) => r.closed > 0).slice(0, 10), [rows])
  const h = height ?? Math.max(150, data.length * 30 + 28)
  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart data={data} layout="vertical" margin={{ top: 2, right: 18, bottom: 2, left: 6 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 4" horizontal={false} />
        <XAxis type="number" tick={tickStyle} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}R`} />
        <YAxis
          type="category"
          dataKey="label"
          tick={{ ...tickStyle, fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          width={112}
        />
        <ReferenceLine x={0} stroke={CHART.zero} />
        <Tooltip
          cursor={{ fill: "rgba(16,24,40,0.03)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const r = payload[0].payload as GroupRow
            return (
              <TipShell>
                <div className="mb-1 font-medium text-ink">{r.label}</div>
                <div className="tabnum text-faint">
                  net {fmtR(r.netR)} · {r.winRate.toFixed(1)}% win · n={r.closed}
                </div>
                <div className="tabnum text-faint">expectancy {fmtR(r.expectancy, 3)}</div>
              </TipShell>
            )
          }}
        />
        <Bar dataKey="netR" radius={[0, 4, 4, 0]} isAnimationActive={false} barSize={13}>
          {data.map((r) => (
            <Cell key={r.key} fill={r.netR >= 0 ? "rgba(23,184,144,0.6)" : "rgba(244,103,127,0.55)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ---------------- Confidence calibration ---------------- */
export function CalibrationChart({ rows, height = 170 }: { rows: Calibration[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -20 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 4" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ ...tickStyle, fontSize: 9 }}
          tickLine={false}
          axisLine={{ stroke: CHART.zero }}
        />
        <YAxis tick={tickStyle} tickLine={false} axisLine={false} width={44} tickFormatter={(v) => `${v}%`} />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const c = payload[0].payload as Calibration
            return (
              <TipShell>
                <div className="text-ink">confidence {c.label}</div>
                <div className="tabnum text-faint">
                  {c.winRate.toFixed(1)}% win · n={c.n}
                </div>
                <div className="tabnum text-faint">expectancy {fmtR(c.expectancy, 3)}</div>
              </TipShell>
            )
          }}
        />
        <Line
          type="monotone"
          dataKey="winRate"
          stroke={CHART.blue}
          strokeWidth={1.8}
          dot={{ r: 2.6, fill: CHART.blue, stroke: "#ffffff", strokeWidth: 1.5 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

/* ---------------- Calendar heatmap ---------------- */
const dayMs = 86400000

function heatColor(cell: DayCell | undefined): string {
  if (!cell || cell.n === 0) return "#f1f4f8"
  const intensity = Math.min(1, Math.abs(cell.netR) / 6)
  if (cell.netR > 0) return `rgba(23,184,144,${0.16 + intensity * 0.62})`
  if (cell.netR < 0) return `rgba(244,103,127,${0.16 + intensity * 0.6})`
  return `rgba(154,167,184,${0.2 + Math.min(1, cell.n / 10) * 0.25})`
}

export function CalendarHeat({
  days,
  cells,
  weeks = 26,
}: {
  days: string[]
  cells: Map<string, DayCell>
  weeks?: number
}) {
  const columns = useMemo(() => {
    const end = new Date(`${days[days.length - 1]}T00:00:00Z`)
    const start = new Date(end.getTime() - (weeks * 7 - 1) * dayMs)
    const grid: { label: string; cells: { day: string; cell?: DayCell }[] }[] = []
    let cursor = new Date(start)
    const shift = (cursor.getUTCDay() + 6) % 7
    cursor = new Date(cursor.getTime() - shift * dayMs)
    while (cursor <= end) {
      const col: { label: string; cells: { day: string; cell?: DayCell }[] } = { label: "", cells: [] }
      for (let i = 0; i < 7; i++) {
        const d = new Date(cursor.getTime() + i * dayMs)
        const key = d.toISOString().slice(0, 10)
        if (i === 0) col.label = key
        col.cells.push({ day: key, cell: cells.get(key) })
      }
      grid.push(col)
      cursor = new Date(cursor.getTime() + 7 * dayMs)
    }
    return grid
  }, [days, cells, weeks])

  return (
    <div className="overflow-x-auto pb-1">
      <div className="flex gap-[3px]">
        {columns.map((col, ci) => {
          const d = new Date(`${col.label}T00:00:00Z`)
          const showMonth = ci === 0 || d.getUTCDate() <= 7
          return (
            <div key={col.label} className="flex flex-col gap-[3px]">
              <div className="mb-0.5 h-3 text-[9px] leading-3 text-faint">
                {showMonth ? d.toLocaleString("en-GB", { month: "short", timeZone: "UTC" }) : ""}
              </div>
              {col.cells.map(({ day, cell }) => (
                <div
                  key={day}
                  title={
                    cell
                      ? `${day} · ${cell.n} signals · ${cell.wins}W/${cell.losses}L · net ${cell.netR >= 0 ? "+" : ""}${cell.netR.toFixed(1)}R`
                      : `${day} · no signals`
                  }
                  className="h-[11px] w-[11px] rounded-[3px] transition-transform hover:scale-[1.3]"
                  style={{ background: heatColor(cell) }}
                />
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ---------------- Symbol heat grid ---------------- */
export function SymbolHeat({ rows }: { rows: GroupRow[] }) {
  const sorted = [...rows].sort((a, b) => b.netR - a.netR)
  const max = Math.max(1, ...sorted.map((r) => Math.abs(r.netR)))
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
      {sorted.map((r) => {
        const strength = Math.abs(r.netR) / max
        return (
          <div
            key={r.key}
            className="rounded-xl border border-line p-2"
            style={{
              background:
                r.netR >= 0
                  ? `rgba(23,184,144,${0.04 + strength * 0.12})`
                  : `rgba(244,103,127,${0.04 + strength * 0.12})`,
            }}
          >
            <div className="flex items-center justify-between gap-1">
              <span className="truncate text-[11.5px] font-medium text-ink">{r.key}</span>
              <span className={cn("tabnum text-[11px]", r.netR >= 0 ? "text-up" : "text-down")}>
                {fmtR(r.netR, 1)}
              </span>
            </div>
            <div className="tabnum mt-0.5 text-[10px] text-faint">
              {r.winRate.toFixed(0)}% · {r.closed} closed
            </div>
          </div>
        )
      })}
    </div>
  )
}

/* ---------------- Donut ---------------- */

export interface DonutSlice {
  label: string
  value: number
  color: string
}

export function Donut({
  slices,
  size = 132,
  thickness = 14,
  centerLabel,
  centerValue,
}: {
  slices: DonutSlice[]
  size?: number
  thickness?: number
  centerLabel?: string
  centerValue?: string
}) {
  const total = slices.reduce((acc, slice) => acc + slice.value, 0)
  const radius = (size - thickness) / 2
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <div className="flex items-center gap-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0 -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#f1f4f8"
          strokeWidth={thickness}
        />
        {total > 0
          ? slices.map((slice) => {
              const length = (slice.value / total) * circumference
              const dash = `${Math.max(0, length - 3)} ${circumference - Math.max(0, length - 3)}`
              const element = (
                <circle
                  key={slice.label}
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke={slice.color}
                  strokeWidth={thickness}
                  strokeDasharray={dash}
                  strokeDashoffset={-offset}
                  strokeLinecap="round"
                />
              )
              offset += length
              return element
            })
          : null}
        {centerValue ? (
          <g className="rotate-90" style={{ transformOrigin: "center" }}>
            <text
              x="50%"
              y="47%"
              textAnchor="middle"
              className="fill-ink"
              style={{ fontSize: 17, fontWeight: 600 }}
            >
              {centerValue}
            </text>
            <text x="50%" y="60%" textAnchor="middle" fill="#8b97a8" style={{ fontSize: 9 }}>
              {centerLabel ?? ""}
            </text>
          </g>
        ) : null}
      </svg>
      <div className="min-w-0 flex-1 space-y-1.5">
        {slices.map((slice) => {
          const pct = total ? (slice.value / total) * 100 : 0
          return (
            <div key={slice.label} className="flex items-center gap-2 text-[11.5px]">
              <span className="h-2 w-2 shrink-0 rounded-[3px]" style={{ background: slice.color }} />
              <span className="min-w-0 flex-1 truncate text-dim">{slice.label}</span>
              <span className="tabnum text-faint">{slice.value}</span>
              <span className="tabnum w-9 text-right text-ink">{pct.toFixed(0)}%</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ---------------- Sparkline bars (activity) ---------------- */

export function MiniBars({
  values,
  color = CHART.blue,
  height = 34,
  className,
  labels,
}: {
  values: number[]
  color?: string
  height?: number
  className?: string
  labels?: string[]
}) {
  const max = Math.max(1, ...values)
  return (
    <div className={cn("flex items-end gap-[2px]", className)} style={{ height }}>
      {values.map((value, index) => (
        <div
          key={index}
          title={labels?.[index] ? `${labels[index]} · ${value}` : String(value)}
          className="flex-1 rounded-[2px] transition-colors"
          style={{
            height: `${Math.max(2, (value / max) * 100)}%`,
            background: value === 0 ? "#eef2f7" : color,
            opacity: value === 0 ? 1 : 0.75,
          }}
        />
      ))}
    </div>
  )
}
