import { useMemo, useState } from "react"
import {
  Bell,
  Database,
  Globe,
  KeyRound,
  Lock,
  Play,
  Save,
  Server,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Terminal,
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
  Field,
  Input,
  MiniStat,
  PreviewChip,
  Select,
  StatusPill,
  Switch,
  Td,
  Th,
  Tr,
} from "@/components/ui"
import { useToast } from "@/components/feedback"
import { PageHeader, Notice } from "@/components/layout"

type SectionId =
  | "general"
  | "providers"
  | "discord"
  | "database"
  | "scanner"
  | "system"
  | "security"

const SECTIONS: { id: SectionId; label: string; icon: React.ElementType }[] = [
  { id: "general", label: "General settings", icon: Settings2 },
  { id: "providers", label: "Data provider", icon: Globe },
  { id: "discord", label: "Discord configuration", icon: Bell },
  { id: "database", label: "Database configuration", icon: Database },
  { id: "scanner", label: "Scanner defaults", icon: SlidersHorizontal },
  { id: "system", label: "System configuration", icon: Server },
  { id: "security", label: "Security", icon: Lock },
]

export function SettingsPage({ data, navigate }: { data: AppData; navigate: (path: string) => void }) {
  const [section, setSection] = useState<SectionId>("general")
  const preview = usePreview()
  const toast = useToast()

  const [dryRun, setDryRun] = useState(data.config?.dryRun ?? false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [confidence, setConfidence] = useState("0.35")
  const [defaultTimeframe, setDefaultTimeframe] = useState("1h")

  const scanners = useMemo(
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

  const savePreview = (what: string) =>
    toast.success(`${what} saved`, "Preview layer only — persist it with `asta setup` to change the engine.")

  return (
    <div className="animate-rise">
      <PageHeader
        title="Settings"
        description="Everything ASTA reads at startup. Values shown here come from the live config; edits stay local until the setup wizard writes them."
        badge={<PreviewChip label="Preview edits" />}
        actions={
          <Button variant="primary" size="md" onClick={() => navigate("/setup")}>
            <Play className="h-3.5 w-3.5" /> Re-run setup
          </Button>
        }
      />

      <div className="grid gap-3 lg:grid-cols-[196px_minmax(0,1fr)]">
        <Card className="h-fit p-1.5">
          <nav className="space-y-0.5">
            {SECTIONS.map((item) => {
              const Icon = item.icon
              const active = section === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => setSection(item.id)}
                  className={cn(
                    "flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[11.5px] font-medium transition-colors",
                    active ? "bg-info-soft text-ink" : "text-dim hover:bg-surface-3 hover:text-ink",
                  )}
                >
                  <Icon className={cn("h-3.5 w-3.5", active ? "text-info" : "text-faint")} />
                  {item.label}
                </button>
              )
            })}
          </nav>
        </Card>

        <div className="space-y-3">
          {section === "general" ? (
            <>
              <Card>
                <CardHeader
                  title="General settings"
                  subtitle="Runtime environment and dashboard behaviour"
                  right={<Badge tone="info">{data.setup?.system.environment ?? data.config?.environment ?? "—"}</Badge>}
                />
                <div className="grid gap-3 px-4 pb-4 sm:grid-cols-2">
                  <Field label="Environment" hint="Set in config/app.yaml — read-only here.">
                    <Input value={data.setup?.system.environment ?? data.config?.environment ?? "—"} disabled />
                  </Field>
                  <Field label="Dashboard port" hint="Loopback only; change it in app.yaml → web.port.">
                    <Input value={String(data.setup?.system.port ?? data.config?.web.port ?? 4310)} disabled />
                  </Field>
                  <div className="flex items-center justify-between rounded-xl border border-line bg-surface-2 px-3 py-2.5 sm:col-span-2">
                    <div>
                      <div className="text-[11.5px] font-medium text-ink">Dry run</div>
                      <div className="text-[10.5px] text-faint">
                        When on, signals are detected but never delivered to Discord.
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <PreviewChip />
                      <Switch checked={dryRun} onChange={setDryRun} label="Dry run" />
                    </div>
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-line bg-surface-2 px-3 py-2.5 sm:col-span-2">
                    <div>
                      <div className="text-[11.5px] font-medium text-ink">Auto refresh</div>
                      <div className="text-[10.5px] text-faint">Poll signals every 60s and runtime health every 20s.</div>
                    </div>
                    <Switch checked={autoRefresh} onChange={setAutoRefresh} label="Auto refresh" />
                  </div>
                  <Field label="Signal date range default">
                    <Select
                      value={defaultTimeframe}
                      onChange={setDefaultTimeframe}
                      options={[
                        { value: "all", label: "All time" },
                        { value: "90d", label: "Last 90 days" },
                        { value: "30d", label: "Last 30 days" },
                      ]}
                      className="w-full"
                    />
                  </Field>
                  <Field label="Timezone" hint="Timestamps are rendered in UTC throughout the dashboard.">
                    <Input value="UTC (engine standard)" disabled />
                  </Field>
                </div>
                <div className="flex justify-end border-t border-line px-4 py-2.5">
                  <Button variant="primary" onClick={() => savePreview("General settings")}>
                    <Save className="h-3.5 w-3.5" /> Save changes
                  </Button>
                </div>
              </Card>

              <Card>
                <CardHeader title="Setup status" subtitle="From config/setup_state.json" />
                <div className="px-4 pb-4">
                  <div className="flex items-center justify-between rounded-xl border border-line-soft bg-surface-2 px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <StatusPill status={data.setup?.complete ? "running" : "warning"} label={data.setup?.complete ? "Complete" : "Incomplete"} />
                      <span className="text-[11px] text-faint">
                        {data.setup?.completedAt ? `finished ${relTime(data.setup.completedAt)}` : "never finished"}
                      </span>
                    </div>
                    <Button variant="secondary" onClick={() => navigate("/setup")}>
                      Open wizard
                    </Button>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {["discord", "providers", "scanners", "system", "review"].map((step) => {
                      const done = data.setup?.completedSteps?.includes(step)
                      return (
                        <Badge key={step} tone={done ? "up" : "neutral"}>
                          {step}
                        </Badge>
                      )
                    })}
                  </div>
                </div>
              </Card>
            </>
          ) : null}

          {section === "providers" ? (
            <Card>
              <CardHeader
                title="Data providers"
                subtitle="One feed per market, detected from config/app.yaml"
                right={<PreviewChip label="Test = preview" />}
              />
              <div className="space-y-2 px-4 pb-4">
                {(["crypto", "stock", "forex"] as const).map((market) => {
                  const provider =
                    data.setup?.providers?.[market] ?? data.config?.providers?.[market] ?? null
                  return (
                    <div key={market} className="rounded-xl border border-line bg-surface-2 px-3 py-2.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Badge tone={marketMeta(market).tone}>{marketMeta(market).label}</Badge>
                          <span className="font-mono text-[11px] text-dim">{provider?.type ?? "—"}</span>
                          <StatusPill
                            status={provider?.configured ? "running" : "stopped"}
                            label={provider?.configured ? "configured" : "not configured"}
                          />
                        </div>
                        <Button
                          variant="secondary"
                          onClick={() =>
                            toast.info(
                              `${marketMeta(market).label} check queued`,
                              "Connectivity is validated by the engine, not the browser.",
                            )
                          }
                        >
                          Test connection
                        </Button>
                      </div>
                      {market === "forex" ? (
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          <MiniStat
                            label="MT5 terminal url"
                            value={data.setup?.providers.forex?.terminalUrlConfigured ? "configured" : "not set"}
                          />
                          <MiniStat
                            label="MT5 token"
                            value={data.setup?.providers.forex?.tokenConfigured ? "configured" : "not set"}
                          />
                        </div>
                      ) : null}
                      <div className="mt-1.5 text-[10px] text-faint">
                        {(data.setup?.markets?.[market]?.symbols ?? []).join(" · ") || "universe not exposed"}
                      </div>
                    </div>
                  )
                })}
                <Notice tone="info" title="Credentials live in .env">
                  Provider keys and tokens are never rendered. Edit them with `asta setup`, which writes .env with
                  0600 permissions.
                </Notice>
              </div>
            </Card>
          ) : null}

          {section === "discord" ? (
            <Card>
              <CardHeader
                title="Discord configuration"
                subtitle="Three channels, one webhook each"
                right={
                  <Button variant="secondary" onClick={() => navigate("/alerts")}>
                    Open alert management
                  </Button>
                }
              />
              <div className="space-y-2 px-4 pb-4">
                {(["stock", "crypto", "forex"] as const).map((market) => {
                  const hook = data.setup?.webhooks?.[market]
                  return (
                    <div
                      key={market}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2.5"
                    >
                      <div className="flex items-center gap-2">
                        <Badge tone={marketMeta(market).tone}>{marketMeta(market).label}</Badge>
                        <span className="font-mono text-[10.5px] text-faint">{hook?.env ?? "—"}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] text-dim">{hook?.masked || "not configured"}</span>
                        <StatusPill
                          status={hook?.configured ? "running" : "stopped"}
                          label={hook?.configured ? "connected" : "missing"}
                        />
                      </div>
                    </div>
                  )
                })}
                <div className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2 text-[10.5px] leading-relaxed text-faint">
                  Webhook URLs are masked everywhere. The full value never enters the browser; only the last four
                  characters are rendered.
                </div>
              </div>
            </Card>
          ) : null}

          {section === "database" ? (
            <Card>
              <CardHeader title="Database configuration" subtitle="SQLite, opened read-only by the dashboard" />
              <div className="grid gap-3 px-4 pb-4 sm:grid-cols-2">
                <Field label="Database path" hint="Set in app.yaml → storage.sqlite_path.">
                  <Input value={data.setup?.system.dbPath ?? data.system?.database.path ?? "—"} disabled />
                </Field>
                <Field label="Backend">
                  <Input value={data.system?.storage?.backend ?? data.config?.storage.backend ?? "sqlite"} disabled />
                </Field>
                <Field label="Size on disk">
                  <Input value={fmtBytes(data.system?.database.sizeBytes)} disabled />
                </Field>
                <Field label="Signal rows">
                  <Input value={fmtInt(data.system?.database.signals ?? data.dataset?.meta.total ?? 0)} disabled />
                </Field>
                <Field label="Journal mode" hint="WAL keeps readers from blocking the scanner writer.">
                  <Input value="WAL" disabled />
                </Field>
                <Field label="Dashboard access" hint="Every query opens mode=ro connections.">
                  <Input value="read-only" disabled />
                </Field>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2.5">
                <span className="text-[10.5px] text-faint">
                  {data.system?.database.available ? "Database reachable" : "Database not reachable"}
                </span>
                <Button
                  variant="secondary"
                  onClick={() =>
                    toast.info("Vacuum is an engine task", "Run `asta` maintenance from the terminal while the engine is stopped.")
                  }
                >
                  Maintenance
                </Button>
              </div>
            </Card>
          ) : null}

          {section === "scanner" ? (
            <>
              <Card>
                <CardHeader
                  title="Scanner defaults"
                  subtitle="Applied to scanners that do not override them"
                  right={<PreviewChip />}
                />
                <div className="grid gap-3 px-4 pb-4 sm:grid-cols-2">
                  <Field label="Default timeframe" hint="Used when a scanner bundle does not declare one.">
                    <Select
                      value={defaultTimeframe}
                      onChange={setDefaultTimeframe}
                      options={["15m", "30m", "1h", "4h", "1d"].map((tf) => ({ value: tf, label: tf }))}
                      className="w-full"
                    />
                  </Field>
                  <Field label="Minimum confidence" hint="Validator floor before a signal is stored.">
                    <Input value={confidence} onChange={(event) => setConfidence(event.target.value)} />
                  </Field>
                  <div className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2 sm:col-span-2">
                    <MiniStat label="Enabled scanners" value={`${scanners.filter((s) => s.enabled).length} / ${scanners.length}`} />
                    <MiniStat
                      label="Covered symbols"
                      value={String(new Set(scanners.flatMap((scanner) => scanner.covered)).size)}
                    />
                  </div>
                </div>
                <div className="flex justify-end border-t border-line px-4 py-2.5">
                  <Button variant="primary" onClick={() => savePreview("Scanner defaults")}>
                    <Save className="h-3.5 w-3.5" /> Save changes
                  </Button>
                </div>
              </Card>

              <Card className="overflow-hidden">
                <CardHeader title="Market universes" subtitle="Symbols each market scans (config/markets.yaml)" />
                <table className="w-full text-[12px]">
                  <thead>
                    <tr>
                      <Th>Market</Th>
                      <Th>Enabled</Th>
                      <Th>Symbols</Th>
                      <Th align="right">Count</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {(["crypto", "stock", "forex"] as const).map((market) => {
                      const entry = data.setup?.markets?.[market]
                      return (
                        <Tr key={market}>
                          <Td>
                            <Badge tone={marketMeta(market).tone}>{marketMeta(market).label}</Badge>
                          </Td>
                          <Td>{entry?.enabled ? "yes" : "no"}</Td>
                          <Td className="font-mono text-[10.5px]">
                            {entry?.symbols?.join(", ") || "not exposed"}
                          </Td>
                          <Td align="right" className="tabnum">
                            {entry?.symbols?.length ?? "—"}
                          </Td>
                        </Tr>
                      )
                    })}
                  </tbody>
                </table>
              </Card>
            </>
          ) : null}

          {section === "system" ? (
            <Card>
              <CardHeader title="System configuration" subtitle="Where ASTA runs and writes" />
              <div className="grid gap-3 px-4 pb-4 sm:grid-cols-2">
                <Field label="Project root">
                  <Input value={data.setup?.system.root ?? "—"} disabled />
                </Field>
                <Field label="Dashboard build">
                  <Input value={data.health?.web.webDir ?? data.system?.web?.webDir ?? "—"} disabled />
                </Field>
                <Field label="Listen address">
                  <Input value={`${data.health?.web.host ?? "127.0.0.1"}:${data.health?.web.port ?? 4310}`} disabled />
                </Field>
                <Field label="Log file">
                  <Input value={data.system?.logs.path ?? "data/logs/asta.log"} disabled />
                </Field>
                <Field label="Engine uptime">
                  <Input value={fmtDuration(data.system?.uptimeSeconds)} disabled />
                </Field>
                <Field label="Scheduler">
                  <Input value={`${data.system?.cycles ?? "—"} cycles · last ${relTime(data.system?.lastCycleAt)}`} disabled />
                </Field>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2.5">
                <span className="text-[10.5px] text-faint">
                  Restarting the engine re-reads .env, app.yaml and markets.yaml.
                </span>
                <Button
                  variant="secondary"
                  onClick={() =>
                    toast.info("Restart from the launcher", "Run `asta launcher` or restart ASTA.app to bounce the engine.")
                  }
                >
                  <Terminal className="h-3.5 w-3.5" /> Restart guidance
                </Button>
              </div>
            </Card>
          ) : null}

          {section === "security" ? (
            <Card>
              <CardHeader title="Security" subtitle="How this dashboard is allowed to touch the engine" right={<KeyRound className="h-3.5 w-3.5 text-faint" />} />
              <div className="space-y-2 px-4 pb-4">
                {[
                  {
                    icon: Lock,
                    title: "Loopback only",
                    body: "The API binds 127.0.0.1 and is never exposed to the network. Anything that can reach the port can read it.",
                  },
                  {
                    icon: KeyRound,
                    title: "Secrets stay in .env",
                    body: "Webhook URLs, provider tokens and API keys are read from .env (0600) and rendered masked. The full value never reaches the browser.",
                  },
                  {
                    icon: Database,
                    title: "Read-only database access",
                    body: "Every dashboard query opens SQLite with mode=ro, so a slow poll can never block the scanner's writer.",
                  },
                  {
                    icon: ShieldCheck,
                    title: "No trading execution",
                    body: "ASTA produces signals only. There is no order routing, no auto-buy and no auto-sell anywhere in the dashboard.",
                  },
                  {
                    icon: Sparkles,
                    title: "Preview writes",
                    body: "Actions that would change engine state (install, enable, uninstall, webhook edit) are recorded locally in the preview layer until the installer writes them.",
                  },
                ].map((item) => {
                  const Icon = item.icon
                  return (
                    <div key={item.title} className="flex items-start gap-2.5 rounded-xl border border-line-soft bg-surface-2 px-3 py-2.5">
                      <span className="mt-[1px] grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-info-soft text-info">
                        <Icon className="h-3.5 w-3.5" />
                      </span>
                      <div>
                        <div className="text-[11.5px] font-medium text-ink">{item.title}</div>
                        <p className="mt-0.5 text-[10.5px] leading-relaxed text-faint">{item.body}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  )
}
