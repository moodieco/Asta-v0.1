import * as React from "react"
import { cn } from "@/lib/utils"

/* ---------- Card ---------- */
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-line bg-surface/70 backdrop-blur-sm shadow-[0_1px_0_0_rgba(255,255,255,0.03)_inset,0_18px_40px_-24px_rgba(0,0,0,0.9)]",
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({
  title,
  subtitle,
  right,
  className,
}: {
  title: React.ReactNode
  subtitle?: React.ReactNode
  right?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4 px-5 pt-4 pb-3", className)}>
      <div className="min-w-0">
        <h3 className="text-[13px] font-medium tracking-tight text-ink">{title}</h3>
        {subtitle ? <p className="mt-0.5 text-[11.5px] leading-snug text-faint">{subtitle}</p> : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  )
}

/* ---------- Badge ---------- */
type Tone = "up" | "down" | "neutral" | "warn" | "info" | "open"

const toneMap: Record<Tone, string> = {
  up: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  down: "border-rose-400/25 bg-rose-400/10 text-rose-300",
  neutral: "border-line bg-white/[0.03] text-dim",
  warn: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  info: "border-sky-400/25 bg-sky-400/10 text-sky-300",
  open: "border-teal-300/25 bg-teal-300/10 text-teal-200",
}

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone
  className?: string
  children: React.ReactNode
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10.5px] font-medium tracking-tight whitespace-nowrap",
        toneMap[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

/* ---------- Button ---------- */
export function Button({
  className,
  variant = "ghost",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "ghost" | "solid" | "outline" }) {
  return (
    <button
      className={cn(
        "inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[12px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-40",
        variant === "ghost" && "text-dim hover:bg-white/[0.05] hover:text-ink",
        variant === "outline" && "border border-line bg-white/[0.02] text-dim hover:border-emerald-400/30 hover:text-ink",
        variant === "solid" && "bg-emerald-400/15 text-emerald-200 hover:bg-emerald-400/25",
        className,
      )}
      {...props}
    />
  )
}

/* ---------- Select ---------- */
export function Select({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  label?: string
  className?: string
}) {
  return (
    <label className={cn("group relative inline-flex shrink-0 items-center", className)}>
      {label ? <span className="sr-only">{label}</span> : null}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 cursor-pointer appearance-none rounded-lg border border-line bg-surface-2 pl-2.5 pr-7 text-[12px] text-dim outline-none transition-colors hover:border-emerald-400/25 hover:text-ink focus:border-emerald-400/40 focus:text-ink"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-surface-2 text-ink">
            {o.label}
          </option>
        ))}
      </select>
      <svg
        aria-hidden
        viewBox="0 0 12 12"
        className="pointer-events-none absolute right-2 h-3 w-3 text-faint transition-colors group-hover:text-dim"
      >
        <path d="M2.5 4.5L6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    </label>
  )
}

/* ---------- Search input ---------- */
export function SearchInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <div className="relative flex-1 min-w-[180px]">
      <svg viewBox="0 0 16 16" className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint">
        <circle cx="7" cy="7" r="4.2" fill="none" stroke="currentColor" strokeWidth="1.4" />
        <path d="M10.2 10.2L13.5 13.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-8 w-full rounded-lg border border-line bg-surface-2 pl-8 pr-2.5 text-[12px] text-ink placeholder:text-faint outline-none transition-colors focus:border-emerald-400/40"
      />
      {value ? (
        <button
          onClick={() => onChange("")}
          className="absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer text-faint hover:text-ink"
          aria-label="Clear search"
        >
          ×
        </button>
      ) : null}
    </div>
  )
}

/* ---------- Segmented control ---------- */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
}) {
  return (
    <div className="inline-flex items-center gap-0.5 rounded-lg border border-line bg-surface-2/70 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "cursor-pointer rounded-[6px] px-2.5 py-1 text-[11.5px] font-medium transition-colors",
            value === o.value ? "bg-emerald-400/15 text-emerald-200" : "text-faint hover:text-dim",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/* ---------- Stat row ---------- */
export function MiniStat({
  label,
  value,
  tone = "neutral",
}: {
  label: string
  value: React.ReactNode
  tone?: "up" | "down" | "neutral"
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-[11px] text-faint">{label}</span>
      <span
        className={cn(
          "tabnum text-[12px] font-medium",
          tone === "up" && "text-emerald-300",
          tone === "down" && "text-rose-300",
          tone === "neutral" && "text-dim",
        )}
      >
        {value}
      </span>
    </div>
  )
}

/* ---------- Meter ---------- */
export function Meter({ pct, tone = "up" }: { pct: number; tone?: "up" | "down" | "neutral" }) {
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-white/[0.06]">
      <div
        className={cn(
          "h-full rounded-full transition-all",
          tone === "up" && "bg-emerald-400/70",
          tone === "down" && "bg-rose-400/70",
          tone === "neutral" && "bg-sky-400/60",
        )}
        style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
      />
    </div>
  )
}

/* ---------- Empty ---------- */
export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-32 items-center justify-center rounded-xl border border-dashed border-line/80 text-[12px] text-faint">
      {children}
    </div>
  )
}

/* ---------- CountUp (dependency-free, settles reliably) ---------- */
export function CountUp({
  value,
  decimals = 0,
  duration = 650,
  className,
}: {
  value: number
  decimals?: number
  duration?: number
  className?: string
}) {
  const [display, setDisplay] = React.useState(0)
  React.useEffect(() => {
    const target = Number.isFinite(value) ? value : 0
    const start = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      setDisplay(target * eased)
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, duration])
  return <span className={className}>{display.toFixed(decimals)}</span>
}
