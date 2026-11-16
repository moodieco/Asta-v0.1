import { useMemo, useState } from "react"
import { ArrowDownToLine, History, Package, RotateCcw, Trash2, UploadCloud } from "lucide-react"
import { fmtDateTime, relTime } from "@/lib/format"
import { useLibrary, type HistoryEvent } from "@/lib/library"
import { marketMeta } from "@/lib/scanners"
import { Badge, Button, Card, EmptyState, SearchInput, Select, Td, Th, Tr } from "@/components/ui"
import { PageHeader, Notice } from "@/components/layout"

const ACTION_META: Record<string, { label: string; tone: "up" | "down" | "warn" | "neutral" | "info"; icon: React.ElementType }> = {
  install: { label: "Installed", tone: "up", icon: UploadCloud },
  uninstall: { label: "Deleted", tone: "warn", icon: Trash2 },
  restore: { label: "Restored", tone: "info", icon: RotateCcw },
  purge: { label: "Purged", tone: "down", icon: Trash2 },
  "set-enabled": { label: "Toggled", tone: "neutral", icon: History },
}

export function UploadHistoryPage({ navigate }: { data: unknown; navigate: (path: string) => void }) {
  const { library } = useLibrary()
  const [query, setQuery] = useState("")
  const [action, setAction] = useState("all")

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return library.history.filter((event) => {
      if (action !== "all" && event.action !== action) return false
      if (!q) return true
      return (
        (event.name ?? "").toLowerCase().includes(q) ||
        (event.scannerId ?? "").toLowerCase().includes(q) ||
        (event.version ?? "").toLowerCase().includes(q)
      )
    })
  }, [library.history, query, action])

  const installs = library.history.filter((e) => e.action === "install").length
  const deleted = library.history.filter((e) => e.action === "uninstall").length
  const restored = library.history.filter((e) => e.action === "restore").length

  return (
    <div className="animate-rise">
      <PageHeader
        title="Upload history"
        description="Every install, uninstall, restore and purge recorded by the scanner library."
        actions={
          <Button variant="primary" size="md" onClick={() => navigate("/upload")}>
            <UploadCloud className="h-3.5 w-3.5" /> Upload scanner
          </Button>
        }
      />

      <Notice tone="info" title="Scanner library events">
        These events come from <span className="font-mono">data/scanners/history.jsonl</span>. Installed bundles live in{" "}
        <span className="font-mono">{library.root || "data/scanners/"}</span>; deleted ones wait in the recycle bin.
      </Notice>

      <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Events", value: library.history.length },
          { label: "Installed", value: installs },
          { label: "Deleted", value: deleted },
          { label: "Restored", value: restored },
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
            label="Action"
            value={action}
            onChange={setAction}
            options={[
              { value: "all", label: "All actions" },
              { value: "install", label: "Installed" },
              { value: "uninstall", label: "Deleted" },
              { value: "restore", label: "Restored" },
              { value: "purge", label: "Purged" },
            ]}
          />
          <span className="ml-auto text-[11px] text-faint">
            <span className="tabnum">{rows.length}</span> of {library.history.length} events
          </span>
        </div>

        {rows.length === 0 ? (
          <div className="p-4">
            <EmptyState
              icon={<Package className="h-4 w-4" />}
              title="No events yet"
              description="Upload a scanner bundle to start a history."
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
                  <Th>Time</Th>
                  <Th>Action</Th>
                  <Th>Scanner</Th>
                  <Th>Market</Th>
                  <Th>Version</Th>
                  <Th>Detail</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((event, index) => (
                  <HistoryRow key={`${event.at}-${event.action}-${index}`} event={event} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

function HistoryRow({ event }: { event: HistoryEvent }) {
  const meta = ACTION_META[event.action] ?? { label: event.action, tone: "neutral" as const, icon: ArrowDownToLine }
  const Icon = meta.icon
  return (
    <Tr>
      <Td className="whitespace-nowrap" title={fmtDateTime(event.at)}>
        {relTime(event.at)}
      </Td>
      <Td>
        <Badge tone={meta.tone}>
          <Icon className="h-3 w-3" /> {meta.label}
        </Badge>
      </Td>
      <Td>
        <div className="font-medium text-ink">{event.name ?? "—"}</div>
        <div className="font-mono text-[10px] text-faint">{event.scannerId}</div>
      </Td>
      <Td>{event.market ? <Badge tone={marketMeta(event.market).tone}>{marketMeta(event.market).label}</Badge> : "—"}</Td>
      <Td className="tabnum">{event.version ? `v${event.version}` : "—"}</Td>
      <Td className="max-w-[280px] truncate text-[11px] text-faint">{event.detail ?? "—"}</Td>
    </Tr>
  )
}
