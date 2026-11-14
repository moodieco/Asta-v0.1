import { useMemo, useState } from "react"
import {
  Activity,
  AlertTriangle,
  Bell,
  Boxes,
  CheckCircle2,
  Cpu,
  Database,
  Gauge,
  HardDrive,
  History,
  MemoryStick,
  RefreshCw,
  Server,
  ShieldCheck,
  Timer,
  Waves,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtInt, relTime } from "@/lib/format"
import { fmtBytes, fmtDuration, type AppData } from "@/lib/api"
import { usePreview } from "@/lib/preview"
import { buildScannerRows, marketMeta } from "@/lib/scanners"
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Meter,
  Skeleton,
  StatusDot,
  StatusPill,
  Td,
  Th,
  Tr,
} from "@/components/ui"
import { PageHeader, Notice } from "@/components/layout"

type Health = "running" | "warning" | "error" | "stopped"

export function SystemMonitorPage({ data, navigate }: { data: AppData; navigate: (path: string) => void }) {
  const preview = usePreview()
  const [tab, setTab] = useState<"all" | "error" | "warning">("all")

  const system = data.system
  const health = data.health

  const scanners = useMemo(
    () =>
      buildScannerRows({
        scanners: data.setup?.scanners ?? data.config?.scanners ?? [],
        setup: data.setup,
        system,
        signals: data.dataset?.signals ?? [],
        overrides: preview.enabledOverrides,
      }),
    [data.setup, data.config, system, data.dataset, preview.enabledOverrides],
  )

  const webhooks = data.setup?.webhooks ?? {}
  const webhookCount = Object.values(webhooks).filter((hook) => hook.configured).length
  const webhookTotal = Object.keys(webhooks).length || 3
  const errorScanners = scanners.filter((row) => row.health === "error").length

  const components: {
    key: string
    label: string
    detail: string
    status: Health
    statusLabel: string
    icon: React.ElementType
    tone: string
  }[] = [
    {
      key: "engine",
      label: "Scanner engine",
      detail: health ? `pid ${health.pid} · ${health.environment}` : "no /api/health response",
      status: health ? (errorScanners ? "warning" : "running") : "stopped",
      statusLabel: health ? (errorScanners ? "Degraded" : "Running") : "Stopped",
      icon: Activity,
      tone: "bg-mint-soft text-mint",
    },
    {
      key: "web",
      label: "Web server",
      detail: system?.web ? `${system.web.host}:${system.web.port}` : "serving this page",
      status: "running",
      statusLabel: "Serving",
      icon: Server,
      tone: "bg-info-soft text-info",
    },
    {
      key: "db",
      label: "SQLite database",
      detail: system?.database.available
        ? `${fmtBytes(system.database.sizeBytes)} · ${fmtInt(system.database.signals ?? 0)} rows`
        : "unavailable",
      status: system?.database.available ? "running" : "error",
      statusLabel: system?.database.available ? "Connected" : "Unavailable",
      icon: Database,
      tone: "bg-violet-soft text-violet",
    },
    {
      key: "discord",
      label: "Discord webhooks",
      detail: `${webhookCount} of ${webhookTotal} channels configured`,
      status: webhookCount === webhookTotal ? "running" : webhookCount > 0 ? "warning" : "stopped",
      statusLabel: `${webhookCount}/${webhookTotal}`,
      icon: Bell,
      tone: "bg-pink-soft text-pink",
    },
  ]

  const providers = (["stock", "crypto", "forex"] as const).map((market) => {
    const provider = data.setup?.providers?.[market] ?? data.config?.providers?.[market]
    const lastSignal = (data.dataset?.signals ?? []).find((s) => s.market === market)
    return {
      market,
      label: marketMeta(market).label,
      type: provider?.type ?? "—",
      configured: Boolean(provider?.configured),
      lastSignal: lastSignal?.createdAt ?? null,
    }
  })

  for (const provider of providers) {
    components.push({
      key: provider.market,
      label: `${provider.label} provider`,
      detail: `${provider.type} · last signal ${relTime(provider.lastSignal)}`,
      status: provider.configured ? (provider.lastSignal ? "running" : "warning") : "stopped",
      statusLabel: provider.configured ? (provider.lastSignal ? "Connected" : "Idle") : "Not set",
      icon: Waves,
      tone: "bg-up-soft text-up",
    })
  }

  components.push({
    key: "processes",
    label: "Scanner processes",
    detail: `${scanners.filter((s) => s.enabled).length} enabled · ${errorScanners} with errors`,
    status: scanners.length === 0 ? "warning" : errorScanners ? "error" : "running",
    statusLabel: `${scanners.length}`,
    icon: Boxes,
    tone: "bg-warn-soft text-warn",
  })

  const logLines = (system?.logs?.recent ?? []).filter((line) =>
    tab === "all" ? true : tab === "error" ? line.level === "error" : line.level === "warning",
  )

  const cpuPct = system?.cpuPct ?? 0
  const rss = system?.rssBytes ?? null
  const load = system?.loadAvg?.[0] ?? null

  return (
    <div className="animate-rise">
      <PageHeader
        title="System monitor"
        description="Every ASTA component in one place — engine, providers, database, webhooks and the individual scanner processes."
        badge={<StatusPill status={health ? "running" : "stopped"} label={health ? "monitoring" : "offline"} />}
        actions={
          <Button variant="secondary" onClick={data.refresh}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
        }
      />

      {!health ? (
        <Notice
          tone="warn"
          title="Engine unreachable — showing the last known state"
          action={
            <Button variant="secondary" onClick={data.refresh}>
              Retry
            </Button>
          }
        >
          Start it with <code className="font-mono">asta serve</code>. Signal History and Upload History still open
          from the cached snapshot.
        </Notice>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {components.map((component) => {
          const Icon = component.icon
          return (
            <Card key={component.key} className="px-4 py-3.5">
              <div className="flex items-start justify-between gap-2">
                <span className={cn("grid h-8 w-8 place-items-center rounded-xl", component.tone)}>
                  <Icon className="h-4 w-4" />
                </span>
                <StatusPill status={component.status} label={component.statusLabel} />
              </div>
              <div className="mt-2 text-[12px] font-semibold text-ink">{component.label}</div>
              <div className="mt-0.5 truncate text-[10.5px] text-faint" title={component.detail}>
                {component.detail}
              </div>
            </Card>
          )
        })}
      </div>

      <div className="mt-3 grid items-start gap-3 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Resources"
            subtitle="Sampled from the running engine process — no estimates"
            right={<Badge tone="info">{system?.threads ?? "—"} threads</Badge>}
          />
          <div className="grid gap-3 px-4 pb-4 sm:grid-cols-2 xl:grid-cols-3">
            <MetricCard
              icon={Cpu}
              label="CPU usage"
              value={system?.cpuPct === null || system?.cpuPct === undefined ? "—" : `${cpuPct.toFixed(1)}%`}
              footnote={load !== null ? `load avg ${load}` : "load avg unavailable"}
              meter={system?.cpuPct === null || system?.cpuPct === undefined ? null : Math.min(100, cpuPct)}
            />
            <MetricCard
              icon={MemoryStick}
              label="RAM usage"
              value={fmtBytes(rss)}
              footnote="resident set size of the engine"
              meter={rss ? Math.min(100, (rss / (512 * 1024 * 1024)) * 100) : null}
            />
            <MetricCard
              icon={HardDrive}
              label="Database size"
              value={fmtBytes(system?.database.sizeBytes)}
              footnote={system?.storage?.backend ? `${system.storage.backend} backend` : "sqlite"}
              meter={null}
            />
            <MetricCard
              icon={Timer}
              label="System uptime"
              value={fmtDuration(system?.uptimeSeconds)}
              footnote={system ? `since ${system.startedAt.slice(0, 16).replace("T", " ")}Z` : "—"}
              meter={null}
            />
            <MetricCard
              icon={Gauge}
              label="Scanner uptime"
              value={fmtDuration(system?.uptimeSeconds)}
              footnote={`${system?.cycles ?? "—"} scheduler cycles`}
              meter={null}
            />
            <MetricCard
              icon={AlertTriangle}
              label="Error / warning logs"
              value={`${fmtInt(system?.logs.errors ?? 0)} / ${fmtInt(system?.logs.warnings ?? 0)}`}
              footnote={`sampled ${fmtInt(system?.logs.sampledLines ?? 0)} log lines`}
              tone={system?.logs.errors ? "text-down" : "text-ink"}
              meter={null}
            />
          </div>
        </Card>

        <Card>
          <CardHeader title="Status legend" subtitle="Consistent across every screen" />
          <div className="space-y-2 px-4 pb-4">
            {[
              { status: "running" as Health, label: "Running / connected", hint: "Healthy and producing" },
              { status: "warning" as Health, label: "Warning", hint: "Up but degraded or stale" },
              { status: "error" as Health, label: "Error / disconnected", hint: "Needs attention" },
              { status: "stopped" as Health, label: "Stopped / inactive", hint: "Disabled or not configured" },
            ].map((row) => (
              <div key={row.status} className="flex items-start gap-2.5 rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
                <StatusDot status={row.status} className="mt-1" />
                <div>
                  <div className="text-[11.5px] font-medium text-ink">{row.label}</div>
                  <div className="text-[10px] text-faint">{row.hint}</div>
                </div>
              </div>
            ))}
            <div className="rounded-xl border border-info/20 bg-info-soft/50 px-3 py-2 text-[10.5px] leading-relaxed text-info">
              <History className="mr-1 inline h-3 w-3" />
              Signal History keeps working when the engine stops — the dashboard reads the last cached snapshot.
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Recent system activity"
            subtitle={system?.logs.available ? system.logs.path : "log file not found"}
            right={
              <div className="flex items-center gap-1">
                {(["all", "error", "warning"] as const).map((option) => (
                  <button
                    key={option}
                    onClick={() => setTab(option)}
                    className={cn(
                      "cursor-pointer rounded-md border px-2 py-0.5 text-[10.5px] font-medium capitalize transition-colors",
                      tab === option
                        ? "border-info/30 bg-info-soft text-info"
                        : "border-line bg-surface text-faint hover:text-ink",
                    )}
                  >
                    {option}
                  </button>
                ))}
              </div>
            }
          />
          <div className="px-4 pb-4">
            {!system ? (
              <div className="space-y-1.5">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
              </div>
            ) : logLines.length === 0 ? (
              <EmptyState
                icon={<ShieldCheck className="h-4 w-4" />}
                title="Nothing to report"
                description="No errors or warnings in the sampled log tail. That is the healthy state."
              />
            ) : (
              <div className="space-y-1.5">
                {logLines.map((line, index) => (
                  <div
                    key={`${line.at}-${index}`}
                    className={cn(
                      "rounded-xl border px-3 py-2",
                      line.level === "error"
                        ? "border-down/15 bg-down-soft/40"
                        : "border-warn/20 bg-warn-soft/40",
                    )}
                  >
                    <div
                      className={cn(
                        "flex items-center gap-1.5 text-[10px] font-medium",
                        line.level === "error" ? "text-down" : "text-warn",
                      )}
                    >
                      {line.level === "error" ? <AlertTriangle className="h-3 w-3" /> : <Bell className="h-3 w-3" />}
                      {line.at} · {line.module}
                    </div>
                    <p className="mt-0.5 break-words text-[10.5px] leading-relaxed text-dim">{line.message}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Scanner processes"
            subtitle="One row per discovered scanner"
            right={<Badge tone="neutral">{scanners.length}</Badge>}
          />
          {scanners.length === 0 ? (
            <div className="px-4 pb-4">
              <EmptyState icon={<Boxes className="h-4 w-4" />} title="No scanners discovered" />
            </div>
          ) : (
            <div className="max-h-[360px] overflow-auto">
              <table className="w-full text-[11.5px]">
                <thead>
                  <tr>
                    <Th>Scanner</Th>
                    <Th>Status</Th>
                    <Th align="right">Last scan</Th>
                  </tr>
                </thead>
                <tbody>
                  {scanners.map((scanner) => (
                    <Tr key={scanner.id} onClick={() => navigate(`/scanners/${scanner.id}`)}>
                      <Td>
                        <div className="truncate font-medium text-ink">{scanner.name}</div>
                        <div className="text-[9.5px] text-faint">{marketMeta(scanner.market).label}</div>
                      </Td>
                      <Td>
                        <StatusPill status={scanner.health} label={scanner.healthLabel} />
                      </Td>
                      <Td align="right" className="whitespace-nowrap">
                        {relTime(scanner.lastScan)}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Engine pid", value: system?.pid ? String(system.pid) : "—", icon: Activity },
          { label: "Version", value: system?.version ?? "—", icon: CheckCircle2 },
          { label: "Environment", value: system?.environment ?? "—", icon: Server },
          { label: "Dry run", value: system ? (system.dryRun ? "yes" : "no") : "—", icon: ShieldCheck },
        ].map((item) => {
          const Icon = item.icon
          return (
            <Card key={item.label} className="flex items-center gap-2.5 px-4 py-2.5">
              <Icon className="h-3.5 w-3.5 text-faint" />
              <div className="min-w-0 flex-1">
                <div className="text-[10px] uppercase tracking-wider text-faint">{item.label}</div>
                <div className="tabnum truncate text-[11.5px] text-ink">{item.value}</div>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

function MetricCard({
  icon: Icon,
  label,
  value,
  footnote,
  meter,
  tone,
}: {
  icon: React.ElementType
  label: string
  value: string
  footnote: string
  meter: number | null
  tone?: string
}) {
  return (
    <div className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider text-faint">{label}</span>
        <Icon className="h-3.5 w-3.5 text-faint" />
      </div>
      <div className={cn("tabnum mt-1 text-[16px] font-semibold leading-none", tone ?? "text-ink")}>{value}</div>
      {meter !== null ? (
        <div className="mt-1.5">
          <Meter pct={meter} tone={meter > 85 ? "down" : meter > 60 ? "warn" : "up"} />
        </div>
      ) : null}
      <div className="mt-1 truncate text-[10px] text-faint">{footnote}</div>
    </div>
  )
}
