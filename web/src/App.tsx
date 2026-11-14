import { useEffect, useMemo, useState } from "react"
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CalendarDays,
  CircleDot,
  Database,
  Gauge,
  History,
  LayoutGrid,
  Target,
  TrendingUp,
  Zap,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtInt, fmtPct, fmtR, relTime } from "@/lib/format"
import {
  EMPTY_META,
  calibration,
  dailyStats,
  equityCurve,
  fetchDataset,
  groupStats,
  isClosed,
  lastNDays,
  rBuckets,
  statsOf,
  type Dataset,
  type Signal,
} from "@/lib/metrics"
import { Card, CardHeader, Badge, Segmented, MiniStat, Meter, Empty, CountUp } from "@/components/ui"
import { CalendarHeat, CalibrationChart, EquityChart, RDistribution, ScannerBars, SymbolHeat } from "@/components/charts"
import { HistoryTable } from "@/components/history"
import { MagicCard } from "@/components/magicui/magic-card"
import { BorderBeam } from "@/components/magicui/border-beam"
import { DotPattern } from "@/components/magicui/dot-pattern"

type View = "overview" | "performance" | "history"
type Range = "all" | "90d" | "30d"

const NAV: { id: View; label: string; icon: React.ElementType; hint: string }[] = [
  { id: "overview", label: "Overview", icon: LayoutGrid, hint: "Equity, edge, rhythm" },
  { id: "performance", label: "Performance", icon: Gauge, hint: "By scanner, symbol, TF" },
  { id: "history", label: "History", icon: History, hint: "Every signal, filterable" },
]

function within(s: Signal, range: Range): boolean {
  if (range === "all") return true
  const days = range === "90d" ? 90 : 30
  const cutoff = Date.now() - days * 86400000
  return new Date(s.createdAt).getTime() >= cutoff
}

function Kpi({
  label,
  value,
  suffix,
  decimals = 0,
  footnote,
  tone = "neutral",
  accent = false,
  delay = 0,
}: {
  label: string
  value: number
  suffix?: string
  decimals?: number
  footnote?: React.ReactNode
  tone?: "up" | "down" | "neutral"
  accent?: boolean
  delay?: number
}) {
  return (
    <MagicCard
      className="relative overflow-hidden rounded-2xl"
      gradientColor="#0f1b1a"
      gradientOpacity={0.9}
      gradientFrom="#34d399"
      gradientTo="#0ea5a4"
    >
      <div className="px-4 py-3.5">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-wider text-faint">{label}</span>
          {tone !== "neutral" ? (
            tone === "up" ? (
              <ArrowUpRight className="h-3.5 w-3.5 text-emerald-400/80" />
            ) : (
              <ArrowDownRight className="h-3.5 w-3.5 text-rose-400/80" />
            )
          ) : null}
        </div>
        <div className="mt-1.5 flex items-baseline gap-0.5">
          <CountUp
            key={`${value}`}
            value={value}
            decimals={decimals}
            className={cn(
              "tabnum text-[26px] font-semibold leading-none tracking-tight",
              tone === "up" && "text-emerald-300",
              tone === "down" && "text-rose-300",
              tone === "neutral" && "text-ink",
            )}
          />
          {suffix ? <span className="text-[13px] font-medium text-faint">{suffix}</span> : null}
        </div>
        {footnote ? <div className="mt-2 text-[10.5px] leading-relaxed text-faint">{footnote}</div> : null}
      </div>
      {accent ? <BorderBeam size={90} duration={9} delay={0} colorFrom="#34d399" colorTo="#5eead4" /> : null}
    </MagicCard>
  )
}

