import type { Signal } from "@/lib/metrics"

/* Presets are calendar windows, not trading sessions: "5 days" is 7 calendar
 * days because a trading week covers five sessions plus the weekend. */
export type Range = "1d" | "5d" | "1m" | "3m" | "6m" | "1y" | "all"

export type CustomRange = { from: string; to: string }

const RANGE_DAYS: Record<Exclude<Range, "all">, number> = {
  "1d": 1,
  "5d": 7,
  "1m": 30,
  "3m": 90,
  "6m": 182,
  "1y": 365,
}

export function withinRange(signal: Signal, range: Range, custom?: CustomRange | null): boolean {
  const at = new Date(signal.createdAt).getTime()
  if (custom && (custom.from || custom.to)) {
    const from = custom.from ? new Date(`${custom.from}T00:00:00`).getTime() : -Infinity
    const to = custom.to ? new Date(`${custom.to}T23:59:59.999`).getTime() : Infinity
    return at >= from && at <= to
  }
  if (range === "all") return true
  return at >= Date.now() - RANGE_DAYS[range] * 86_400_000
}

export const RANGE_OPTIONS: { value: Range; label: string; short: string }[] = [
  { value: "1d", label: "1 day", short: "1D" },
  { value: "5d", label: "5 days", short: "5D" },
  { value: "1m", label: "1 month", short: "1M" },
  { value: "3m", label: "3 months", short: "3M" },
  { value: "6m", label: "6 months", short: "6M" },
  { value: "1y", label: "1 year", short: "1Y" },
  { value: "all", label: "All time", short: "All" },
]
