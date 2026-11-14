import { useMemo, useState } from "react"
import {
  ArrowLeft,
  ArrowRight,
  Bell,
  CheckCircle2,
  Database,
  Globe,
  Rocket,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtInt } from "@/lib/format"
import type { AppData } from "@/lib/api"
import { previewActions, usePreview } from "@/lib/preview"
import { buildScannerRows, marketMeta } from "@/lib/scanners"
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Input,
  PreviewChip,
  StatusPill,
  Switch,
} from "@/components/ui"
import { useToast } from "@/components/feedback"
import { PageHeader, Notice } from "@/components/layout"

const STEPS = [
  { id: 1, label: "Discord channels", icon: Bell },
  { id: 2, label: "Data providers", icon: Globe },
  { id: 3, label: "Markets & scanners", icon: SlidersHorizontal },
  { id: 4, label: "Local system", icon: Database },
  { id: 5, label: "Validate & save", icon: ShieldCheck },
]

const MARKETS = ["stock", "crypto", "forex"] as const

export function SetupPage({ data, navigate }: { data: AppData; navigate: (path: string) => void }) {
  const preview = usePreview()
  const toast = useToast()
  const [step, setStep] = useState(1)
  const [webhooks, setWebhooks] = useState<Record<string, string>>({})
  const [port, setPort] = useState(String(data.setup?.system.port ?? 4310))
  const [dryRun, setDryRun] = useState(data.config?.dryRun ?? false)

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

  const configured = MARKETS.filter((market) => data.setup?.webhooks?.[market]?.configured).length

  const finish = () => {
    if (port && port !== String(data.setup?.system.port)) {
      toast.info("Port change noted", "The port is written by `asta setup`; the dashboard stays on its current port.")
    }
    previewActions.acknowledge("setup-review")
    toast.success("Setup reviewed", "The dashboard is ready. Engine writes happen through `asta setup`.")
    navigate("/overview")
  }

  const webhookValid = (value: string) => /^https:\/\/discord(app)?\.com\/api\/webhooks\/\S+$/.test(value.trim())

  return (
    <div className="animate-rise">
      <PageHeader
        title="Setup"
        description="The same five steps the launcher runs, now inside the dashboard. Secrets stay in .env and are only ever shown masked."
        badge={
          <Badge tone={data.setup?.complete ? "up" : "warn"}>
            {data.setup?.complete ? "Configured" : "Needs setup"}
          </Badge>
        }
        actions={
          <Button variant="ghost" onClick={() => navigate("/overview")}>
            Skip to dashboard
          </Button>
        }
      />

      {data.setup?.complete ? (
        <Notice tone="up" title="Setup already complete">
          Completed {data.setup.completedAt?.slice(0, 10)} · {configured} of 3 Discord channels configured. Re-running
          the wizard only overwrites the values you change.
        </Notice>
      ) : (
        <Notice tone="warn" title="Finish setup to start scanning">
          Without Discord channels and a market universe the engine will start but deliver nothing.
        </Notice>
      )}

      <Card className="mb-3 px-4 py-3">
        <div className="flex items-center gap-1 overflow-x-auto">
          {STEPS.map((item, index) => {
            const Icon = item.icon
            const active = step === item.id
            const done = step > item.id
            return (
              <div key={item.id} className="flex flex-1 items-center gap-1 last:flex-none">
                <button
                  onClick={() => setStep(item.id)}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 transition-colors",
                    active ? "bg-info-soft" : "hover:bg-surface-3",
                  )}
                >
                  <span
                    className={cn(
                      "grid h-5 w-5 place-items-center rounded-full",
                      done ? "bg-up-soft text-up" : active ? "bg-info text-white" : "bg-surface-3 text-faint",
                    )}
                  >
                    {done ? <CheckCircle2 className="h-3 w-3" /> : <Icon className="h-2.5 w-2.5" />}
                  </span>
                  <span
                    className={cn(
                      "whitespace-nowrap text-[11.5px] font-medium",
                      active ? "text-ink" : done ? "text-dim" : "text-faint",
                    )}
                  >
                    {item.label}
                  </span>
                </button>
                {index < STEPS.length - 1 ? (
                  <div className={cn("mx-1 h-[2px] flex-1 rounded-full", done ? "bg-up/40" : "bg-line")} />
                ) : null}
              </div>
            )
          })}
        </div>
      </Card>

      <div className="grid gap-3 xl:grid-cols-3">
        <div className="space-y-3 xl:col-span-2">
          {step === 1 ? (
            <Card>
              <CardHeader
                title="1 · Discord channels"
                subtitle="One webhook per market. Existing values are detected, never retyped."
                right={<Badge tone={configured === 3 ? "up" : "warn"}>{configured}/3 configured</Badge>}
              />
              <div className="space-y-2 px-4 pb-4">
                {MARKETS.map((market) => {
                  const hook = data.setup?.webhooks?.[market]
                  const draft = webhooks[market] ?? ""
                  return (
                    <div key={market} className="rounded-xl border border-line bg-surface-2 px-3 py-2.5">
                      <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Badge tone={marketMeta(market).tone}>{marketMeta(market).label}</Badge>
                          <span className="font-mono text-[10px] text-faint">{hook?.env}</span>
                        </div>
                        <StatusPill
                          status={hook?.configured ? "running" : "stopped"}
                          label={hook?.configured ? `saved ${hook.masked}` : "not configured"}
                        />
                      </div>
                      <Field label="New webhook URL" hint="Leave empty to keep the saved value. Written to .env on save.">
                        <Input
                          type="password"
                          autoComplete="off"
                          value={draft}
                          onChange={(event) => setWebhooks((current) => ({ ...current, [market]: event.target.value }))}
                          placeholder={hook?.configured ? "•••••••• (saved)" : "https://discord.com/api/webhooks/…"}
                        />
                      </Field>
                      {draft && !webhookValid(draft) ? (
                        <div className="mt-1 text-[10.5px] text-down">
                          Expected https://discord.com/api/webhooks/…
                        </div>
                      ) : null}
                    </div>
                  )
                })}
              </div>
            </Card>
          ) : null}

          {step === 2 ? (
            <Card>
              <CardHeader title="2 · Data providers" subtitle="Detected from config/app.yaml" right={<PreviewChip label="Checks are preview" />} />
              <div className="space-y-2 px-4 pb-4">
                {(["crypto", "stock", "forex"] as const).map((market) => {
                  const provider = data.setup?.providers?.[market] ?? data.config?.providers?.[market]
                  return (
                    <div key={market} className="rounded-xl border border-line bg-surface-2 px-3 py-2.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Badge tone={marketMeta(market).tone}>{marketMeta(market).label}</Badge>
                          <span className="font-mono text-[11px] text-dim">{provider?.type ?? "—"}</span>
                        </div>
                        <StatusPill status={provider?.configured ? "running" : "stopped"} label={provider?.configured ? "configured" : "missing"} />
                      </div>
                      {market === "forex" ? (
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          <Field label="MT5 terminal url" hint="Optional — set in .env.">
                            <Input
                              disabled
                              value={data.setup?.providers.forex?.terminalUrlConfigured ? "configured" : "not set"}
                            />
                          </Field>
                          <Field label="MT5 token">
                            <Input
                              disabled
                              value={data.setup?.providers.forex?.tokenConfigured ? "configured" : "not set"}
                            />
                          </Field>
                        </div>
                      ) : null}
                      <div className="mt-1.5 text-[10px] text-faint">
                        {(data.setup?.markets?.[market]?.symbols ?? []).join(" · ") || "universe not exposed"}
                      </div>
                    </div>
                  )
                })}
                <div className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2 text-[10.5px] leading-relaxed text-faint">
                  Credentials are written to .env with 0600 permissions. The dashboard never renders a full token.
                </div>
              </div>
            </Card>
          ) : null}

          {step === 3 ? (
            <Card>
              <CardHeader
                title="3 · Markets & scanners"
                subtitle="Checkboxes map to scanner_overrides in markets.yaml"
                right={<Badge tone="info">{scanners.filter((s) => s.enabled).length} enabled</Badge>}
              />
              <div className="space-y-2 px-4 pb-4">
                {MARKETS.map((market) => {
                  const meta = marketMeta(market)
                  const rows = scanners.filter((scanner) => scanner.market === market)
                  const marketEntry = data.setup?.markets?.[market]
                  return (
                    <div key={market} className="rounded-xl border border-line bg-surface-2 px-3 py-2.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge tone={meta.tone}>{meta.label}</Badge>
                          <span className="text-[10px] text-faint">
                            {marketEntry?.symbols?.length ?? 0} symbols · {rows.length} scanners
                          </span>
                        </div>
                        <Badge tone={marketEntry?.enabled ? "up" : "neutral"}>
                          {marketEntry?.enabled ? "market on" : "market off"}
                        </Badge>
                      </div>
                      <div className="mt-2 space-y-1">
                        {rows.length === 0 ? (
                          <div className="text-[10.5px] text-faint">No scanners discovered for this market.</div>
                        ) : (
                          rows.map((scanner) => (
                            <div
                              key={scanner.id}
                              className="flex items-center justify-between gap-2 rounded-lg border border-line-soft bg-surface px-2.5 py-1.5"
                            >
                              <div className="min-w-0">
                                <div className="truncate text-[11.5px] font-medium text-ink">{scanner.name}</div>
                                <div className="font-mono text-[9.5px] text-faint">
                                  {scanner.id} · {scanner.timeframe}
                                </div>
                              </div>
                              <Switch
                                checked={scanner.enabled}
                                onChange={(next) => previewActions.setScannerEnabled(scanner.id, next)}
                                label={`Toggle ${scanner.name}`}
                              />
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </Card>
          ) : null}

          {step === 4 ? (
            <Card>
              <CardHeader title="4 · Local system" subtitle="Where the engine and dashboard live" />
              <div className="grid gap-3 px-4 pb-4 sm:grid-cols-2">
                <Field label="SQLite path" hint="app.yaml → storage.sqlite_path">
                  <Input disabled value={data.setup?.system.dbPath ?? "—"} />
                </Field>
                <Field label="Dashboard port" hint="Loopback only. Default 4310.">
                  <Input value={port} onChange={(event) => setPort(event.target.value.replace(/[^0-9]/g, ""))} />
                </Field>
                <Field label="Listen host">
                  <Input disabled value={data.setup?.system.host ?? "127.0.0.1"} />
                </Field>
                <Field label="Project root">
                  <Input disabled value={data.setup?.system.root ?? "—"} />
                </Field>
                <div className="flex items-center justify-between rounded-xl border border-line bg-surface-2 px-3 py-2.5 sm:col-span-2">
                  <div>
                    <div className="text-[11.5px] font-medium text-ink">Dry run</div>
                    <div className="text-[10.5px] text-faint">Detect signals without delivering them to Discord.</div>
                  </div>
                  <Switch checked={dryRun} onChange={setDryRun} label="Dry run" />
                </div>
              </div>
            </Card>
          ) : null}

          {step === 5 ? (
            <Card>
              <CardHeader title="5 · Review & save" subtitle="Nothing is written until the installer runs" />
              <div className="px-4 pb-4">
                <div className="grid gap-2 sm:grid-cols-2">
                  {[
                    ["Discord channels", `${configured} of 3 configured`],
                    ["Providers", MARKETS.map((m) => `${m}: ${data.setup?.providers?.[m]?.type ?? "—"}`).join(" · ")],
                    ["Scanners enabled", `${scanners.filter((s) => s.enabled).length} of ${scanners.length}`],
                    ["Signals in database", fmtInt(data.dataset?.meta.total ?? 0)],
                    ["Database", data.setup?.system.dbPath ?? "—"],
                    ["Dashboard", `127.0.0.1:${port}`],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
                      <div className="text-[10px] uppercase tracking-wider text-faint">{label}</div>
                      <div className="mt-0.5 break-words text-[11.5px] text-ink">{value}</div>
                    </div>
                  ))}
                </div>
                <div className="mt-2 space-y-1.5">
                  {[
                    { ok: configured > 0, label: "At least one Discord channel configured" },
                    { ok: scanners.some((scanner) => scanner.enabled), label: "At least one scanner enabled" },
                    { ok: Boolean(data.setup?.system.dbExists), label: "SQLite database present" },
                    { ok: Boolean(data.health), label: "Engine responding on /api/health" },
                  ].map((check) => (
                    <div key={check.label} className="flex items-center gap-2 text-[11px]">
                      <span
                        className={cn(
                          "grid h-4 w-4 place-items-center rounded-full",
                          check.ok ? "bg-up-soft text-up" : "bg-warn-soft text-warn",
                        )}
                      >
                        <CheckCircle2 className="h-2.5 w-2.5" />
                      </span>
                      <span className={check.ok ? "text-dim" : "text-warn"}>{check.label}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 rounded-xl border border-info/20 bg-info-soft/50 px-3 py-2 text-[10.5px] leading-relaxed text-info">
                  Saving from the dashboard is a preview action. `asta setup` writes .env, app.yaml and
                  setup_state.json — the wizard keeps the same answers so nothing has to be retyped.
                </div>
              </div>
            </Card>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button variant="secondary" onClick={() => setStep((current) => Math.max(1, current - 1))} disabled={step === 1}>
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </Button>
            <div className="flex items-center gap-2">
              <span className="text-[10.5px] text-faint">
                Step {step} of {STEPS.length}
              </span>
              {step < STEPS.length ? (
                <Button variant="primary" size="md" onClick={() => setStep((current) => Math.min(STEPS.length, current + 1))}>
                  Continue <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              ) : (
                <Button variant="primary" size="md" onClick={finish}>
                  <Rocket className="h-3.5 w-3.5" /> Save & finish
                </Button>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <Card>
            <CardHeader title="What setup writes" subtitle="Files and their purpose" />
            <div className="space-y-2 px-4 pb-4 text-[11px] leading-relaxed text-dim">
              {[
                [".env", "Secrets: webhooks, provider tokens. Atomic write, chmod 0600."],
                ["config/app.yaml", "Runtime, storage, providers, dashboard port."],
                ["config/markets.yaml", "Markets, symbol universe, scanner overrides."],
                ["config/setup_state.json", "Which steps are done — never a secret."],
              ].map(([file, description]) => (
                <div key={file} className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
                  <div className="font-mono text-[10.5px] text-ink">{file}</div>
                  <div className="mt-0.5 text-[10px] text-faint">{description}</div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Good to know" subtitle="Design boundaries" right={<Sparkles className="h-3.5 w-3.5 text-faint" />} />
            <div className="space-y-1.5 px-4 pb-4 text-[10.5px] leading-relaxed text-faint">
              <p>· No trading execution, no auto-buy, no auto-sell — signals only.</p>
              <p>· The dashboard API is read-only and loopback-only.</p>
              <p>· Signal History keeps working while the engine is stopped.</p>
              <p>· Existing credentials are detected, so nothing is asked twice.</p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