export default function App() {
  const [view, setView] = useState<View>("overview")
  const [range, setRange] = useState<Range>("all")
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    const load = () => {
      fetchDataset()
        .then((next) => {
          if (!alive) return
          setDataset(next)
          setLoadError(null)
        })
        .catch((err: unknown) => {
          if (alive) setLoadError(err instanceof Error ? err.message : String(err))
        })
    }
    load()
    const timer = setInterval(load, 60_000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  const META = dataset?.meta ?? EMPTY_META
  const signals = useMemo(
    () => (dataset?.signals ?? []).filter((s) => within(s, range)),
    [dataset, range],
  )
  const stats = useMemo(() => statsOf(signals), [signals])
  const curve = useMemo(() => equityCurve(signals), [signals])
  const buckets = useMemo(() => rBuckets(signals), [signals])
  const byScanner = useMemo(() => groupStats(signals, (s) => s.scanner), [signals])
  const bySymbol = useMemo(() => groupStats(signals, (s) => s.symbol), [signals])
  const byTimeframe = useMemo(() => groupStats(signals, (s) => `${s.market} · ${s.timeframe}`), [signals])
  const bySide = useMemo(() => groupStats(signals, (s) => s.side), [signals])
  const calib = useMemo(() => calibration(signals), [signals])
  const days = useMemo(() => lastNDays(26 * 7), [])
  const calendar = useMemo(() => dailyStats(signals), [signals])

  const bestScanner = byScanner.filter((r) => r.closed >= 10)[0]
  const worstScanner = [...byScanner].filter((r) => r.closed >= 10).pop()
  const bestSymbol = [...bySymbol].filter((r) => r.closed >= 10)[0]
  const openNow = signals.filter((s) => s.status === "open")

  const tone = stats.netR >= 0 ? "up" : "down"

  if (!dataset) {
    return (
      <div className="grid min-h-screen place-items-center px-6">
        <div className="w-full max-w-md rounded-2xl border border-line bg-surface/70 p-6 text-center">
          {loadError ? (
            <>
              <div className="text-[13px] font-medium text-rose-300">Cannot reach the ASTA API</div>
              <p className="mt-2 text-[11.5px] leading-relaxed text-faint">
                The dashboard reads <code className="text-dim">/api/signals</code> from the local
                server. Start it with <code className="text-dim">asta serve</code>, or run the
                frontend in dev with <code className="text-dim">npm run dev</code> against that
                server.
              </p>
              <p className="mt-3 break-all rounded-lg border border-line/70 bg-black/30 px-2 py-1.5 text-left text-[10.5px] text-faint">
                {loadError}
              </p>
            </>
          ) : (
            <>
              <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line border-t-emerald-400" />
              <p className="mt-3 text-[11.5px] text-faint">Loading signal history…</p>
            </>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <div className="mx-auto flex w-full max-w-[1560px]">
        {/* Sidebar */}
        <aside className="sticky top-0 hidden h-screen w-[212px] shrink-0 flex-col border-r border-line/70 px-3 py-5 lg:flex">
          <div className="flex items-center gap-2 px-1.5">
            <div className="grid h-8 w-8 place-items-center rounded-lg border border-emerald-400/25 bg-emerald-400/10">
              <Zap className="h-4 w-4 text-emerald-300" />
            </div>
            <div className="leading-tight">
              <div className="text-[13px] font-semibold tracking-tight text-ink">ASTA</div>
              <div className="text-[10px] text-faint">v0.1 · signals</div>
            </div>
          </div>

          <nav className="mt-6 space-y-0.5">
            {NAV.map((item) => {
              const Icon = item.icon
              const active = view === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => setView(item.id)}
                  className={cn(
                    "group flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors",
                    active ? "bg-emerald-400/10 text-ink" : "text-dim hover:bg-white/[0.04] hover:text-ink",
                  )}
                >
                  <Icon className={cn("h-4 w-4 shrink-0", active ? "text-emerald-300" : "text-faint group-hover:text-dim")} />
                  <span className="flex-1">
                    <span className="block text-[12.5px] font-medium leading-tight">{item.label}</span>
                    <span className="block text-[10px] leading-tight text-faint">{item.hint}</span>
                  </span>
                  {active ? <span className="h-1 w-1 rounded-full bg-emerald-300" /> : null}
                </button>
              )
            })}
          </nav>

          <div className="mt-6 rounded-xl border border-line/70 bg-white/[0.02] p-3">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-faint">
              <Database className="h-3 w-3" /> data
            </div>
            <div className="mt-1.5 space-y-1 text-[10.5px] text-faint">
              <div className="flex justify-between gap-2">
                <span>signals</span>
                <span className="tabnum text-dim">{fmtInt(META.total)}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span>closed</span>
                <span className="tabnum text-dim">{fmtInt(META.closed)}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span>refreshed</span>
                <span className="text-dim">{relTime(META.generatedAt)}</span>
              </div>
            </div>
          </div>

          <div className="mt-auto px-1 text-[10px] leading-relaxed text-faint">
            <div className="flex items-center gap-1.5">
              <CircleDot className="h-3 w-3 text-emerald-400/70" />
              <span>sqlite · read-only export</span>
            </div>
            <p className="mt-1 break-all text-[9.5px] text-faint/80">auto-refresh · 60s</p>
          </div>
        </aside>

        {/* Main */}
        <main className="min-w-0 flex-1 px-4 pb-10 pt-5 sm:px-6">
          <header className="relative mb-5 overflow-hidden rounded-2xl border border-line/70 bg-surface/40 px-5 py-4">
            <DotPattern
              width={22}
              height={22}
              cr={0.8}
              className="absolute inset-0 text-emerald-200/[0.14] [mask-image:radial-gradient(340px_at_18%_0%,black,transparent)]"
            />
            <div className="relative flex flex-wrap items-end justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-[19px] font-semibold tracking-tight text-ink">
                    Signal{" "}
                    <span
                      className="inline-block animate-gradient bg-clip-text text-transparent"
                      style={
                        {
                          backgroundImage: "linear-gradient(90deg, #34d399, #7dd3fc, #34d399)",
                          backgroundSize: "300% 100%",
                        } as React.CSSProperties
                      }
                    >
                      performance
                    </span>
                  </h1>
                  <Badge tone={openNow.length ? "open" : "neutral"}>
                    <Activity className="h-2.5 w-2.5" />
                    {openNow.length} open
                  </Badge>
                </div>
                <p className="mt-1 text-[11.5px] text-faint">
                  {fmtInt(stats.closed)} closed trades · {META.firstSignal?.slice(0, 10)} → {META.lastSignal?.slice(0, 10)} · R multiples from realized_r
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Segmented<Range>
                  value={range}
                  onChange={setRange}
                  options={[
                    { value: "all", label: "All time" },
                    { value: "90d", label: "90d" },
                    { value: "30d", label: "30d" },
                  ]}
                />
              </div>
            </div>
          </header>

          {view === "overview" ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <Kpi
                    label="Win rate"
                    value={stats.winRate}
                    decimals={1}
                    suffix="%"
                    tone={stats.winRate >= 50 ? "up" : tone}
                    accent
                    footnote={
                      <div className="space-y-1.5">
                        <div className="flex justify-between">
                          <span>{fmtInt(stats.wins)} wins / {fmtInt(stats.losses)} losses</span>
                          <span className="tabnum">{fmtPct(stats.winRate)}</span>
                        </div>
                        <Meter pct={stats.winRate} tone={stats.winRate >= 50 ? "up" : "down"} />
                      </div>
                    }
                  />
                  <Kpi
                    label="Expectancy"
                    value={stats.expectancy}
                    decimals={3}
                    suffix="R / trade"
                    tone={stats.expectancy >= 0 ? "up" : "down"}
                    footnote={
                      <span>
                        avg win {fmtR(stats.avgWin, 2)} · avg loss {fmtR(stats.avgLoss, 2)}
                      </span>
                    }
                  />
                  <Kpi
                    label="Net result"
                    value={stats.netR}
                    decimals={1}
                    suffix="R"
                    tone={stats.netR >= 0 ? "up" : "down"}
                    footnote={
                      <span>
                        best {fmtR(stats.bestR, 1)} · worst {fmtR(stats.worstR, 1)} · max DD {stats.maxDrawdownR.toFixed(1)}R
                      </span>
                    }
                  />
                  <Kpi
                    label="Profit factor"
                    value={stats.profitFactor ?? 0}
                    decimals={2}
                    tone={(stats.profitFactor ?? 0) >= 1 ? "up" : "down"}
                    footnote={
                      <span>
                        {fmtInt(stats.open)} open · avg hold {stats.avgBars ? stats.avgBars.toFixed(1) : "—"} bars
                      </span>
                    }
                  />
                </div>

              <div className="grid gap-3 xl:grid-cols-3">
                <Card className="xl:col-span-2">
                  <CardHeader
                    title="Cumulative R"
                    subtitle="Every closed signal in sequence — the shape of the edge, not the story around it"
                    right={
                      <div className="flex items-center gap-3 text-[10.5px] text-faint">
                        <span className="flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> cumulative
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-rose-400" /> drawdown
                        </span>
                      </div>
                    }
                  />
                  <div className="px-1 pb-3">
                    {curve.length ? <EquityChart data={curve} height={248} /> : <Empty>No closed trades yet.</Empty>}
                  </div>
                </Card>

                <Card>
                  <CardHeader title="Edge diagnostics" subtitle="What the sequence hides in aggregates" />
                  <div className="space-y-2.5 px-5 pb-4">
                    <div className="rounded-xl border border-line/70 bg-white/[0.02] p-3">
                      <div className="text-[10px] uppercase tracking-wider text-faint">Streaks</div>
                      <div className="mt-1 grid grid-cols-2 gap-2">
                        <div>
                          <div className="tabnum text-[17px] font-semibold text-emerald-300">{stats.maxWinStreak}</div>
                          <div className="text-[10px] text-faint">max win streak</div>
                        </div>
                        <div>
                          <div className="tabnum text-[17px] font-semibold text-rose-300">{stats.maxLossStreak}</div>
                          <div className="text-[10px] text-faint">max loss streak</div>
                        </div>
                      </div>
                    </div>
                    <div className="rounded-xl border border-line/70 bg-white/[0.02] p-3">
                      <div className="text-[10px] uppercase tracking-wider text-faint">Scanners worth watching</div>
                      <div className="mt-1.5 space-y-1.5">
                        {bestScanner ? (
                          <div className="flex items-center justify-between gap-2">
                            <span className="flex items-center gap-1.5 text-[11.5px] text-dim">
                              <TrendingUp className="h-3 w-3 text-emerald-400" />
                              {bestScanner.label}
                            </span>
                            <span className="tabnum text-[11.5px] text-emerald-300">{fmtR(bestScanner.netR, 1)}</span>
                          </div>
                        ) : null}
                        {worstScanner ? (
                          <div className="flex items-center justify-between gap-2">
                            <span className="flex items-center gap-1.5 text-[11.5px] text-dim">
                              <ArrowDownRight className="h-3 w-3 text-rose-400" />
                              {worstScanner.label}
                            </span>
                            <span className="tabnum text-[11.5px] text-rose-300">{fmtR(worstScanner.netR, 1)}</span>
                          </div>
                        ) : null}
                        {bestSymbol ? (
                          <div className="flex items-center justify-between gap-2">
                            <span className="flex items-center gap-1.5 text-[11.5px] text-dim">
                              <Target className="h-3 w-3 text-sky-300" />
                              {bestSymbol.label}
                            </span>
                            <span className="tabnum text-[11.5px] text-sky-300">{fmtR(bestSymbol.netR, 1)}</span>
                          </div>
                        ) : null}
                      </div>
                    </div>
                    <div className="rounded-xl border border-line/70 bg-white/[0.02] p-3">
                      <div className="text-[10px] uppercase tracking-wider text-faint">Long vs short</div>
                      <div className="mt-1.5 space-y-1.5">
                        {bySide.map((r) => (
                          <div key={r.key}>
                            <div className="flex items-center justify-between text-[11px]">
                              <span className="uppercase text-dim">{r.key}</span>
                              <span className={cn("tabnum", r.netR >= 0 ? "text-emerald-300" : "text-rose-300")}>
                                {fmtR(r.netR, 1)} · {r.winRate.toFixed(0)}%
                              </span>
                            </div>
                            <div className="mt-1">
                              <Meter pct={r.winRate} tone={r.netR >= 0 ? "up" : "down"} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </Card>
              </div>

              <div className="grid gap-3 xl:grid-cols-2">
                <Card>
                  <CardHeader title="Outcome distribution" subtitle="How R lands: the 2:1 payoff profile in practice" right={<Badge tone={tone}>{tone === "up" ? "net positive" : "net negative"}</Badge>} />
                  <div className="px-2 pb-3">
                    <RDistribution buckets={buckets} height={188} />
                  </div>
                </Card>
                <Card>
                  <CardHeader
                    title="Confidence calibration"
                    subtitle="Does a higher score actually mean a better signal?"
                    right={<Badge tone="info">{calib.length} buckets</Badge>}
                  />
                  <div className="px-2 pb-3">
                    {calib.length ? <CalibrationChart rows={calib} height={188} /> : <Empty>Not enough closed signals.</Empty>}
                  </div>
                </Card>
              </div>

              <Card>
                <CardHeader
                  title="Signal rhythm"
                  subtitle="Each square is a day — green days net positive R, red days net negative, size = signals fired"
                  right={
                    <span className="flex items-center gap-1 text-[10.5px] text-faint">
                      <CalendarDays className="h-3 w-3" /> last 26 weeks
                    </span>
                  }
                />
                <div className="px-5 pb-4">
                  <CalendarHeat days={days} cells={calendar} weeks={26} />
                  <div className="mt-2 flex items-center justify-end gap-1.5 text-[10px] text-faint">
                    <span>loss</span>
                    <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: "rgba(251,113,133,0.8)" }} />
                    <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: "rgba(251,113,133,0.35)" }} />
                    <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: "rgba(255,255,255,0.06)" }} />
                    <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: "rgba(52,211,153,0.45)" }} />
                    <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: "rgba(52,211,153,0.85)" }} />
                    <span>gain</span>
                  </div>
                </div>
              </Card>
            </div>
          ) : null}

          {view === "performance" ? (
            <div className="space-y-3">
              <div className="grid gap-3 xl:grid-cols-3">
                <Card className="xl:col-span-2">
                  <CardHeader title="Net R by scanner" subtitle="Ranked by contribution — negative bars are the ones draining the book" />
                  <div className="px-2 pb-3">
                    <ScannerBars rows={byScanner} />
                  </div>
                </Card>
                <Card>
                  <CardHeader title="Timeframes" subtitle="Where the signals actually come from" />
                  <div className="space-y-2 px-5 pb-4">
                    {byTimeframe.map((r) => (
                      <div key={r.key} className="rounded-lg border border-line/60 bg-white/[0.02] px-3 py-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11.5px] text-dim">{r.label}</span>
                          <span className={cn("tabnum text-[11.5px]", r.netR >= 0 ? "text-emerald-300" : "text-rose-300")}>
                            {fmtR(r.netR, 1)}
                          </span>
                        </div>
                        <div className="tabnum mt-1 flex justify-between text-[10px] text-faint">
                          <span>{r.closed} closed</span>
                          <span>{r.winRate.toFixed(1)}% win · {fmtR(r.expectancy, 3)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>

              <Card>
                <CardHeader
                  title="Scanner ledger"
                  subtitle="Win rate, expectancy and profit factor per scanner (min. 1 closed trade)"
                  right={<Badge>{byScanner.length} scanners</Badge>}
                />
                <div className="overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="text-left text-[10px] uppercase tracking-wider text-faint">
                        <th className="px-5 py-2 font-medium">Scanner</th>
                        <th className="px-3 py-2 text-right font-medium">Closed</th>
                        <th className="px-3 py-2 text-right font-medium">Win rate</th>
                        <th className="px-3 py-2 text-right font-medium">Expectancy</th>
                        <th className="px-3 py-2 text-right font-medium">Net R</th>
                        <th className="px-3 py-2 text-right font-medium">PF</th>
                        <th className="px-3 py-2 text-right font-medium">Max DD</th>
                        <th className="px-3 py-2 font-medium">Consistency</th>
                      </tr>
                    </thead>
                    <tbody>
                      {byScanner.map((r) => (
                        <tr key={r.key} className="border-t border-line/50 hover:bg-white/[0.03]">
                          <td className="px-5 py-2 text-ink">{r.label}</td>
                          <td className="tabnum px-3 py-2 text-right text-dim">{r.closed}</td>
                          <td className="tabnum px-3 py-2 text-right text-dim">{r.winRate.toFixed(1)}%</td>
                          <td className={cn("tabnum px-3 py-2 text-right", r.expectancy >= 0 ? "text-emerald-300" : "text-rose-300")}>
                            {fmtR(r.expectancy, 3)}
                          </td>
                          <td className={cn("tabnum px-3 py-2 text-right", r.netR >= 0 ? "text-emerald-300" : "text-rose-300")}>
                            {fmtR(r.netR, 1)}
                          </td>
                          <td className="tabnum px-3 py-2 text-right text-dim">
                            {r.profitFactor === null ? "∞" : r.profitFactor.toFixed(2)}
                          </td>
                          <td className="tabnum px-3 py-2 text-right text-faint">{r.maxDrawdownR.toFixed(1)}R</td>
                          <td className="px-3 py-2">
                            <div className="w-24">
                              <Meter pct={r.winRate} tone={r.netR >= 0 ? "up" : "down"} />
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <div className="grid gap-3 xl:grid-cols-3">
                <Card className="xl:col-span-2">
                  <CardHeader title="Symbol map" subtitle="Colour strength = net R contribution · closed trades under each symbol" />
                  <div className="px-5 pb-4">
                    <SymbolHeat rows={bySymbol} />
                  </div>
                </Card>
                <Card>
                  <CardHeader title="Per-symbol detail" subtitle="Top 6 by net R" />
                  <div className="space-y-1.5 px-5 pb-4">
                    {[...bySymbol]
                      .sort((a, b) => b.netR - a.netR)
                      .slice(0, 6)
                      .map((r) => (
                        <div key={r.key} className="flex items-center justify-between gap-2 rounded-lg border border-line/60 bg-white/[0.02] px-2.5 py-1.5">
                          <div className="min-w-0">
                            <div className="truncate text-[11.5px] text-ink">{r.label}</div>
                            <div className="tabnum text-[10px] text-faint">
                              {r.closed} closed · {r.winRate.toFixed(0)}% win
                            </div>
                          </div>
                          <span className={cn("tabnum text-[11.5px]", r.netR >= 0 ? "text-emerald-300" : "text-rose-300")}>
                            {fmtR(r.netR, 1)}
                          </span>
                        </div>
                      ))}
                  </div>
                </Card>
              </div>
            </div>
          ) : null}

          {view === "history" ? (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Card className="px-4 py-3">
                  <MiniStat label="Signals in view" value={fmtInt(signals.length)} />
                  <div className="mt-2 flex items-center justify-between gap-2 text-[10.5px] text-faint">
                    <span>open now</span>
                    <span className="tabnum text-teal-200">{stats.open}</span>
                  </div>
                </Card>
                <Card className="px-4 py-3">
                  <MiniStat label="Win rate" value={fmtPct(stats.winRate)} tone={stats.winRate >= 50 ? "up" : "down"} />
                  <div className="mt-2">
                    <Meter pct={stats.winRate} tone={stats.winRate >= 50 ? "up" : "down"} />
                  </div>
                </Card>
                <Card className="px-4 py-3">
                  <MiniStat label="Expectancy" value={`${fmtR(stats.expectancy, 3)} / trade`} tone={stats.expectancy >= 0 ? "up" : "down"} />
                  <div className="mt-2 flex items-center justify-between gap-2 text-[10.5px] text-faint">
                    <span>avg hold</span>
                    <span className="tabnum text-dim">{stats.avgBars ? `${stats.avgBars.toFixed(1)} bars` : "—"}</span>
                  </div>
                </Card>
                <Card className="px-4 py-3">
                  <MiniStat label="Net R" value={fmtR(stats.netR, 1)} tone={stats.netR >= 0 ? "up" : "down"} />
                  <div className="mt-2 flex items-center justify-between gap-2 text-[10.5px] text-faint">
                    <span>last signal</span>
                    <span className="text-dim">{relTime(META.lastSignal)}</span>
                  </div>
                </Card>
              </div>
              <HistoryTable signals={signals} />
            </div>
          ) : null}

          <footer className="mt-8 flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-3 text-[10.5px] text-faint">
            <span>
              ASTA signal performance · data snapshot {relTime(META.generatedAt)} · R from realized_r
            </span>
            <span className="tabnum">
              {fmtInt(META.total)} signals · {fmtInt(META.closed)} closed · net {fmtR(META.netR, 1)}
            </span>
          </footer>
        </main>
      </div>
    </div>
  )
}
