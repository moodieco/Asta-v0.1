import { useMemo, useState } from "react"
import { CalendarClock, CheckCircle2, CloudUpload, FileClock, History, Package, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtDateTime, relTime } from "@/lib/format"
import { fmtBytes, type AppData } from "@/lib/api"
import { previewActions, usePreview, versionChain, type UploadRecord } from "@/lib/preview"
import { marketMeta } from "@/lib/scanners"
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  MiniStat,
  PreviewChip,
  SearchInput,
  Select,
  Td,
  Th,
  Tr,
} from "@/components/ui"
import { ConfirmDialog, Modal, useToast } from "@/components/feedback"
import { PageHeader, Notice } from "@/components/layout"

export function UploadHistoryPage({ navigate }: { data: AppData; navigate: (path: string) => void }) {
  const preview = usePreview()
  const toast = useToast()
  const [query, setQuery] = useState("")
  const [market, setMarket] = useState("all")
  const [status, setStatus] = useState("all")
  const [detail, setDetail] = useState<UploadRecord | null>(null)
  const [confirmRemove, setConfirmRemove] = useState<UploadRecord | null>(null)

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return [...preview.uploads]
      .filter((row) => {
        if (market !== "all" && row.market !== market) return false
        if (status !== "all" && row.status !== status) return false
        if (!q) return true
        return (
          row.name.toLowerCase().includes(q) ||
          row.scannerId.toLowerCase().includes(q) ||
          row.version.includes(q)
        )
      })
      .sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt))
  }, [preview.uploads, query, market, status])

  const installed = preview.uploads.filter((row) => row.status === "installed").length
  const failed = preview.uploads.filter((row) => row.status === "failed").length
  const latest = [...preview.uploads].sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt))[0]

  return (
    <div className="animate-rise">
      <PageHeader
        title="Upload history"
        description="Every bundle that reached the installer, with its version chain, change log and compatibility notes."
        badge={<PreviewChip label="Sample data" />}
        actions={
          <Button variant="primary" size="md" onClick={() => navigate("/upload")}>
            Upload scanner
          </Button>
        }
      />

      <Notice tone="info" title="Installer records are preview data">
        The engine does not persist installer events yet. This page shows the designed record shape with sample
        entries; signal and runtime data elsewhere in the app stays real.
      </Notice>

      <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Uploads recorded", value: String(preview.uploads.length) },
          { label: "Installed", value: String(installed) },
          { label: "Failed", value: String(failed) },
          { label: "Latest upload", value: latest ? relTime(latest.uploadedAt) : "—" },
        ].map((stat) => (
          <Card key={stat.label} className="px-4 py-3">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.07em] text-faint">{stat.label}</div>
            <div className="tabnum mt-1 text-[20px] font-semibold leading-none text-ink">{stat.value}</div>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
          <SearchInput value={query} onChange={setQuery} placeholder="Search scanner, id or version…" />
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
              { value: "installed", label: "Installed" },
              { value: "superseded", label: "Superseded" },
              { value: "failed", label: "Failed" },
            ]}
          />
          <span className="ml-auto text-[11px] text-faint">
            <span className="tabnum">{rows.length}</span> of {preview.uploads.length} records
          </span>
        </div>

        {rows.length === 0 ? (
          <div className="p-4">
            <EmptyState
              icon={<Package className="h-4 w-4" />}
              title="No uploads match"
              description="Clear the filters, or upload a new scanner bundle to start a history."
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
                  <Th>Upload date</Th>
                  <Th>Installation status</Th>
                  <Th>Update history</Th>
                  <Th align="right">Actions</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const chain = versionChain(preview.uploads, row.scannerId)
                  return (
                    <Tr key={row.id}>
                      <Td>
                        <div className="font-medium text-ink">{row.name}</div>
                        <div className="font-mono text-[10px] text-faint">{row.scannerId}</div>
                      </Td>
                      <Td>
                        <Badge tone={marketMeta(row.market).tone}>{marketMeta(row.market).label}</Badge>
                      </Td>
                      <Td className="tabnum">v{row.version}</Td>
                      <Td className="whitespace-nowrap" title={fmtDateTime(row.uploadedAt)}>
                        {relTime(row.uploadedAt)}
                      </Td>
                      <Td>
                        <Badge
                          tone={
                            row.status === "installed"
                              ? "up"
                              : row.status === "failed"
                                ? "down"
                                : row.status === "superseded"
                                  ? "neutral"
                                  : "info"
                          }
                        >
                          {row.status}
                        </Badge>
                      </Td>
                      <Td>
                        <span className="text-[11px] text-faint">
                          {chain.length > 1
                            ? `${chain.length} releases · newest v${chain[0].version}`
                            : "first release"}
                        </span>
                      </Td>
                      <Td align="right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" onClick={() => setDetail(row)}>
                            Details
                          </Button>
                          <Button
                            variant="ghost"
                            onClick={() => navigate("/scanners")}
                            className="text-faint"
                          >
                            Open
                          </Button>
                          {row.status === "failed" || row.status === "superseded" ? (
                            <Button
                              variant="ghost"
                              onClick={() => setConfirmRemove(row)}
                              className="text-faint hover:text-down"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          ) : null}
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

      <Modal
        open={detail !== null}
        onClose={() => setDetail(null)}
        title={detail ? `${detail.name} · v${detail.version}` : ""}
        description={detail ? `${marketMeta(detail.market).label} · ${fmtDateTime(detail.uploadedAt)}` : undefined}
        width="max-w-[560px]"
        footer={
          <Button variant="secondary" onClick={() => setDetail(null)}>
            Close
          </Button>
        }
      >
        {detail ? (
          <div className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-2">
              {[
                ["Bundle size", fmtBytes(detail.sizeBytes)],
                ["Timeframes", detail.timeframes.join(", ")],
                ["Status", detail.status],
                ["Origin", "uploaded through installer"],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-wider text-faint">{label}</div>
                  <div className="mt-0.5 text-[11.5px] text-ink">{value}</div>
                </div>
              ))}
            </div>

            <div className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-faint">Description</div>
              <p className="mt-0.5 text-[11.5px] leading-relaxed text-dim">{detail.description}</p>
            </div>

            <div>
              <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">
                <FileClock className="h-3 w-3" /> Changes in this version
              </div>
              <ul className="space-y-1">
                {detail.changes.map((change) => (
                  <li key={change} className="flex items-start gap-1.5 text-[11.5px] leading-relaxed text-dim">
                    <CheckCircle2 className="mt-[3px] h-3 w-3 shrink-0 text-up" />
                    {change}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl border border-line bg-surface-2 px-3 py-2">
              <MiniStat label="Compatibility" value={detail.compatibility} />
              <MiniStat label="Dependencies" value={detail.dependencies.join(", ") || "none"} />
            </div>

            <div>
              <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">
                <History className="h-3 w-3" /> Version chain
              </div>
              <div className="space-y-1.5">
                {versionChain(preview.uploads, detail.scannerId).map((version, index) => (
                  <div
                    key={version.id}
                    className={cn(
                      "flex items-center justify-between gap-2 rounded-xl border px-3 py-2",
                      version.id === detail.id ? "border-info/30 bg-info-soft/40" : "border-line-soft bg-surface-2",
                    )}
                  >
                    <div>
                      <div className="tabnum text-[11.5px] font-medium text-ink">v{version.version}</div>
                      <div className="text-[10px] text-faint">
                        <CalendarClock className="mr-1 inline h-2.5 w-2.5" />
                        {fmtDateTime(version.uploadedAt)}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {index === 0 ? <Badge tone="up">newest</Badge> : null}
                      <Badge tone={version.status === "failed" ? "down" : "neutral"}>{version.status}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={confirmRemove !== null}
        title={`Remove ${confirmRemove?.name ?? ""} v${confirmRemove?.version ?? ""} from history?`}
        description="The record disappears from the upload history. Installed scanners are unaffected."
        confirmLabel="Remove record"
        onConfirm={() => {
          if (confirmRemove) {
            previewActions.removeUpload(confirmRemove.id)
            toast.success("Upload record removed")
          }
          setConfirmRemove(null)
        }}
        onCancel={() => setConfirmRemove(null)}
      />
    </div>
  )
}
