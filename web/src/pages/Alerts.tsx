import { useEffect, useMemo, useState } from "react"
import { AlertTriangle, Bell, CheckCircle2, Hash, Link2, RefreshCw, Send, ShieldCheck, Webhook } from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtInt, fmtPct, fmtDateTime, relTime } from "@/lib/format"
import type { AppData } from "@/lib/api"
import { libraryActions, type AlertEntry } from "@/lib/library"
import { marketMeta } from "@/lib/scanners"
import { Badge, Button, Card, CardHeader, Meter, StatusDot, StatusPill, Td, Th, Tr } from "@/components/ui"
import { useToast } from "@/components/feedback"
import { PageHeader, Notice } from "@/components/layout"

const MARKET_ORDER = ["stock", "crypto", "forex"] as const

function statsOf(entries: AlertEntry[]) {
  const delivered = entries.filter((e) => e.ok === true).length
  const failed = entries.filter((e) => e.ok === false).length
  const total = delivered + failed
  return {
    total,
    delivered,
    failed,
    successRate: total ? (delivered / total) * 100 : 0,
    lastDelivered: entries.find((e) => e.ok === true)?.at ?? null,
  }
}

export function AlertsPage({ data }: { data: AppData }) {
  const toast = useToast()
  const [log, setLog] = useState<AlertEntry[]>([])
  const [testing, setTesting] = useState<string | null>(null)
  const [notifying, setNotifying] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>("all")

  const loadLog = () => {
    libraryActions
      .alertLog()
      .then((payload) => setLog(payload.entries))
      .catch(() => undefined)
  }

  useEffect(() => {
    loadLog()
    const timer = setInterval(loadLog, 20_000)
    return () => clearInterval(timer)
  }, [])

  const totals = statsOf(log)

  const byMarket = useMemo(() => {
    const map: Record<string, AlertEntry[]> = {}
    for (const market of MARKET_ORDER) map[market] = log.filter((e) => e.market === market)
    return map
  }, [log])

  const filteredLog = useMemo(
    () => [...log].filter((entry) => filter === "all" || entry.market === filter).sort((a, b) => b.at.localeCompare(a.at)),
    [log, filter],
  )

  const webhookFor = (market: string) => data.setup?.webhooks?.[market] ?? null

  const testWebhook = async (market: string) => {
    setTesting(market)
    try {
      const { results } = await libraryActions.testAlert(market)
      const result = results[0]
      if (result?.ok) {
        toast.success(`${marketMeta(market).label} test delivered`, result.dry_run ? "Dry run — no real post was sent." : undefined)
      } else {
        toast.error(`${marketMeta(market).label} test failed`, result?.error ?? "Discord rejected the request.")
      }
      loadLog()
    } catch (error) {
      toast.error("Test failed", error instanceof Error ? error.message : String(error))
    } finally {
      setTesting(null)
    }
  }

  const notifySample = async (market: string) => {
    setNotifying(market)
    try {
      const { results } = await libraryActions.sampleAlert(market)
      const result = results[0]
      if (result?.ok) {
        toast.success(`${marketMeta(market).label} sample sent`, "A labelled sample signal card was posted.")
      } else {
        toast.error(`${marketMeta(market).label} sample failed`, result?.error ?? "Discord rejected the request.")
      }
      loadLog()
    } catch (error) {
      toast.error("Sample failed", error instanceof Error ? error.message : String(error))
    } finally {
      setNotifying(null)
    }
  }

  return (
    <div className="animate-rise">
      <PageHeader
        title="Alert management"
        description="Three Discord destinations, one per market. Webhook secrets are read from .env and never shown in full."
        badge={<Badge tone="violet">discord</Badge>}
        actions={
          <Button variant="secondary" onClick={loadLog}>
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

      <Notice tone="info" title="Delivery log">
        Test and sample notifications you send from here are recorded in{" "}
        <span className="font-mono">data/alerts/delivery_log.jsonl</span>. Webhook connection status below is read live
        from .env.
      </Notice>

      <div className="grid gap-3 xl:grid-cols-3">
        {MARKET_ORDER.map((market) => {
          const hook = webhookFor(market)
          const meta = marketMeta(market)
          const entries = byMarket[market] ?? []
          const stats = statsOf(entries)
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
                    <span className="flex items-center gap-1">env key</span>
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
                <Button variant="ghost" onClick={() => notifySample(market)} disabled={!connected} loading={notifying === market}>
                  <Bell className="h-3.5 w-3.5" /> Notify
                </Button>
              </div>
            </Card>
          )
        })}
      </div>

      <Card className="mt-3 overflow-hidden">
        <CardHeader
          title="Recent notification logs"
          subtitle="Test and sample deliveries across the three channels"
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
          <div className="px-4 pb-4">
            <div className="flex h-32 items-center justify-center rounded-xl border border-dashed border-line bg-surface-2 text-[12px] text-faint">
              No notifications yet — press Test or Notify above.
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr>
                  <Th>Time</Th>
                  <Th>Kind</Th>
                  <Th>Channel</Th>
                  <Th>Status</Th>
                  <Th>Detail</Th>
                </tr>
              </thead>
              <tbody>
                {filteredLog.slice(0, 24).map((entry, index) => (
                  <Tr key={`${entry.at}-${index}`}>
                    <Td className="whitespace-nowrap" title={fmtDateTime(entry.at)}>
                      {relTime(entry.at)}
                    </Td>
                    <Td>
                      <Badge tone="neutral">{entry.kind === "test" ? "test" : "sample"}</Badge>
                    </Td>
                    <Td>{entry.market ? <Badge tone={marketMeta(entry.market).tone}>{marketMeta(entry.market).label}</Badge> : "—"}</Td>
                    <Td>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1.5 text-[11px] font-medium",
                          entry.ok ? "text-up" : "text-down",
                        )}
                      >
                        <StatusDot status={entry.ok ? "running" : "error"} />
                        {entry.dry_run ? "dry run" : entry.ok ? "delivered" : "failed"}
                      </span>
                    </Td>
                    <Td className="max-w-[280px] truncate text-[11px] text-faint">
                      {entry.error ?? (entry.dry_run ? "dry run — nothing posted" : "delivered")}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
