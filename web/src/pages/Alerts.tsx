import { useMemo, useState } from "react"
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  CreditCard,
  Hash,
  Link2,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldCheck,
  Webhook,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtInt, fmtPct, fmtDateTime, relTime } from "@/lib/format"
import type { AppData } from "@/lib/api"
import { alertStats, previewActions, usePreview, type AlertLogEntry } from "@/lib/preview"
import { marketMeta } from "@/lib/scanners"
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Input,
  Meter,
  PreviewChip,
  StatusDot,
  StatusPill,
  Td,
  Th,
  Tr,
} from "@/components/ui"
import { ConfirmDialog, Modal, useToast } from "@/components/feedback"
import { PageHeader, Notice } from "@/components/layout"

const MARKET_ORDER = ["stock", "crypto", "forex"] as const

export function AlertsPage({ data }: { data: AppData }) {
  const preview = usePreview()
  const toast = useToast()
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [detail, setDetail] = useState<AlertLogEntry | null>(null)
  const [confirmRetry, setConfirmRetry] = useState<string | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>("all")

  const totals = alertStats(preview.alertLog)

  const byMarket = useMemo(() => {
    const map: Record<string, AlertLogEntry[]> = {}
    for (const market of MARKET_ORDER) {
      map[market] = preview.alertLog.filter((entry) => entry.market === market)
    }
    return map
  }, [preview.alertLog])

  const filteredLog = useMemo(
    () =>
      [...preview.alertLog]
        .filter((entry) => filter === "all" || entry.market === filter)
        .sort((a, b) => b.at.localeCompare(a.at)),
    [preview.alertLog, filter],
  )

  const webhookFor = (market: string) => data.setup?.webhooks?.[market] ?? null

  const saveWebhook = () => {
    if (!editing) return
    const trimmed = draft.trim()
    if (!trimmed) {
      toast.error("Webhook is empty", "Paste a Discord webhook URL or cancel.")
      return
    }
    if (!/^https:\/\/discord(app)?\.com\/api\/webhooks\//.test(trimmed)) {
      toast.error("Not a Discord webhook", "Expected https://discord.com/api/webhooks/…")
      return
    }
    previewActions.saveWebhookDraft(editing, trimmed)
    setEditing(null)
    setDraft("")
    toast.success("Webhook updated", "Stored as a masked preview value — the real secret stays in .env.")
  }

  const testWebhook = (market: string) => {
    const hook = webhookFor(market)
    setTesting(market)
    window.setTimeout(() => {
      setTesting(null)
      if (!hook?.configured) {
        toast.error(
          `${marketMeta(market).label} webhook not configured`,
          `Set ${hook?.env ?? "the webhook"} in .env, then retry.`,
        )
        return
      }
      toast.info(
        `${marketMeta(market).label} webhook format valid`,
        "Live delivery is sent by the engine — the dashboard API is read-only.",
      )
    }, 800)
  }

  return (
    <div className="animate-rise">
      <PageHeader
        title="Alert management"
        description="Three Discord destinations, one per market. Webhook secrets are read from .env and never shown in full."
        badge={<Badge tone="violet">discord</Badge>}
        actions={
          <Button
            variant="secondary"
            onClick={() => {
              data.refresh()
              toast.info("Delivery state refreshed")
            }}
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
        }
      />

      <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Alerts sent", value: fmtInt(totals.total), icon: Send, tone: "text-ink" },
          { label: "Delivered", value: fmtInt(totals.delivered), icon: CheckCircle2, tone: "text-up" },
          { label: "Failed", value: fmtInt(totals.failed), icon: AlertTriangle, tone: totals.failed ? "text-down" : "text-ink" },
          { label: "Success rate", value: fmtPct(totals.successRate, 1), icon: ShieldCheck, tone: totals.successRate >= 98 ? "text-up" : "text-warn" },
        ].map((stat) => {
          const Icon = stat.icon
          return (
            <Card key={stat.label} className="px-4 py-3">
              <div className="flex items-center justify-between">
                <span className="text-[10.5px] font-semibold uppercase tracking-[0.07em] text-faint">{stat.label}</span>
                <Icon className="h-3.5 w-3.5 text-faint" />
              </div>
              <div className={cn("tabnum mt-1 text-[20px] font-semibold leading-none", stat.tone)}>{stat.value}</div>
            </Card>
          )
        })}
      </div>

      <Notice tone="info" title="Delivery log is a sample until the engine records alerts">
        ASTA stores signal history, not webhook responses. Connection status and masked secrets are real (read from
        .env); counters and the log below come from the preview layer so the design can be evaluated.
      </Notice>

      <div className="grid gap-3 xl:grid-cols-3">
        {MARKET_ORDER.map((market) => {
          const hook = webhookFor(market)
          const meta = marketMeta(market)
          const entries = byMarket[market] ?? []
          const stats = alertStats(entries)
          const connected = Boolean(hook?.configured)
          return (
            <Card key={market} className="flex flex-col">
              <CardHeader
                title={
                  <span className="flex items-center gap-2">
                    <span className={cn("grid h-6 w-6 place-items-center rounded-lg", meta.soft, meta.text)}>
                      <Hash className="h-3 w-3" />
                    </span>
                    {meta.label} Discord webhook
                  </span>
                }
                subtitle={hook?.label || hook?.env || "—"}
                right={<StatusPill status={connected ? "running" : "stopped"} label={connected ? "Connected" : "Not set"} />}
              />
              <div className="flex-1 space-y-2 px-4 pb-3">
                <div className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
                  <div className="flex items-center justify-between text-[10px] text-faint">
                    <span className="flex items-center gap-1">
                      <Link2 className="h-2.5 w-2.5" /> webhook
                    </span>
                    <span className="font-mono text-[10.5px] text-dim">{hook?.masked || "not configured"}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[10px] text-faint">
                    <span className="flex items-center gap-1">
                      <CreditCard className="h-2.5 w-2.5" /> env key
                    </span>
                    <span className="font-mono text-[10px] text-dim">{hook?.env ?? "—"}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-xl border border-line-soft bg-surface-2 px-2.5 py-2">
                    <div className="text-[9.5px] uppercase tracking-wider text-faint">Sent</div>
                    <div className="tabnum text-[13px] font-medium text-ink">{fmtInt(stats.total)}</div>
                  </div>
                  <div className="rounded-xl border border-line-soft bg-surface-2 px-2.5 py-2">
                    <div className="text-[9.5px] uppercase tracking-wider text-faint">Failed</div>
                    <div className={cn("tabnum text-[13px] font-medium", stats.failed ? "text-down" : "text-ink")}>
                      {fmtInt(stats.failed)}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="mb-1 flex items-center justify-between text-[10px] text-faint">
                    <span>Delivery success</span>
                    <span className="tabnum text-dim">{fmtPct(stats.successRate, 1)}</span>
                  </div>
                  <Meter pct={stats.successRate} tone={stats.successRate >= 98 ? "up" : "warn"} />
                </div>

                <div className="flex items-center justify-between text-[10.5px] text-faint">
                  <span>Last successful delivery</span>
                  <span className="text-dim">{relTime(stats.lastDelivered)}</span>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-1.5 border-t border-line px-4 py-2.5">
                <Button variant="secondary" onClick={() => testWebhook(market)} loading={testing === market}>
                  <Webhook className="h-3.5 w-3.5" /> Test
                </Button>
                <Button
                  variant="ghost"
                  onClick={() =>
                    toast.info(
                      `${meta.label} test notification queued`,
                      "Sent as a preview event; the engine owns real delivery.",
                    )
                  }
                  disabled={!connected}
                >
                  <Bell className="h-3.5 w-3.5" /> Notify
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setEditing(market)
                    setDraft("")
                  }}
                >
                  Edit
                </Button>
                <Button
                  variant="ghost"
                  disabled={stats.failed === 0}
                  onClick={() => setConfirmRetry(market)}
                  className="ml-auto"
                >
                  <RotateCcw className="h-3.5 w-3.5" /> Retry failed
                </Button>
              </div>
            </Card>
          )
        })}
      </div>

      <Card className="mt-3 overflow-hidden">
        <CardHeader
          title="Recent notification logs"
          subtitle="Every delivery attempt across the three channels"
          right={<PreviewChip label="Sample" />}
        />
        <div className="flex flex-wrap items-center gap-1.5 px-4 pb-3">
          {[
            { value: "all", label: "All channels" },
            { value: "stock", label: "Stocks" },
            { value: "crypto", label: "Crypto" },
            { value: "forex", label: "Forex" },
          ].map((option) => (
            <button
              key={option.value}
              onClick={() => setFilter(option.value)}
              className={cn(
                "cursor-pointer rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-colors",
                filter === option.value
                  ? "border-info/30 bg-info-soft text-info"
                  : "border-line bg-surface text-faint hover:text-ink",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>

        {filteredLog.length === 0 ? (
          <div className="p-4">
            <EmptyState icon={<Bell className="h-4 w-4" />} title="No notifications for this channel" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr>
                  <Th>Time</Th>
                  <Th>Channel</Th>
                  <Th>Symbol</Th>
                  <Th>Scanner</Th>
                  <Th>Status</Th>
                  <Th>Detail</Th>
                  <Th align="right">Actions</Th>
                </tr>
              </thead>
              <tbody>
                {filteredLog.slice(0, 12).map((entry) => (
                  <Tr key={entry.id}>
                    <Td className="whitespace-nowrap">{relTime(entry.at)}</Td>
                    <Td>
                      <Badge tone={marketMeta(entry.market).tone}>{marketMeta(entry.market).label}</Badge>
                    </Td>
                    <Td className="font-medium text-ink">{entry.symbol}</Td>
                    <Td className="whitespace-nowrap">{entry.scanner}</Td>
                    <Td>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1.5 text-[11px] font-medium",
                          entry.status === "delivered" ? "text-up" : "text-down",
                        )}
                      >
                        <StatusDot status={entry.status === "delivered" ? "running" : "error"} />
                        {entry.status}
                      </span>
                    </Td>
                    <Td className="max-w-[260px] truncate text-[11px] text-faint">{entry.detail}</Td>
                    <Td align="right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" onClick={() => setDetail(entry)}>
                          Details
                        </Button>
                        {entry.status === "failed" ? (
                          <Button
                            variant="ghost"
                            onClick={() => {
                              previewActions.retryAlert(entry.id)
                              toast.success("Notification retried", "Marked delivered in the preview log.")
                            }}
                          >
                            Retry
                          </Button>
                        ) : null}
                      </div>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={`Edit ${editing ? marketMeta(editing).label : ""} webhook`}
        description="The URL is written to .env by the installer. The dashboard never displays it in full."
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={saveWebhook}>
              Save webhook
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Field
            label="Discord webhook URL"
            hint="Stored masked. Only a new URL replaces the existing one."
            required
          >
            <Input
              type="password"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="https://discord.com/api/webhooks/…"
              autoComplete="off"
            />
          </Field>
          <div className="rounded-xl border border-line bg-surface-2 px-3 py-2 text-[11px] text-faint">
            Current value:{" "}
            <span className="font-mono text-dim">
              {editing ? webhookFor(editing)?.masked || "not configured" : "—"}
            </span>
          </div>
        </div>
      </Modal>

      <Modal
        open={detail !== null}
        onClose={() => setDetail(null)}
        title="Notification details"
        description={detail ? fmtDateTime(detail.at) : undefined}
      >
        {detail ? (
          <div className="space-y-2 text-[12px]">
            {[
              ["Channel", marketMeta(detail.market).label],
              ["Symbol", detail.symbol],
              ["Scanner", detail.scanner],
              ["Status", detail.status],
              ["Detail", detail.detail],
              ["Event id", detail.id],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-4 border-b border-line-soft py-1.5 last:border-0">
                <span className="text-[11px] text-faint">{label}</span>
                <span className="text-right text-[12px] text-dim">{value}</span>
              </div>
            ))}
            <p className="pt-1 text-[10.5px] leading-relaxed text-faint">
              Sample event from the preview layer. Discord responses are not stored by ASTA, so retries and delivery
              counts are not authoritative until the engine records them.
            </p>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={confirmRetry !== null}
        title={`Retry failed ${confirmRetry ? marketMeta(confirmRetry).label : ""} notifications?`}
        description="Every failed delivery for this channel is re-queued in the preview log."
        confirmLabel="Retry all"
        tone="primary"
        onConfirm={() => {
          if (confirmRetry) {
            previewActions.retryAllFailed(confirmRetry)
            toast.success("Failed notifications retried", "Marked delivered in the preview log.")
          }
          setConfirmRetry(null)
        }}
        onCancel={() => setConfirmRetry(null)}
      />
    </div>
  )
}
