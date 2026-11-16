import { useEffect, useRef, useState } from "react"
import { Calendar, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { RANGE_OPTIONS, type CustomRange, type Range } from "@/lib/range"
import { Button, IconButton, Input } from "@/components/ui"

/* Presets + a calendar popover for an explicit from/to window. Used by
 * Overview and Signal History so both screens filter on the same selection. */
export function RangePicker({
  range,
  custom,
  onRange,
  onCustom,
}: {
  range: Range
  custom: CustomRange | null
  onRange: (range: Range) => void
  onCustom: (custom: CustomRange | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [from, setFrom] = useState(custom?.from ?? "")
  const [to, setTo] = useState(custom?.to ?? "")
  const panel = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    setFrom(custom?.from ?? "")
    setTo(custom?.to ?? "")
  }, [custom])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open])

  const active = custom !== null
  const label = active ? `${custom.from || "…"} → ${custom.to || "…"}` : "Custom range"

  return (
    <div className="relative flex items-center gap-1">
      <div className="inline-flex items-center gap-0.5 rounded-lg border border-line bg-surface-3 p-0.5">
        {RANGE_OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={() => onRange(option.value)}
            title={option.label}
            className={cn(
              "cursor-pointer rounded-[6px] px-2.5 py-1 text-[11.5px] font-medium transition-all",
              !active && range === option.value
                ? "bg-surface text-ink shadow-[0_1px_2px_rgba(16,24,40,0.08)]"
                : "text-faint hover:text-dim",
            )}
          >
            {option.short}
          </button>
        ))}
      </div>

      <button
        onClick={() => setOpen((value) => !value)}
        title={label}
        aria-label="Custom date range"
        aria-expanded={open}
        className={cn(
          "inline-flex h-[30px] cursor-pointer items-center gap-1.5 rounded-lg border px-2 text-[11.5px] font-medium transition-colors",
          active
            ? "border-info/30 bg-info-soft text-info"
            : "border-line bg-surface text-faint hover:text-ink",
        )}
      >
        <Calendar className="h-3.5 w-3.5" />
        {active ? <span className="tabnum">{label}</span> : null}
      </button>

      {active ? (
        <IconButton label="Clear custom range" onClick={() => onCustom(null)}>
          <X className="h-3 w-3" />
        </IconButton>
      ) : null}

      {open ? (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div
            ref={panel}
            className="absolute right-0 top-[36px] z-50 w-[248px] rounded-xl border border-line bg-surface p-3 shadow-[var(--shadow-pop)]"
          >
            <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">Custom range</div>
            <div className="mt-2 space-y-2">
              <label className="block">
                <span className="mb-1 block text-[10.5px] text-faint">From</span>
                <Input type="date" value={from} max={to || undefined} onChange={(event) => setFrom(event.target.value)} />
              </label>
              <label className="block">
                <span className="mb-1 block text-[10.5px] text-faint">To</span>
                <Input type="date" value={to} min={from || undefined} onChange={(event) => setTo(event.target.value)} />
              </label>
            </div>
            <div className="mt-3 flex items-center justify-between gap-2">
              <Button
                variant="ghost"
                onClick={() => {
                  setFrom("")
                  setTo("")
                  onCustom(null)
                  setOpen(false)
                }}
              >
                Reset
              </Button>
              <Button
                variant="primary"
                disabled={!from && !to}
                onClick={() => {
                  onCustom({ from, to })
                  setOpen(false)
                }}
              >
                Apply
              </Button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
