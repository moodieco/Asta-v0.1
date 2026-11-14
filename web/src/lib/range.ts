import type { Signal } from "@/lib/metrics"

export type Range = "all" | "90d" | "30d"

export function withinRange(signal: Signal, range: Range): boolean {
  if (range === "all") return true
  const days = range === "90d" ? 90 : 30
  return new Date(signal.createdAt).getTime() >= Date.now() - days * 86_400_000
}

export const RANGE_OPTIONS: { value: Range; label: string }[] = [
  { value: "all", label: "All time" },
  { value: "90d", label: "90d" },
  { value: "30d", label: "30d" },
]
