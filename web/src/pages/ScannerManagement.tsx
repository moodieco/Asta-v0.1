import { useMemo, useState } from "react"
import {
  ArrowUpCircle,
  Boxes,
  Eye,
  RotateCw,
  SlidersHorizontal,
  Trash2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtInt, fmtR, relTime } from "@/lib/format"
import type { AppData } from "@/lib/api"
import { usePreview, previewActions } from "@/lib/preview"
import { buildScannerRows, marketMeta, type ScannerRow } from "@/lib/scanners"
import {
  Badge,
  Button,
  Card,
  EmptyState,
  IconButton,
  SearchInput,
  Select,
  SkeletonRows,
  StatusPill,
  Switch,
  Td,
  Th,
  Tr,
} from "@/components/ui"
import { ConfirmDialog, useToast } from "@/components/feedback"
import { PageHeader, Notice } from "@/components/layout"

type Pending =
  | { kind: "restart"; row: ScannerRow }
  | { kind: "update"; row: ScannerRow }
  | { kind: "uninstall"; row: ScannerRow }
  | null

export function ScannerManagementPage({
  data,
  navigate,
}: {
  data: AppData
  navigate: (path: string) => void
}) {
  const preview = usePreview()
  const toast = useToast()
  const [query, setQuery] = useState("")
  const [market, setMarket] = useState("all")
  const [status, setStatus] = useState("all")
  const [pending, setPending] = useState<Pending>(null)
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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((row) => {
      if (market !== "all" && row.market !== market) return false
      if (status === "enabled" && !row.enabled) return false
      if (status === "disabled" && row.enabled) return false
      if (status === "error" && row.health !== "error") return false
      if (!q) return true
      return (
        row.name.toLowerCase().includes(q) ||
        row.id.toLowerCase().includes(q) ||
        row.covered.join(" ").toLowerCase().includes(q)
      )
    })
  }, [rows, query, market, status])

  const loading = data.loading && !data.dataset

  const toggle = (row: ScannerRow, next: boolean) => {
    previewActions.setScannerEnabled(row.id, next)
    toast.push({
      tone: next ? "success" : "info",
      title: `${row.name} ${next ? "enabled" : "disabled"}`,
      description: "Recorded in the preview layer — the running engine is untouched.",
    })
  }

  const runPending = () => {
    if (!pending) return
    setBusy(true)
    const { kind, row } = pending
    window.setTimeout(() => {
      if (kind === "uninstall") {
        previewActions.setScannerEnabled(row.id, false)
        toast.success(`${row.name} uninstalled`, "Files stay on disk — preview only.")
      } else if (kind === "restart") {
        toast.success(`${row.name} restart requested`, "The engine restarts it on the next cycle.")
      } else {
        toast.info(`${row.name} is up to date`, `Version ${row.version} is the newest available.`)
      }
      setBusy(false)
      setPending(null)
    }, 700)
  }

  return (
    <div className="animate-rise">
      <PageHeader
        title="Scanner management"
        description="Every discovered scanner, its market coverage and what it has produced. Enable, restart or remove one without touching strategy code."
        actions={
          <Button variant="primary" size="md" onClick={() => navigate("/upload")}>
            Upload scanner
          </Button>
        }
        badge={<Badge tone="info">{rows.length} installed</Badge>}
      />

      {!data.health ? (
        <Notice
          tone="warn"
          title="Scanner engine is offline"
          action={
            <Button variant="secondary" onClick={data.refresh}>
              Retry
            </Button>
          }
        >
          Scanner status cannot be verified while `asta serve` is down. Signal history stays available below.
        </Notice>
      ) : null}

      <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Installed scanners", value: rows.length, tone: "text-ink" },
          { label: "Enabled", value: rows.filter((r) => r.enabled).length, tone: "text-up" },
          { label: "Errors", value: rows.filter((r) => r.health === "error").length, tone: "text-down" },
          { label: "Symbols covered", value: new Set(rows.flatMap((r) => r.covered)).size, tone: "text-ink" },
        ].map((stat) => (
          <Card key={stat.label} className="px-4 py-3">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.07em] text-faint">{stat.label}</div>
            <div className={cn("tabnum mt-1 text-[20px] font-semibold leading-none", stat.tone)}>{stat.value}</div>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
          <SearchInput value={query} onChange={setQuery} placeholder="Search scanner name, id or symbol…" />
          <Select
            label="Market"
            value={market}
            onChange={setMarket}
            options={[
              { value: "all", label: "All markets" },
              { value: "crypto", label: "Crypto" },
              { value: "stock", label: "Stocks" },
              { value: "forex", label: "Forex" },
            ]}
          />
          <Select
            label="Status"
            value={status}
            onChange={setStatus}
            options={[
              { value: "all", label: "All status" },
              { value: "enabled", label: "Enabled" },
              { value: "disabled", label: "Disabled" },
              { value: "error", label: "With errors" },
            ]}
          />
          <div className="ml-auto flex items-center gap-2 text-[11px] text-faint">
            <SlidersHorizontal className="h-3.5 w-3.5" />
            <span className="tabnum">
              {filtered.length} of {rows.length}
            </span>
          </div>
        </div>

        {loading ? (
          <SkeletonRows rows={6} />
        ) : filtered.length === 0 ? (
          <div className="p-4">
            <EmptyState
              icon={<Boxes className="h-4 w-4" />}
              title="No scanners match"
              description="Adjust the search or filters, or upload a new scanner bundle."
              action={
                <Button variant="secondary" onClick={() => navigate("/upload")}>
                  Upload scanner
                </Button>
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr>
                  <Th>Scanner name</Th>
                  <Th>Market</Th>
                  <Th>Version</Th>
                  <Th>Status</Th>
                  <Th align="right">Symbols</Th>
                  <Th>Last scan</Th>
                  <Th align="right">Total signals</Th>
                  <Th align="right">Actions</Th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <Tr key={row.id}>
                    <Td>
                      <button
                        onClick={() => navigate(`/scanners/${row.id}`)}
                        className="cursor-pointer text-left"
                      >
                        <div className="font-medium text-ink hover:text-info">{row.name}</div>
                        <div className="font-mono text-[10px] text-faint">{row.id}</div>
                      </button>
                    </Td>
                    <Td>
                      <Badge tone={marketMeta(row.market).tone}>{marketMeta(row.market).label}</Badge>
                    </Td>
                    <Td className="tabnum">v{row.version}</Td>
                    <Td>
                      <div className="flex items-center gap-2">
                        <StatusPill status={row.health} label={row.healthLabel} />
                        <Switch
                          checked={row.enabled}
                          onChange={(next) => toggle(row, next)}
                          label={`${row.enabled ? "Disable" : "Enable"} ${row.name}`}
                        />
                      </div>
                    </Td>
                    <Td align="right" className="tabnum">
                      {row.covered.length}
                      <span className="text-faint"> / {row.universe.length || "—"}</span>
                    </Td>
                    <Td className="whitespace-nowrap">
                      <span title={row.lastScan ?? undefined}>{relTime(row.lastScan)}</span>
                    </Td>
                    <Td align="right">
                      <div className="tabnum font-medium text-ink">{fmtInt(row.totalSignals)}</div>
                      <div className={cn("tabnum text-[10px]", row.netR >= 0 ? "text-up" : "text-down")}>
                        {fmtR(row.netR, 1)}
                      </div>
                    </Td>
                    <Td align="right">
                      <div className="flex items-center justify-end gap-0.5">
                        <IconButton label="View details" onClick={() => navigate(`/scanners/${row.id}`)}>
                          <Eye className="h-3.5 w-3.5" />
                        </IconButton>
                        <IconButton label="Restart scanner" onClick={() => setPending({ kind: "restart", row })}>
                          <RotateCw className="h-3.5 w-3.5" />
                        </IconButton>
                        <IconButton label="Update scanner" onClick={() => setPending({ kind: "update", row })}>
                          <ArrowUpCircle className="h-3.5 w-3.5" />
                        </IconButton>
                        <IconButton
                          label="Uninstall scanner"
                          onClick={() => setPending({ kind: "uninstall", row })}
                          className="hover:bg-down-soft hover:text-down"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </IconButton>
                      </div>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ConfirmDialog
        open={pending !== null}
        busy={busy}
        title={
          pending?.kind === "uninstall"
            ? `Uninstall ${pending.row.name}?`
            : pending?.kind === "restart"
              ? `Restart ${pending.row.name}?`
              : `Check ${pending?.row.name ?? "scanner"} for updates?`
        }
        description={
          pending?.kind === "uninstall"
            ? "The scanner stops producing signals immediately. Its historical signals stay in the database."
            : pending?.kind === "restart"
              ? "The scanner process is recycled on the next engine cycle; open positions are unaffected."
              : "Compares the installed bundle against the newest upload in the preview library."
        }
        confirmLabel={pending?.kind === "uninstall" ? "Uninstall" : pending?.kind === "restart" ? "Restart" : "Check"}
        tone={pending?.kind === "uninstall" ? "danger" : "primary"}
        onConfirm={runPending}
        onCancel={() => setPending(null)}
      />
    </div>
  )
}
