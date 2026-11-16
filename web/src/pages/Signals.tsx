import { useMemo } from "react"
import { History, RefreshCw, WifiOff } from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtInt, fmtPct, fmtR, relTime } from "@/lib/format"
import type { AppData } from "@/lib/api"
import { isClosed, statsOf } from "@/lib/metrics"
import { withinRange, type CustomRange, type Range } from "@/lib/range"
import { Badge, Button, Card, Meter, MiniStat, SkeletonRows } from "@/components/ui"
import { HistoryTable } from "@/components/history"
import { PageHeader, Notice } from "@/components/layout"
import { RangePicker } from "@/components/range-picker"

export function SignalsPage({
  data,
  range,
  onRange,
  custom,
  onCustom,
}: {
  data: AppData
  range: Range
  onRange: (range: Range) => void
  custom: CustomRange | null
  onCustom: (custom: CustomRange | null) => void
}) {
  const signals = useMemo(
    () => (data.dataset?.signals ?? []).filter((signal) => withinRange(signal, range, custom)),
    [data.dataset, range, custom],
  )
  const stats = useMemo(() => statsOf(signals), [signals])
  const openNow = signals.filter((signal) => signal.status === "open").length

  return (
    <div className="animate-rise">
      <PageHeader
        title="Signal history"
        description="Every accepted signal, straight from the local SQLite history. Filters and sorting run in the browser."
        badge={<Badge tone="info">{fmtInt(data.dataset?.meta.total ?? 0)} stored</Badge>}
        actions={
          <>
            <RangePicker range={range} custom={custom} onRange={onRange} onCustom={onCustom} />
            <Button variant="secondary" onClick={data.refresh}>
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </Button>
          </>
        }
      />

      {!data.health ? (
        <Notice
          tone="warn"
          title="Engine is offline — reading the cached snapshot"
          action={
            <Button variant="secondary" onClick={data.refresh}>
              Try again
            </Button>
          }
        >
          <span className="inline-flex items-center gap-1">
            <WifiOff className="h-3 w-3" />
            Showing {fmtInt(data.dataset?.meta.total ?? 0)} signals captured {relTime(data.snapshotAt)}. Signal
            History stays usable while the scanner is stopped; it refreshes as soon as the engine answers.
          </span>
        </Notice>
      ) : null}

      {data.cached ? (
        <Notice tone="info" title="Cached snapshot">
          This is the last successful read of the database, kept in the browser so the history opens offline.
        </Notice>
      ) : null}

      <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="px-4 py-3">
          <MiniStat label="Signals in view" value={fmtInt(signals.length)} />
          <div className="mt-2 flex items-center justify-between text-[10.5px] text-faint">
            <span>open now</span>
            <span className="tabnum text-mint">{openNow}</span>
          </div>
        </Card>
        <Card className="px-4 py-3">
          <MiniStat label="Win rate" value={fmtPct(stats.winRate)} tone={stats.winRate >= 50 ? "up" : "down"} />
          <div className="mt-2">
            <Meter pct={stats.winRate} tone={stats.winRate >= 50 ? "up" : "down"} />
          </div>
        </Card>
        <Card className="px-4 py-3">
          <MiniStat
            label="Expectancy"
            value={`${fmtR(stats.expectancy, 3)} / trade`}
            tone={stats.expectancy >= 0 ? "up" : "down"}
          />
          <div className="mt-2 flex items-center justify-between text-[10.5px] text-faint">
            <span>avg hold</span>
            <span className="tabnum text-dim">{stats.avgBars ? `${stats.avgBars.toFixed(1)} bars` : "—"}</span>
          </div>
        </Card>
        <Card className="px-4 py-3">
          <MiniStat label="Net R" value={fmtR(stats.netR, 1)} tone={stats.netR >= 0 ? "up" : "down"} />
          <div className="mt-2 flex items-center justify-between text-[10.5px] text-faint">
            <span>{fmtInt(signals.filter(isClosed).length)} closed</span>
            <span className="text-dim">{relTime(data.dataset?.meta.lastSignal)}</span>
          </div>
        </Card>
      </div>

      {data.loading && !data.dataset ? (
        <Card>
          <SkeletonRows rows={8} />
        </Card>
      ) : (
        <HistoryTable signals={signals} />
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[10.5px] text-faint">
        <span className="inline-flex items-center gap-1.5">
          <History className="h-3 w-3" />
          Source: data/history/asta.db · read-only connection per request
        </span>
        <span className="tabnum">
          snapshot {relTime(data.snapshotAt)} · {fmtInt(data.dataset?.meta.total ?? 0)} total ·{" "}
          {fmtInt(data.dataset?.meta.closed ?? 0)} closed
        </span>
      </div>
    </div>
  )
}
