import { useMemo } from "react"
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Bell,
  Boxes,
  CircleDollarSign,
  CloudUpload,
  Database,
  Gauge,
  Package,
  Server,
  ShieldCheck,
  Target,
  TrendingUp,
  Zap,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtInt, fmtPct, fmtR, relTime } from "@/lib/format"
import {
  equityCurve,
  groupStats,
  isClosed,
  statsOf,
  type Dataset,
} from "@/lib/metrics"
import { fmtBytes, fmtDuration, type AppData } from "@/lib/api"
import { usePreview, alertStats } from "@/lib/preview"
import { buildScannerRows, marketMeta } from "@/lib/scanners"
import type { Range } from "@/lib/range"
import { withinRange } from "@/lib/range"
import {
  Badge,
  Card,
  CardHeader,
  CountUp,
  Empty,
  Meter,
  PreviewChip,
  SectionLabel,
  StatusDot,
  StatusPill,
} from "@/components/ui"
import { CHART, Donut, EquityChart, MiniBars } from "@/components/charts"
import { PageHeader } from "@/components/layout"

const TINTS = {
  blue: { chip: "bg-info-soft text-info", card: "from-info-soft/70" },
  mint: { chip: "bg-mint-soft text-mint", card: "from-mint-soft/70" },
  yellow: { chip: "bg-warn-soft text-warn", card: "from-warn-soft/70" },
  pink: { chip: "bg-pink-soft text-pink", card: "from-pink-soft/70" },
} as const

function Kpi({
  label,
  value,
  suffix,
  decimals = 0,
  tint,
  icon: Icon,
  footnote,
  trend,
}: {
  label: string
  value: number
  suffix?: string
  decimals?: number
  tint: keyof typeof TINTS
  icon: React.ElementType
  footnote?: React.ReactNode
  trend?: "up" | "down" | null
}) {
  const tone = TINTS[tint]
  return (
    <Card className="relative overflow-hidden">
      <div className={cn("pointer-events-none absolute inset-x-0 top-0 h-16 bg-gradient-to-b to-transparent", tone.card)} />
      <div className="relative px-4 pb-3.5 pt-4">
        <div className="flex items-start justify-between gap-2">
          <span className="text-[10.5px] font-semibold uppercase tracking-[0.07em] text-faint">{label}</span>
          <span className={cn("grid h-7 w-7 place-items-center rounded-lg", tone.chip)}>
            <Icon className="h-3.5 w-3.5" strokeWidth={2} />
          </span>
        </div>
        <div className="mt-1.5 flex items-baseline gap-1">
          <CountUp
            value={value}
            decimals={decimals}
            className={cn(
              "tabnum text-[24px] font-semibold leading-none tracking-tight",
              trend === "up" && "text-up",
              trend === "down" && "text-down",
              !trend && "text-ink",
            )}
          />
          {suffix ? <span className="text-[12px] font-medium text-faint">{suffix}</span> : null}
        </div>
        {footnote ? <div className="mt-2 text-[10.5px] leading-relaxed text-faint">{footnote}</div> : null}
      </div>
    </Card>
  )
}

function ListRow({
  icon,
  title,
  meta,
  right,
  tone,
}: {
  icon?: React.ReactNode
  title: React.ReactNode
  meta?: React.ReactNode
  right?: React.ReactNode
  tone?: "up" | "down" | "neutral"
}) {
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-line-soft bg-surface-2 px-2.5 py-2">
      {icon ? <div className="shrink-0">{icon}</div> : null}
      <div className="min-w-0 flex-1">
        <div className="truncate text-[11.5px] font-medium text-ink">{title}</div>
        {meta ? <div className="truncate text-[10px] text-faint">{meta}</div> : null}
      </div>
      {right ? (
        <div
          className={cn(
            "tabnum shrink-0 text-[11.5px] font-medium",
            tone === "up" && "text-up",
            tone === "down" && "text-down",
            (!tone || tone === "neutral") && "text-dim",
          )}
        >
          {right}
        </div>
      ) : null}
    </div>
  )
}

