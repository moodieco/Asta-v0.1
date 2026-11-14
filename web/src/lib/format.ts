export const nf = new Intl.NumberFormat("en-US")

export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—"
  return nf.format(Math.round(n))
}

export function fmtR(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—"
  const v = n.toFixed(digits)
  return `${n > 0 ? "+" : ""}${v}R`
}

export function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—"
  return `${n.toFixed(digits)}%`
}

export function fmtPrice(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—"
  if (n >= 1000) return nf.format(Math.round(n))
  if (n >= 1) return n.toFixed(2)
  return n.toPrecision(4)
}

const dtf = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
})

const dfShort = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  timeZone: "UTC",
})

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  return `${dtf.format(d)} UTC`
}

export function fmtDay(iso: string | null | undefined): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  return dfShort.format(d)
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "—"
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return "—"
  const diff = Date.now() - then
  const mins = Math.round(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  return `${Math.round(days / 30)}mo ago`
}

export function dayKey(iso: string): string {
  return iso.slice(0, 10)
}
