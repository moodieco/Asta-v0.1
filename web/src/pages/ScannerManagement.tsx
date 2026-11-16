import { useMemo, useState } from "react"
import { Boxes, Eye, Recycle, SlidersHorizontal, Trash2, UploadCloud } from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtInt, fmtR, relTime } from "@/lib/format"
import type { AppData, ConfigScanner } from "@/lib/api"
import { libraryActions, useLibrary, type LibraryInfo } from "@/lib/library"
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

export function ScannerManagementPage({
  data,
  navigate,
}: {
  data: AppData
  navigate: (path: string) => void
}) {
  const toast = useToast()
  const { library, refresh: refreshLibrary } = useLibrary()
  const [query, setQuery] = useState("")
  const [market, setMarket] = useState("all")
  const [status, setStatus] = useState("all")
  const [overrides, setOverrides] = useState<Record<string, boolean>>({})
  const [pending, setPending] = useState<ScannerRow | null>(null)
  const [busy, setBusy] = useState(false)

  const rows = useMemo(() => buildScannerRows({ ...buildRowsInput(data, library, overrides) }), [data, library, overrides])

  const userIds = useMemo(() => new Set(library.installed.map((r) => r.scannerId)), [library.installed])

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

  const toggle = async (row: ScannerRow, next: boolean) => {
    setOverrides((current) => ({ ...current, [row.id]: next }))
    try {
      await libraryActions.setEnabled(row.id, next)
      refreshLibrary()
      toast.success(`${row.name} ${next ? "enabled" : "disabled"}`, "Persisted — restart the engine to apply.")
    } catch (error) {
      setOverrides((current) => ({ ...current, [row.id]: !next }))
      toast.error("Could not update scanner", error instanceof Error ? error.message : String(error))
    }
  }

  const runUninstall = async () => {
    if (!pending) return
    setBusy(true)
    const row = pending
    const isUser = userIds.has(row.id)
    try {
      if (isUser) {
        await libraryActions.uninstall(row.id)
        refreshLibrary()
        toast.success(`${row.name} moved to the recycle bin`, "Restore it any time from the Recycle bin.")
      } else {
        await libraryActions.setEnabled(row.id, false)
        setOverrides((current) => ({ ...current, [row.id]: false }))
        refreshLibrary()
        toast.info(`${row.name} disabled`, "Built-in scanners can't be deleted — this disables it. Restart to apply.")
      }
    } catch (error) {
      toast.error("Uninstall failed", error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
      setPending(null)
    }
  }

  return (
    <div className="animate-rise">
      <PageHeader
        title="Scanner management"
        description="Every discovered scanner, its market coverage and what it has produced. Enable, uninstall or restore without touching strategy code."
        actions={
          <>
            <Button variant="secondary" size="md" onClick={() => navigate("/scanners/trash")}>
              <Recycle className="h-3.5 w-3.5" /> Recycle bin
              {library.trash.length ? <Badge tone="warn">{library.trash.length}</Badge> : null}
            </Button>
            <Button variant="primary" size="md" onClick={() => navigate("/upload")}>
              <UploadCloud className="h-3.5 w-3.5" /> Upload scanner
            </Button>
          </>
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
                  <Th align="right">Active</Th>
                  <Th align="right">Symbols</Th>
                  <Th>Last scan</Th>
                  <Th align="right">Total signals</Th>
                  <Th align="right">Actions</Th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => {
                  const isUser = userIds.has(row.id)
                  return (
                    <Tr key={row.id}>
                      <Td>
                        <button
                          onClick={() => navigate(`/scanners/${row.id}`)}
                          className="cursor-pointer text-left"
                        >
                          <div className="flex items-center gap-1.5 font-medium text-ink hover:text-info">
                            {row.name}
                            {isUser ? <Badge tone="violet">user</Badge> : null}
                          </div>
                          <div className="font-mono text-[10px] text-faint">{row.id}</div>
                        </button>
                      </Td>
                      <Td>
                        <Badge tone={marketMeta(row.market).tone}>{marketMeta(row.market).label}</Badge>
                      </Td>
                      <Td className="tabnum">v{row.version}</Td>
                      <Td>
                        <StatusPill status={row.health} label={row.healthLabel} />
                      </Td>
                      <Td align="right">
                        <div className="flex justify-end">
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
                          <IconButton
                            label={isUser ? "Uninstall scanner" : "Disable scanner"}
                            onClick={() => setPending(row)}
                            className="hover:bg-down-soft hover:text-down"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </IconButton>
                        </div>
                      </Td>
                    </Tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ConfirmDialog
        open={pending !== null}
        busy={busy}
        title={pending && userIds.has(pending.id) ? `Uninstall ${pending.name}?` : `Disable ${pending?.name ?? "scanner"}?`}
        description={
          pending && userIds.has(pending.id)
            ? "The scanner is moved to the recycle bin and stops producing signals. Its historical signals stay in the database, and you can restore it any time."
            : "Built-in scanners ship with ASTA and cannot be removed. This disables it in markets.yaml (applied on restart); its history stays available."
        }
        confirmLabel={pending && userIds.has(pending.id) ? "Move to recycle bin" : "Disable"}
        tone="danger"
        onConfirm={runUninstall}
        onCancel={() => setPending(null)}
      />
    </div>
  )
}

function buildRowsInput(
  data: AppData,
  library: LibraryInfo,
  overrides: Record<string, boolean>,
): Parameters<typeof buildScannerRows>[0] {
  const engineScanners: ConfigScanner[] = data.setup?.scanners ?? data.config?.scanners ?? []
  const engineIds = new Set(engineScanners.map((s) => s.id))
  const userScanners: ConfigScanner[] = library.installed
    .filter((r) => !engineIds.has(r.scannerId))
    .map((r) => ({
      id: r.scannerId,
      name: r.name,
      market: r.market,
      timeframe: r.timeframes[0] ?? "1h",
      enabled: r.enabled ?? true,
    }))
  return {
    scanners: [...engineScanners, ...userScanners],
    setup: data.setup,
    system: data.system,
    signals: data.dataset?.signals ?? [],
    overrides,
  }
}