export function OverviewPage({
  data,
  range,
  onRange,
  dataset,
}: {
  data: AppData
  range: Range
  onRange: (range: Range) => void
  dataset: Dataset | null
}) {
  const preview = usePreview()
  const signals = useMemo(
    () => (dataset?.signals ?? []).filter((s) => withinRange(s, range)),
    [dataset, range],
  )
  const stats = useMemo(() => statsOf(signals), [signals])
  const curve = useMemo(() => equityCurve(signals), [signals])
  const byScanner = useMemo(() => groupStats(signals, (s) => s.scanner), [signals])
  const bySymbol = useMemo(() => groupStats(signals, (s) => s.symbol), [signals])
  const byMarket = useMemo(() => groupStats(signals, (s) => s.market), [signals])
  const bySide = useMemo(() => groupStats(signals, (s) => s.side), [signals])

  const scanners = useMemo(
    () =>
      buildScannerRows({
        scanners: data.setup?.scanners ?? data.config?.scanners ?? [],
        setup: data.setup,
        system: data.system,
        signals: dataset?.signals ?? [],
        overrides: preview.enabledOverrides,
      }),
    [data.setup, data.config, data.system, dataset, preview.enabledOverrides],
  )

  const engineStatus = data.health ? (data.systemError ? "warning" : "running") : "stopped"
  const engineLabel = data.health ? "Engine online" : "Engine offline"
  const alerts = preview.alertLog
  const recentAlerts = alerts.slice(0, 5)
  const alertTotals = alertStats(alerts)

  const todayKey = new Date().toISOString().slice(0, 10)
  const todaySignals = (dataset?.signals ?? []).filter((s) => s.createdAt.slice(0, 10) === todayKey).length
  const weekValues = useMemo(() => {
    const out: number[] = []
    for (let i = 13; i >= 0; i--) {
      const key = new Date(Date.now() - i * 86_400_000).toISOString().slice(0, 10)
      out.push((dataset?.signals ?? []).filter((s) => s.createdAt.slice(0, 10) === key).length)
    }
    return out
  }, [dataset])

  const longShare = bySide.find((row) => row.key.toLowerCase() === "long")
  const shortShare = bySide.find((row) => row.key.toLowerCase() === "short")
  const longCount = longShare?.n ?? 0
  const shortCount = shortShare?.n ?? 0
  const totalSides = Math.max(1, longCount + shortCount)

  const marketSlices = ["crypto", "stock", "forex"]
    .map((market) => ({
      label: marketMeta(market).label,
      value: enabledByMarket(scanners, market),
      color:
        market === "crypto" ? CHART.up : market === "stock" ? CHART.blue : CHART.yellow,
    }))
    .filter((slice) => slice.value > 0)

  const topScanners = [...scanners].sort((a, b) => b.totalSignals - a.totalSignals).slice(0, 5)
  const topSymbols = [...bySymbol].sort((a, b) => b.n - a.n).slice(0, 6)
  const recentErrors = (data.system?.logs?.recent ?? []).filter((l) => l.level === "error").slice(0, 4)
  const latestUploads = [...preview.uploads]
    .sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt))
    .slice(0, 4)

  const providerRows = ["crypto", "stock", "forex"].map((market) => {
    const provider = data.setup?.providers?.[market] ?? data.config?.providers?.[market]
    const lastSignal = (dataset?.signals ?? []).find((s) => s.market === market)
    return {
      market,
      label: marketMeta(market).label,
      type: provider?.type ?? "—",
      ok: Boolean(provider?.configured),
      lastSignal: lastSignal?.createdAt ?? null,
    }
  })

  return (
    <div className="animate-rise">
      <PageHeader
        title="Overview"
        description="One screen for the engine, the scanners and the edge — every number comes from the local signal database."
        badge={<StatusPill status={engineStatus} label={engineLabel} />}
        actions={
          <div className="inline-flex items-center gap-0.5 rounded-lg border border-line bg-surface-3 p-0.5">
            {(["all", "90d", "30d"] as Range[]).map((option) => (
              <button
                key={option}
                onClick={() => onRange(option)}
                className={cn(
                  "cursor-pointer rounded-[6px] px-2.5 py-1 text-[11.5px] font-medium transition-all",
                  range === option ? "bg-surface text-ink shadow-[0_1px_2px_rgba(16,24,40,0.08)]" : "text-faint hover:text-dim",
                )}
              >
                {option === "all" ? "All time" : option}
              </button>
            ))}
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label="Signals stored"
          value={dataset?.meta.total ?? 0}
          tint="blue"
          icon={Target}
          footnote={
            <span className="flex items-center justify-between gap-2">
              <span>{fmtInt(todaySignals)} today · {fmtInt(stats.open)} open</span>
              <MiniBars values={weekValues} color={CHART.blue} height={16} className="w-16" />
            </span>
          }
        />
        <Kpi
          label="Win rate"
          value={stats.winRate}
          decimals={1}
          suffix="%"
          tint="mint"
          icon={Gauge}
          trend={stats.winRate >= 50 ? "up" : "down"}
          footnote={
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <span>{fmtInt(stats.wins)} wins · {fmtInt(stats.losses)} losses</span>
                <span className="tabnum">{fmtPct(stats.winRate)}</span>
              </div>
              <Meter pct={stats.winRate} tone={stats.winRate >= 50 ? "up" : "down"} />
            </div>
          }
        />
        <Kpi
          label="Net result"
          value={stats.netR}
          decimals={1}
          suffix="R"
          tint="yellow"
          icon={TrendingUp}
          trend={stats.netR >= 0 ? "up" : "down"}
          footnote={
            <span>
              expectancy {fmtR(stats.expectancy, 3)} · PF{" "}
              {stats.profitFactor === null ? "∞" : stats.profitFactor.toFixed(2)}
            </span>
          }
        />
        <Kpi
          label="Open positions"
          value={stats.open}
          tint="pink"
          icon={Zap}
          footnote={
            <span>
              {scanners.filter((s) => s.enabled).length} of {scanners.length} scanners enabled ·{" "}
              {fmtInt(dataset?.meta.closed ?? 0)} closed
            </span>
          }
        />
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Cumulative R"
            subtitle="Every closed signal in sequence — the shape of the edge, not the story around it"
            right={
              <div className="flex items-center gap-3 text-[10.5px] text-faint">
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-up" /> cumulative
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-down" /> drawdown
                </span>
              </div>
            }
          />
          <div className="px-2 pb-3">
            {curve.length ? <EquityChart data={curve} height={244} /> : <Empty>No closed trades yet.</Empty>}
          </div>
          <div className="grid grid-cols-2 gap-2 border-t border-line px-4 py-3 sm:grid-cols-4">
            {[
              { label: "Best trade", value: fmtR(stats.bestR, 1), tone: "text-up" },
              { label: "Worst trade", value: fmtR(stats.worstR, 1), tone: "text-down" },
              { label: "Max drawdown", value: `${stats.maxDrawdownR.toFixed(1)}R`, tone: "text-dim" },
              { label: "Win / loss streak", value: `${stats.maxWinStreak} / ${stats.maxLossStreak}`, tone: "text-dim" },
            ].map((item) => (
              <div key={item.label}>
                <div className="text-[9.5px] uppercase tracking-wider text-faint">{item.label}</div>
                <div className={cn("tabnum mt-0.5 text-[12.5px] font-medium", item.tone)}>{item.value}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Engine & providers" subtitle="Live runtime, read-only" right={<Server className="h-3.5 w-3.5 text-faint" />} />
          <div className="space-y-2 px-4 pb-4">
            <div className="rounded-xl border border-line bg-surface-2 px-3 py-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11.5px] font-medium text-ink">Scanner engine</span>
                <StatusPill status={engineStatus} label={engineLabel} />
              </div>
              <div className="mt-1.5 grid grid-cols-2 gap-1 text-[10.5px] text-faint">
                <span>uptime</span>
                <span className="tabnum text-right text-dim">{fmtDuration(data.system?.uptimeSeconds)}</span>
                <span>cycles</span>
                <span className="tabnum text-right text-dim">{data.system?.cycles ?? "—"}</span>
                <span>last cycle</span>
                <span className="text-right text-dim">{relTime(data.system?.lastCycleAt)}</span>
              </div>
            </div>

            {providerRows.map((row) => (
              <div key={row.market} className="flex items-center gap-2.5 rounded-xl border border-line-soft bg-surface-2 px-2.5 py-2">
                <StatusDot status={row.ok ? "running" : "stopped"} />
                <div className="min-w-0 flex-1">
                  <div className="text-[11.5px] font-medium text-ink">{row.label}</div>
                  <div className="text-[10px] text-faint">{row.type} · last signal {relTime(row.lastSignal)}</div>
                </div>
                <Badge tone={row.ok ? "up" : "neutral"}>{row.ok ? "connected" : "idle"}</Badge>
              </div>
            ))}

            <div className="flex items-center justify-between rounded-xl border border-line-soft bg-surface-2 px-2.5 py-2 text-[10.5px] text-faint">
              <span className="flex items-center gap-1.5">
                <Database className="h-3 w-3" /> sqlite
              </span>
              <span className="tabnum text-dim">
                {fmtBytes(data.system?.database.sizeBytes)} · {fmtInt(data.system?.database.signals ?? dataset?.meta.total ?? 0)} rows
              </span>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-3">
        <Card>
          <CardHeader
            title="Scanner distribution"
            subtitle="Enabled scanners by market"
            right={<Badge tone="info">{scanners.filter((s) => s.enabled).length} active</Badge>}
          />
          <div className="px-4 pb-4">
            {marketSlices.length ? (
              <Donut
                slices={marketSlices}
                centerValue={String(scanners.filter((s) => s.enabled).length)}
                centerLabel="enabled"
              />
            ) : (
              <Empty>No scanners discovered.</Empty>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Signal distribution"
            subtitle="BUY vs SELL in the selected range"
            right={<Badge tone="neutral">{fmtInt(totalSides)} signals</Badge>}
          />
          <div className="px-4 pb-4">
            <Donut
              slices={[
                { label: "BUY (long)", value: longCount, color: CHART.blue },
                { label: "SELL (short)", value: shortCount, color: CHART.pink },
              ]}
              centerValue={`${((longCount / totalSides) * 100).toFixed(0)}%`}
              centerLabel="long"
            />
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded-xl border border-line-soft bg-info-soft/40 px-2.5 py-2">
                <div className="flex items-center gap-1 text-[10px] text-faint">
                  <ArrowUpRight className="h-3 w-3 text-info" /> long edge
                </div>
                <div className="tabnum mt-0.5 text-[12.5px] font-medium text-ink">
                  {fmtR(longShare?.netR ?? 0, 1)}
                </div>
              </div>
              <div className="rounded-xl border border-line-soft bg-pink-soft/40 px-2.5 py-2">
                <div className="flex items-center gap-1 text-[10px] text-faint">
                  <ArrowDownRight className="h-3 w-3 text-pink" /> short edge
                </div>
                <div className="tabnum mt-0.5 text-[12.5px] font-medium text-ink">
                  {fmtR(shortShare?.netR ?? 0, 1)}
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Provider health" subtitle="Detected feed per market" right={<ShieldCheck className="h-3.5 w-3.5 text-faint" />} />
          <div className="space-y-2 px-4 pb-4">
            {["crypto", "stock", "forex"].map((market) => {
              const provider = data.setup?.providers?.[market] ?? data.config?.providers?.[market]
              const rows = signals.filter((s) => s.market === market)
              const stats = statsOf(rows)
              return (
                <div key={market} className="rounded-xl border border-line-soft bg-surface-2 px-2.5 py-2">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-[11.5px] font-medium text-ink">
                      <StatusDot status={provider?.configured ? "running" : "stopped"} />
                      {marketMeta(market).label}
                    </span>
                    <span className="text-[10px] text-faint">{provider?.type ?? "—"}</span>
                  </div>
                  <div className="mt-1 grid grid-cols-3 gap-1 text-[10px] text-faint">
                    <span>{fmtInt(rows.length)} signals</span>
                    <span className="text-center">{fmtPct(stats.winRate, 0)} win</span>
                    <span className={cn("text-right tabnum", stats.netR >= 0 ? "text-up" : "text-down")}>
                      {fmtR(stats.netR, 1)}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Top active scanners"
            subtitle="Signals produced in the selected range"
            right={<Badge tone="neutral">{fmtInt(signals.length)} signals</Badge>}
          />
          <div className="px-4 pb-4">
            {topScanners.length ? (
              <div className="space-y-1.5">
                {topScanners.map((scanner) => {
                  const max = Math.max(1, ...topScanners.map((r) => r.totalSignals))
                  return (
                    <div key={scanner.id} className="flex items-center gap-3 rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="truncate text-[11.5px] font-medium text-ink">{scanner.name}</span>
                          <Badge tone={marketMeta(scanner.market).tone}>{marketMeta(scanner.market).label}</Badge>
                        </div>
                        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[#eef1f6]">
                          <div
                            className="h-full rounded-full bg-info/70"
                            style={{ width: `${(scanner.totalSignals / max) * 100}%` }}
                          />
                        </div>
                      </div>
                      <div className="w-[92px] shrink-0 text-right">
                        <div className="tabnum text-[11.5px] font-medium text-ink">{fmtInt(scanner.totalSignals)}</div>
                        <div className={cn("tabnum text-[10px]", scanner.netR >= 0 ? "text-up" : "text-down")}>
                          {fmtR(scanner.netR, 1)}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <Empty>No scanners have produced signals yet.</Empty>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Recent Discord alerts"
            subtitle="Last deliveries across the three channels"
            right={<PreviewChip label="Sample" />}
          />
          <div className="space-y-1.5 px-4 pb-4">
            {recentAlerts.map((alert) => (
              <ListRow
                key={alert.id}
                icon={
                  <span
                    className={cn(
                      "grid h-7 w-7 place-items-center rounded-lg",
                      alert.status === "delivered" ? "bg-up-soft text-up" : "bg-down-soft text-down",
                    )}
                  >
                    <Bell className="h-3.5 w-3.5" />
                  </span>
                }
                title={`${alert.symbol} · ${alert.scanner}`}
                meta={`${marketMeta(alert.market).label} · ${relTime(alert.at)}`}
                right={alert.status === "delivered" ? "sent" : "failed"}
                tone={alert.status === "delivered" ? "up" : "down"}
              />
            ))}
            <div className="flex items-center justify-between px-1 pt-1 text-[10.5px] text-faint">
              <span>{fmtPct(alertTotals.successRate, 0)} delivery success</span>
              <span>{fmtInt(alertTotals.failed)} failed</span>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-3">
        <Card>
          <CardHeader title="Top signal symbols" subtitle="Where the signals cluster" right={<Target className="h-3.5 w-3.5 text-faint" />} />
          <div className="space-y-1 px-4 pb-4">
            {topSymbols.length ? (
              topSymbols.map((row) => (
                <div key={row.key} className="flex items-center justify-between gap-2 rounded-lg px-1.5 py-1.5 hover:bg-surface-2">
                  <div className="min-w-0">
                    <div className="truncate text-[11.5px] font-medium text-ink">{row.key}</div>
                    <div className="text-[10px] text-faint">
                      {fmtInt(row.n)} signals · {row.winRate.toFixed(0)}% win
                    </div>
                  </div>
                  <span className={cn("tabnum text-[11.5px]", row.netR >= 0 ? "text-up" : "text-down")}>
                    {fmtR(row.netR, 1)}
                  </span>
                </div>
              ))
            ) : (
              <Empty>No symbols yet.</Empty>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Scanner errors"
            subtitle="From the engine log (last sample)"
            right={
              <Badge tone={recentErrors.length ? "down" : "up"}>
                {recentErrors.length ? `${recentErrors.length} errors` : "clean"}
              </Badge>
            }
          />
          <div className="space-y-1.5 px-4 pb-4">
            {recentErrors.length ? (
              recentErrors.map((line, index) => (
                <div key={`${line.at}-${index}`} className="rounded-xl border border-down/15 bg-down-soft/40 px-2.5 py-2">
                  <div className="flex items-center gap-1.5 text-[10px] text-down">
                    <AlertTriangle className="h-3 w-3" />
                    {line.at} · {line.module}
                  </div>
                  <p className="mt-1 line-clamp-2 text-[10.5px] leading-relaxed text-dim">{line.message}</p>
                </div>
              ))
            ) : (
              <div className="flex h-[120px] flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-line bg-surface-2 text-[11px] text-faint">
                <ShieldCheck className="h-4 w-4 text-up" />
                No errors in the recent log
              </div>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Latest uploaded scanners"
            subtitle="Installer history"
            right={<PreviewChip label="Sample" />}
          />
          <div className="space-y-1.5 px-4 pb-4">
            {latestUploads.map((upload) => (
              <ListRow
                key={upload.id}
                icon={
                  <span className="grid h-7 w-7 place-items-center rounded-lg bg-violet-soft text-violet">
                    {upload.status === "installed" ? <Package className="h-3.5 w-3.5" /> : <CloudUpload className="h-3.5 w-3.5" />}
                  </span>
                }
                title={upload.name}
                meta={`v${upload.version} · ${marketMeta(upload.market).label} · ${relTime(upload.uploadedAt)}`}
                right={<Badge tone={upload.status === "installed" ? "up" : upload.status === "failed" ? "down" : "neutral"}>{upload.status}</Badge>}
              />
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

function enabledByMarket(scanners: ReturnType<typeof buildScannerRows>, market: string): number {
  return scanners.filter((scanner) => scanner.market === market && scanner.enabled).length
}
