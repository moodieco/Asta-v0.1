import { useEffect, useMemo, useState } from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"
import { fmtDateTime, fmtDay, fmtInt, fmtPct, fmtPrice, fmtR, relTime } from "@/lib/format"
import { isClosed, type Signal } from "@/lib/metrics"
import {
  Badge,
  Button,
  Card,
  Empty,
  IconButton,
  Meter,
  SearchInput,
  Select,
  Td,
  Th,
  Tr,
} from "@/components/ui"
import { X } from "lucide-react"

type SortKey = "newest" | "oldest" | "best" | "worst" | "confidence"

const PAGE_SIZE = 20

export function statusBadge(s: Signal) {
  if (s.status === "hit_tp") return <Badge tone="up">hit TP</Badge>
  if (s.status === "hit_sl") return <Badge tone="down">hit SL</Badge>
  if (s.status === "open") return <Badge tone="open">open</Badge>
  return <Badge>{s.status}</Badge>
}

export function sideBadge(s: Signal) {
  return s.side === "long" ? <Badge tone="info">LONG</Badge> : <Badge tone="pink">SHORT</Badge>
}

export function HistoryTable({ signals }: { signals: Signal[] }) {
  const [query, setQuery] = useState("")
  const [status, setStatus] = useState("all")
  const [scanner, setScanner] = useState("all")
  const [market, setMarket] = useState("all")
  const [timeframe, setTimeframe] = useState("all")
  const [sort, setSort] = useState<SortKey>("newest")
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<Signal | null>(null)

  const scalars = useMemo(() => {
    const s = new Set<string>()
    const m = new Set<string>()
    const t = new Set<string>()
    for (const x of signals) {
      s.add(x.scanner)
      m.add(x.market)
      t.add(x.timeframe)
    }
    return {
      scanners: [...s].sort(),
      markets: [...m].sort(),
      timeframes: [...t].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })),
    }
  }, [signals])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const rows = signals.filter((s) => {
      if (status !== "all" && s.status !== status) return false
      if (scanner !== "all" && s.scanner !== scanner) return false
      if (market !== "all" && s.market !== market) return false
      if (timeframe !== "all" && s.timeframe !== timeframe) return false
      if (!q) return true
      return (
        s.symbol.toLowerCase().includes(q) ||
        s.scanner.toLowerCase().includes(q) ||
        s.reason.toLowerCase().includes(q) ||
        s.side.toLowerCase().includes(q)
      )
    })
    return [...rows].sort((a, b) => {
      switch (sort) {
        case "oldest":
          return a.createdAt.localeCompare(b.createdAt)
        case "best":
          return (b.realizedR ?? -Infinity) - (a.realizedR ?? -Infinity)
        case "worst":
          return (a.realizedR ?? Infinity) - (b.realizedR ?? Infinity)
        case "confidence":
          return (b.confidence ?? 0) - (a.confidence ?? 0)
        default:
          return b.createdAt.localeCompare(a.createdAt)
      }
    })
  }, [signals, query, status, scanner, market, timeframe, sort])

  useEffect(() => setPage(0), [query, status, scanner, market, timeframe, sort])

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const visible = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  return (
    <>
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
          <SearchInput value={query} onChange={setQuery} placeholder="Search symbol, scanner, reason…" />
          <Select
            label="Status"
            value={status}
            onChange={setStatus}
            options={[
              { value: "all", label: "All status" },
              { value: "hit_tp", label: "Hit TP" },
              { value: "hit_sl", label: "Hit SL" },
              { value: "open", label: "Open" },
            ]}
          />
          <Select
            label="Scanner"
            value={scanner}
            onChange={setScanner}
            options={[
              { value: "all", label: "All scanners" },
              ...scalars.scanners.map((s) => ({ value: s, label: s })),
            ]}
          />
          <Select
            label="Market"
            value={market}
            onChange={setMarket}
            options={[
              { value: "all", label: "All markets" },
              ...scalars.markets.map((s) => ({ value: s, label: s })),
            ]}
          />
          <Select
            label="Timeframe"
            value={timeframe}
            onChange={setTimeframe}
            options={[
              { value: "all", label: "All TFs" },
              ...scalars.timeframes.map((s) => ({ value: s, label: s })),
            ]}
          />
          <Select
            label="Sort"
            value={sort}
            onChange={(v) => setSort(v as SortKey)}
            options={[
              { value: "newest", label: "Newest first" },
              { value: "oldest", label: "Oldest first" },
              { value: "best", label: "Best R" },
              { value: "worst", label: "Worst R" },
              { value: "confidence", label: "Confidence" },
            ]}
          />
        </div>

        <div className="flex items-center justify-between px-4 py-2 text-[11px] text-faint">
          <span className="tabnum">
            {fmtInt(filtered.length)} of {fmtInt(signals.length)} signals
            {filtered.length !== signals.length ? " (filtered)" : ""}
          </span>
          <span className="tabnum">
            page {page + 1} / {pages}
          </span>
        </div>

        {visible.length === 0 ? (
          <div className="px-4 pb-4">
            <Empty>No signals match these filters.</Empty>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr>
                  <Th>Time</Th>
                  <Th>Symbol</Th>
                  <Th>Side</Th>
                  <Th>Scanner</Th>
                  <Th>TF</Th>
                  <Th align="right">Confidence</Th>
                  <Th align="right">Entry</Th>
                  <Th align="right">R:R</Th>
                  <Th>Status</Th>
                  <Th align="right">R</Th>
                  <Th align="right">Bars</Th>
                </tr>
              </thead>
              <tbody>
                {visible.map((s) => {
                  const closed = isClosed(s)
                  return (
                    <Tr key={s.id} onClick={() => setSelected(s)}>
                      <Td className="whitespace-nowrap">
                        <span title={fmtDateTime(s.createdAt)}>{relTime(s.createdAt)}</span>
                      </Td>
                      <Td className="whitespace-nowrap">
                        <span className="font-medium text-ink">{s.symbol}</span>
                        <span className="ml-1.5 text-[10px] text-faint">{s.market}</span>
                      </Td>
                      <Td>{sideBadge(s)}</Td>
                      <Td className="whitespace-nowrap">{s.scanner}</Td>
                      <Td>
                        <span className="rounded border border-line px-1 py-0.5 text-[10px] text-faint">
                          {s.timeframe}
                        </span>
                      </Td>
                      <Td align="right">
                        <div className="flex items-center justify-end gap-1.5">
                          <span className="tabnum">
                            {s.confidence !== null ? (s.confidence * 100).toFixed(0) : "—"}
                          </span>
                          <div className="w-8">
                            <Meter pct={(s.confidence ?? 0) * 100} tone="info" />
                          </div>
                        </div>
                      </Td>
                      <Td align="right" className="tabnum">
                        {fmtPrice(s.price)}
                      </Td>
                      <Td align="right" className="tabnum text-faint">
                        {s.riskReward ? s.riskReward.toFixed(1) : "—"}
                      </Td>
                      <Td>{statusBadge(s)}</Td>
                      <Td
                        align="right"
                        className={cn(
                          "tabnum font-medium",
                          closed ? ((s.realizedR as number) > 0 ? "text-up" : "text-down") : "text-faint",
                        )}
                      >
                        {closed ? fmtR(s.realizedR, 1) : "—"}
                      </Td>
                      <Td align="right" className="tabnum text-faint">
                        {s.barsHeld ?? "—"}
                      </Td>
                    </Tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-line px-4 py-2.5">
          <Button variant="secondary" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
            ← Prev
          </Button>
          <span className="tabnum text-[11px] text-faint">
            {page * PAGE_SIZE + 1}–{Math.min(filtered.length, (page + 1) * PAGE_SIZE)} /{" "}
            {fmtInt(filtered.length)}
          </span>
          <Button
            variant="secondary"
            onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
            disabled={page >= pages - 1}
          >
            Next →
          </Button>
        </div>
      </Card>

      <SignalDrawer signal={selected} onClose={() => setSelected(null)} />
    </>
  )
}

function Row({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line-soft py-1.5 last:border-0">
      <span className="text-[11px] text-faint">{label}</span>
      <span className={cn("text-right text-[12px] text-dim", mono && "tabnum")}>{value}</span>
    </div>
  )
}

export function SignalDrawer({ signal, onClose }: { signal: Signal | null; onClose: () => void }) {
  if (!signal) return null
  const s = signal
  const closed = isClosed(s)
  return createPortal(
    <div className="fixed inset-0 z-[95] flex justify-end">
      <div className="absolute inset-0 bg-ink/20 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <aside className="relative flex h-full w-full max-w-[470px] animate-rise flex-col border-l border-line bg-surface shadow-[var(--shadow-pop)]">
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[15px] font-semibold tracking-tight text-ink">{s.symbol}</span>
              {sideBadge(s)}
              {statusBadge(s)}
            </div>
            <p className="mt-1 text-[11px] text-faint">
              {s.scanner} · {s.timeframe} · {s.market} · {s.levelsSource || "levels n/a"}
            </p>
          </div>
          <IconButton label="Close" onClick={onClose}>
            <X className="h-3.5 w-3.5" />
          </IconButton>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-3">
          <div className="mb-3 grid grid-cols-3 gap-2">
            <div className="rounded-xl border border-line bg-surface-2 p-2.5">
              <div className="text-[10px] uppercase tracking-wider text-faint">Entry</div>
              <div className="tabnum mt-0.5 text-[13px] font-medium text-ink">{fmtPrice(s.price)}</div>
            </div>
            <div className="rounded-xl border border-down/15 bg-down-soft/50 p-2.5">
              <div className="text-[10px] uppercase tracking-wider text-faint">Stop</div>
              <div className="tabnum mt-0.5 text-[13px] font-medium text-down">{fmtPrice(s.stopLoss)}</div>
            </div>
            <div className="rounded-xl border border-up/15 bg-up-soft/50 p-2.5">
              <div className="text-[10px] uppercase tracking-wider text-faint">Target</div>
              <div className="tabnum mt-0.5 text-[13px] font-medium text-up">{fmtPrice(s.takeProfit)}</div>
            </div>
          </div>

          <section className="mb-4">
            <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.09em] text-faint">Outcome</h4>
            <div className="rounded-xl border border-line bg-surface-2 px-3 py-1.5">
              <Row
                label="Realized R"
                mono
                value={
                  closed ? (
                    <span className={(s.realizedR as number) > 0 ? "text-up" : "text-down"}>
                      {fmtR(s.realizedR)}
                    </span>
                  ) : (
                    "open"
                  )
                }
              />
              <Row label="Risk / reward" mono value={s.riskReward ? `${s.riskReward.toFixed(2)} : 1` : "—"} />
              <Row label="Risk pct" mono value={s.riskPct !== null ? fmtPct(s.riskPct, 2) : "—"} />
              <Row label="Bars held" mono value={s.barsHeld ?? "—"} />
              <Row
                label="Confidence"
                mono
                value={s.confidence !== null ? `${(s.confidence * 100).toFixed(1)}%` : "—"}
              />
              <Row label="ATR" mono value={s.atr !== null ? s.atr.toFixed(4) : "—"} />
            </div>
          </section>

          <section className="mb-4">
            <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.09em] text-faint">Timeline</h4>
            <div className="rounded-xl border border-line bg-surface-2 px-3 py-1.5">
              <Row label="Signal created" value={fmtDateTime(s.createdAt)} />
              <Row label="Closed" value={closed ? fmtDateTime(s.closedAt) : "—"} />
              <Row label="Expires" value={fmtDateTime(s.expiresAt)} />
              <Row label="Source" value={s.source} />
              <Row label="Signal id" mono value={<span className="text-[11px] text-faint">{s.signalId}</span>} />
            </div>
          </section>

          <section className="mb-4">
            <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.09em] text-faint">Reason</h4>
            <p className="rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-[12px] leading-relaxed text-dim">
              {s.reason || "No reason recorded."}
            </p>
          </section>

          {Object.keys(s.indicators).length > 0 ? (
            <section>
              <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.09em] text-faint">
                Indicators
              </h4>
              <div className="rounded-xl border border-line bg-surface-2 px-3 py-1.5">
                {Object.entries(s.indicators).map(([k, v]) => (
                  <Row key={k} label={k} mono value={typeof v === "object" ? JSON.stringify(v) : String(v)} />
                ))}
              </div>
            </section>
          ) : null}
        </div>

        <footer className="border-t border-line bg-surface-2 px-5 py-3 text-[10.5px] text-faint">
          {fmtDay(s.createdAt)} · {s.strategy || s.scanner} · read-only view
        </footer>
      </aside>
    </div>,
    document.body,
  )
}
