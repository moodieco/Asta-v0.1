import { useMemo, useState } from "react"
import {
  Activity,
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  FileCode2,
  History,
  Layers,
  RotateCw,
  Settings2,
  Trash2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtDateTime, fmtInt, fmtPct, fmtR, relTime } from "@/lib/format"
import type { AppData } from "@/lib/api"
import { usePreview, previewActions, versionChain } from "@/lib/preview"
import { activitySeries, buildScannerRows, marketMeta, symbolCoverage } from "@/lib/scanners"
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Meter,
  PreviewChip,
  Progress,
  StatusPill,
  Switch,
  Td,
  Th,
  Tr,
} from "@/components/ui"
import { MiniBars, CHART } from "@/components/charts"
import { ConfirmDialog, useToast } from "@/components/feedback"
import { PageHeader } from "@/components/layout"

export function ScannerDetailPage({
  data,
  scannerId,
  navigate,
}: {
  data: AppData
  scannerId: string
  navigate: (path: string) => void
}) {
  const preview = usePreview()
  const toast = useToast()
  const [confirm, setConfirm] = useState<"restart" | "uninstall" | null>(null)
  const [busy, setBusy] = useState(false)

  const rows = useMemo(
    () =>
      buildScannerRows({
        scanners: data.setup?.scanners ?? data.config?.scanners ?? [],
        setup: data.setup,
        system: data.system,
        signals: data.dataset?.signals ?? [],
        overrides: preview.enabledOverrides,
      }),
    [data.setup, data.config, data.system, data.dataset, preview.enabledOverrides],
  )

  const scanner = rows.find((row) => row.id.toLowerCase() === scannerId.toLowerCase())

  const ownSignals = useMemo(
    () => (data.dataset?.signals ?? []).filter((s) => s.scannerId === scanner?.id || s.scanner === scanner?.name),
    [data.dataset, scanner],
  )

  const activity = useMemo(() => activitySeries(ownSignals, 21), [ownSignals])
  const coverage = useMemo(() => symbolCoverage(ownSignals), [ownSignals])
  const versions = useMemo(
    () => (scanner ? versionChain(preview.uploads, scanner.id) : []),
    [preview.uploads, scanner],
  )
  const errors = useMemo(
    () =>
      (data.system?.logs?.recent ?? []).filter(
        (line) =>
          line.level === "error" &&
          (line.message.toLowerCase().includes(scannerId.toLowerCase()) ||
            (scanner ? line.message.toLowerCase().includes(scanner.name.toLowerCase()) : false)),
      ),
    [data.system, scannerId, scanner],
  )

  if (!scanner) {
    return (
      <div className="animate-rise">
        <PageHeader title="Scanner not found" back="Scanner management" onBack={() => navigate("/scanners")} />
        <Card className="p-6">
          <EmptyState
            icon={<Layers className="h-4 w-4" />}
            title={`No scanner with id "${scannerId}"`}
            description="It may have been uninstalled, or the id in the URL is wrong. The scanner inventory comes from the engine config."
            action={
              <Button variant="primary" onClick={() => navigate("/scanners")}>
                Back to scanners
              </Button>
            }
          />
        </Card>
      </div>
    )
  }

  const meta = marketMeta(scanner.market)
  const runConfirm = () => {
    if (!confirm) return
    setBusy(true)
    window.setTimeout(() => {
      if (confirm === "uninstall") {
        previewActions.setScannerEnabled(scanner.id, false)
        toast.success(`${scanner.name} uninstalled`, "Preview only — the engine config is untouched.")
      } else {
        toast.success(`${scanner.name} restart requested`, "Picked up on the next engine cycle.")
      }
      setBusy(false)
      setConfirm(null)
    }, 700)
  }

  return (
    <div className="animate-rise">
      <PageHeader
        back="Scanner management"
        onBack={() => navigate("/scanners")}
        title={scanner.name}
        badge={
          <>
            <Badge tone={meta.tone}>{meta.label}</Badge>
            <Badge tone="neutral">v{scanner.version}</Badge>
            <StatusPill status={scanner.health} label={scanner.healthLabel} />
          </>
        }
        description={
          <span className="font-mono text-[11px] text-faint">{scanner.id}</span>
        }
        actions={
          <>
            <div className="flex items-center gap-2 rounded-lg border border-line bg-surface px-2.5 py-1.5">
              <span className="text-[11px] text-faint">{scanner.enabled ? "Enabled" : "Disabled"}</span>
              <Switch
                checked={scanner.enabled}
                onChange={(next) => {
                  previewActions.setScannerEnabled(scanner.id, next)
                  toast.push({
                    tone: next ? "success" : "info",
                    title: `${scanner.name} ${next ? "enabled" : "disabled"}`,
                    description: "Preview layer only.",
                  })
                }}
                label="Toggle scanner"
              />
            </div>
            <Button variant="secondary" onClick={() => setConfirm("restart")}>
              <RotateCw className="h-3.5 w-3.5" /> Restart
            </Button>
            <Button variant="danger" onClick={() => setConfirm("uninstall")}>
              <Trash2 className="h-3.5 w-3.5" /> Uninstall
            </Button>
          </>
        }
      />

      <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "Signals produced",
            value: fmtInt(scanner.totalSignals),
            meta: `${fmtInt(scanner.openSignals)} open · ${fmtInt(scanner.closedSignals)} closed`,
          },
          {
            label: "Win rate",
            value: fmtPct(scanner.winRate),
            meta: `${fmtInt(scanner.wins)}W / ${fmtInt(scanner.losses)}L`,
            tone: scanner.winRate >= 50 ? "text-up" : "text-down",
          },
          {
            label: "Net R",
            value: fmtR(scanner.netR, 1),
            meta: `expectancy ${fmtR(scanner.expectancy, 3)}`,
            tone: scanner.netR >= 0 ? "text-up" : "text-down",
          },
          {
            label: "Last scan",
            value: relTime(scanner.lastScan),
            meta: fmtDateTime(scanner.lastScan),
          },
        ].map((stat) => (
          <Card key={stat.label} className="px-4 py-3">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.07em] text-faint">{stat.label}</div>
            <div className={cn("tabnum mt-1 text-[19px] font-semibold leading-none", stat.tone ?? "text-ink")}>
              {stat.value}
            </div>
            <div className="mt-1 text-[10.5px] text-faint">{stat.meta}</div>
          </Card>
        ))}
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <div className="space-y-3 xl:col-span-2">
          <Card>
            <CardHeader
              title="Configuration"
              subtitle="Read from the engine config — the dashboard never edits strategy code"
              right={<Settings2 className="h-3.5 w-3.5 text-faint" />}
            />
            <div className="grid gap-2 px-4 pb-4 sm:grid-cols-2">
              {[
                { label: "Scanner id", value: scanner.id, mono: true },
                { label: "Market", value: meta.label },
                { label: "Timeframe", value: scanner.timeframe, mono: true },
                { label: "Version", value: `v${scanner.version}`, mono: true },
                { label: "Universe", value: `${scanner.universe.length} symbols` },
                { label: "Enabled", value: scanner.enabled ? "Yes" : "No" },
              ].map((field) => (
                <div key={field.label} className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-wider text-faint">{field.label}</div>
                  <div className={cn("mt-0.5 text-[11.5px] text-ink", field.mono && "font-mono text-[11px]")}>
                    {field.value}
                  </div>
                </div>
              ))}
            </div>
            {scanner.universe.length ? (
              <div className="border-t border-line px-4 py-3">
                <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">
                  <FileCode2 className="h-3 w-3" /> Symbol universe
                </div>
                <div className="flex flex-wrap gap-1">
                  {scanner.universe.map((symbol) => {
                    const active = scanner.covered.includes(symbol)
                    return (
                      <span
                        key={symbol}
                        className={cn(
                          "rounded-md border px-1.5 py-0.5 font-mono text-[10px]",
                          active
                            ? "border-info/20 bg-info-soft text-info"
                            : "border-line bg-surface-2 text-faint",
                        )}
                      >
                        {symbol}
                      </span>
                    )
                  })}
                </div>
              </div>
            ) : null}
          </Card>

          <Card>
            <CardHeader
              title="Activity"
              subtitle="Signals fired per day over the last 3 weeks"
              right={<Badge tone="neutral">{fmtInt(activity.reduce((acc, day) => acc + day.signals, 0))} signals</Badge>}
            />
            <div className="px-4 pb-4">
              <div className="mb-2 flex items-end justify-between gap-2">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-faint">Daily signals</div>
                  <div className="tabnum text-[18px] font-semibold text-ink">
                    {fmtInt(Math.round(activity.reduce((acc, day) => acc + day.signals, 0) / activity.length))}
                    <span className="ml-1 text-[11px] font-normal text-faint">avg / day</span>
                  </div>
                </div>
                <MiniBars
                  values={activity.map((day) => day.signals)}
                  labels={activity.map((day) => day.day)}
                  color={CHART.blue}
                  height={40}
                  className="w-[55%]"
                />
              </div>
              <div className="mt-3 grid grid-cols-7 gap-1 text-[9.5px] text-faint">
                {activity.map((day) => (
                  <div key={day.day} className="rounded-lg border border-line-soft bg-surface-2 px-1 py-1 text-center">
                    <div className="tabnum text-[11px] font-medium text-ink">{day.signals}</div>
                    <div>{day.day.slice(5)}</div>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Symbol coverage"
              subtitle="Every symbol this scanner has produced a signal for"
              right={<Badge tone="info">{coverage.length} symbols</Badge>}
            />
            {coverage.length === 0 ? (
              <div className="px-4 pb-4">
                <EmptyState
                  icon={<Activity className="h-4 w-4" />}
                  title="No signals yet"
                  description="Coverage fills in as soon as this scanner fires its first signal."
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr>
                      <Th>Symbol</Th>
                      <Th align="right">Signals</Th>
                      <Th align="right">Win rate</Th>
                      <Th align="right">Net R</Th>
                      <Th>Coverage</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {coverage.map((row) => (
                      <Tr key={row.symbol}>
                        <Td className="font-mono text-[11px] text-ink">{row.symbol}</Td>
                        <Td align="right" className="tabnum">
                          {fmtInt(row.total)}
                        </Td>
                        <Td align="right" className="tabnum">
                          {fmtPct(row.winRate, 0)}
                        </Td>
                        <Td align="right" className={cn("tabnum", row.netR >= 0 ? "text-up" : "text-down")}>
                          {fmtR(row.netR, 1)}
                        </Td>
                        <Td>
                          <div className="w-24">
                            <Meter pct={row.winRate} tone={row.netR >= 0 ? "up" : "down"} />
                          </div>
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-3">
          <Card>
            <CardHeader
              title="Error history"
              subtitle="Engine log lines attributed to this scanner"
              right={
                <Badge tone={errors.length ? "down" : "up"}>
                  {errors.length ? `${errors.length} errors` : "clean"}
                </Badge>
              }
            />
            <div className="space-y-1.5 px-4 pb-4">
              {errors.length === 0 ? (
                <div className="flex items-center gap-2 rounded-xl border border-up/20 bg-up-soft/50 px-3 py-2.5 text-[11px] text-up">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  No errors in the recent log sample
                </div>
              ) : (
                errors.map((line, index) => (
                  <div key={`${line.at}-${index}`} className="rounded-xl border border-down/15 bg-down-soft/40 px-2.5 py-2">
                    <div className="flex items-center gap-1.5 text-[10px] text-down">
                      <AlertTriangle className="h-3 w-3" />
                      {line.at}
                    </div>
                    <p className="mt-1 text-[10.5px] leading-relaxed text-dim">{line.message}</p>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Version history"
              subtitle="Uploads for this scanner"
              right={<PreviewChip label="Sample" />}
            />
            <div className="space-y-2 px-4 pb-4">
              {versions.length === 0 ? (
                <EmptyState
                  icon={<History className="h-4 w-4" />}
                  title="No upload records"
                  description="This scanner was discovered from the bundle on disk, not through the installer."
                />
              ) : (
                versions.map((version, index) => (
                  <div key={version.id} className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <span className="tabnum text-[11.5px] font-medium text-ink">v{version.version}</span>
                        {index === 0 ? <Badge tone="up">current</Badge> : null}
                      </div>
                      <Badge tone={version.status === "failed" ? "down" : version.status === "superseded" ? "neutral" : "info"}>
                        {version.status}
                      </Badge>
                    </div>
                    <div className="mt-0.5 flex items-center gap-1 text-[10px] text-faint">
                      <CalendarClock className="h-2.5 w-2.5" />
                      {relTime(version.uploadedAt)}
                    </div>
                    <ul className="mt-1.5 space-y-0.5">
                      {version.changes.slice(0, 3).map((change) => (
                        <li key={change} className="text-[10.5px] leading-relaxed text-dim">
                          · {change}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))
              )}
              {versions.length ? (
                <div className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2 text-[10.5px] text-faint">
                  Compatibility: <span className="text-dim">{versions[0].compatibility}</span>
                </div>
              ) : null}
            </div>
          </Card>

          <Card>
            <CardHeader title="Runtime" subtitle="Where this scanner sits in the engine" />
            <div className="space-y-2 px-4 pb-4">
              <div className="flex items-center justify-between rounded-xl border border-line-soft bg-surface-2 px-2.5 py-2">
                <span className="text-[11px] text-faint">Engine</span>
                <StatusPill status={data.health ? "running" : "stopped"} label={data.health ? "online" : "offline"} />
              </div>
              <div className="flex items-center justify-between rounded-xl border border-line-soft bg-surface-2 px-2.5 py-2">
                <span className="text-[11px] text-faint">Scheduler cycles</span>
                <span className="tabnum text-[11.5px] text-ink">{data.system?.cycles ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between rounded-xl border border-line-soft bg-surface-2 px-2.5 py-2">
                <span className="text-[11px] text-faint">Last cycle</span>
                <span className="text-[11.5px] text-ink">{relTime(data.system?.lastCycleAt)}</span>
              </div>
              <div className="rounded-xl border border-line-soft bg-surface-2 px-2.5 py-2">
                <div className="mb-1 flex items-center justify-between text-[10.5px] text-faint">
                  <span>Universe covered</span>
                  <span className="tabnum text-dim">
                    {scanner.covered.length}/{scanner.universe.length || "—"}
                  </span>
                </div>
                <Progress pct={scanner.universe.length ? (scanner.covered.length / scanner.universe.length) * 100 : 0} />
              </div>
            </div>
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={confirm !== null}
        busy={busy}
        title={confirm === "uninstall" ? `Uninstall ${scanner.name}?` : `Restart ${scanner.name}?`}
        description={
          confirm === "uninstall"
            ? "The scanner stops producing signals. Its history stays available in Signal History."
            : "The process is recycled on the next engine cycle; open positions are unaffected."
        }
        confirmLabel={confirm === "uninstall" ? "Uninstall" : "Restart"}
        tone={confirm === "uninstall" ? "danger" : "primary"}
        onConfirm={runConfirm}
        onCancel={() => setConfirm(null)}
      />
    </div>
  )
}
