import * as React from "react"
import { Check, ChevronDown, Loader2, Search, X } from "lucide-react"
import { cn } from "@/lib/utils"

/* ================================================================== *
 * Surfaces
 * ================================================================== */

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-line bg-surface shadow-[var(--shadow-card)]",
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
  compact = false,
}: {
  title: React.ReactNode
  subtitle?: React.ReactNode
  right?: React.ReactNode
  className?: string
  compact?: boolean
}) {
  return (
    <div
      className={cn(
        "flex items-start justify-between gap-4 px-5",
        compact ? "pt-4 pb-2" : "pt-4 pb-3",
        className,
      )}
    >
      <div className="min-w-0">
        <h3 className="text-[13px] font-semibold tracking-tight text-ink">{title}</h3>
        {subtitle ? (
          <p className="mt-0.5 text-[11.5px] leading-snug text-faint">{subtitle}</p>
        ) : null}
      </div>
      {right ? <div className="flex shrink-0 items-center gap-2">{right}</div> : null}
    </div>
  )
}

export function SectionLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("text-[10px] font-semibold uppercase tracking-[0.09em] text-faint", className)}>
      {children}
    </div>
  )
}

/* ================================================================== *
 * Badges, chips, status
 * ================================================================== */

export type Tone = "up" | "down" | "neutral" | "warn" | "info" | "open" | "mint" | "pink" | "violet"

const toneMap: Record<Tone, string> = {
  up: "border-up/20 bg-up-soft text-up",
  down: "border-down/20 bg-down-soft text-down",
  neutral: "border-line bg-surface-3 text-dim",
  warn: "border-warn/20 bg-warn-soft text-warn",
  info: "border-info/15 bg-info-soft text-info",
  open: "border-mint/20 bg-mint-soft text-mint",
  mint: "border-mint/20 bg-mint-soft text-mint",
  pink: "border-pink/20 bg-pink-soft text-pink",
  violet: "border-violet/20 bg-violet-soft text-violet",
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
        "inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-[3px] text-[10.5px] font-medium tracking-tight",
        toneMap[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function PreviewChip({ label = "Preview" }: { label?: string }) {
  return (
    <Badge tone="violet" className="gap-1">
      <span className="h-1 w-1 rounded-full bg-violet" />
      {label}
    </Badge>
  )
}

export type Health = "running" | "warning" | "error" | "stopped"

const healthTone: Record<Health, { dot: string; ring: string; text: string; label: string }> = {
  running: { dot: "bg-up", ring: "ring-up/20", text: "text-up", label: "Running" },
  warning: { dot: "bg-warn", ring: "ring-warn/20", text: "text-warn", label: "Warning" },
  error: { dot: "bg-down", ring: "ring-down/20", text: "text-down", label: "Error" },
  stopped: { dot: "bg-faint", ring: "ring-faint/20", text: "text-faint", label: "Inactive" },
}

export function StatusDot({ status, className }: { status: Health; className?: string }) {
  const tone = healthTone[status]
  return (
    <span
      className={cn("inline-flex h-2 w-2 shrink-0 rounded-full ring-4", tone.dot, tone.ring, className)}
      aria-hidden
    />
  )
}

export function StatusPill({
  status,
  label,
  className,
}: {
  status: Health
  label?: string
  className?: string
}) {
  const tone = healthTone[status]
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2 py-[3px] text-[10.5px] font-medium",
        tone.text,
        className,
      )}
    >
      <StatusDot status={status} />
      {label ?? tone.label}
    </span>
  )
}

/* ================================================================== *
 * Actions
 * ================================================================== */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "subtle"
type ButtonSize = "sm" | "md"

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "border border-transparent bg-info text-white shadow-[var(--shadow-pastel)] hover:bg-info/90 active:bg-info/80",
  secondary: "border border-line bg-surface text-dim hover:border-info/30 hover:text-ink",
  ghost: "border border-transparent text-dim hover:bg-surface-3 hover:text-ink",
  danger: "border border-down/20 bg-down-soft text-down hover:bg-down/15",
  subtle: "border border-line bg-surface-3 text-dim hover:bg-line-soft hover:text-ink",
}

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-[11.5px]",
  md: "h-9 px-3 text-[12px]",
}

export function Button({
  className,
  variant = "secondary",
  size = "sm",
  loading = false,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
}) {
  return (
    <button
      className={cn(
        "inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-lg font-medium transition-all disabled:pointer-events-none disabled:opacity-45",
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      disabled={props.disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
      {children}
    </button>
  )
}

export function IconButton({
  className,
  label,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      title={label}
      aria-label={label}
      className={cn(
        "inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-lg border border-transparent text-faint transition-colors hover:bg-surface-3 hover:text-ink disabled:pointer-events-none disabled:opacity-40",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}

export function Switch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
  label: string
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-[18px] w-[32px] shrink-0 cursor-pointer items-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-40",
        checked ? "border-up/30 bg-up" : "border-line bg-surface-3",
      )}
    >
      <span
        className={cn(
          "block h-[12px] w-[12px] rounded-full bg-white shadow-sm transition-transform",
          checked ? "translate-x-[16px]" : "translate-x-[3px]",
        )}
      />
    </button>
  )
}

/* ================================================================== *
 * Inputs
 * ================================================================== */

const fieldShell =
  "w-full rounded-lg border border-line bg-surface text-[12px] text-ink placeholder:text-faint transition-colors hover:border-info/40 focus:border-info/50 focus:outline-none focus:ring-2 focus:ring-info/10 disabled:bg-surface-3 disabled:text-faint"

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(fieldShell, "h-8 px-2.5", className)} {...props} />
}

export function Textarea({
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(fieldShell, "min-h-[68px] px-2.5 py-2 leading-relaxed", className)} {...props} />
}

export function Field({
  label,
  hint,
  error,
  required,
  children,
  className,
}: {
  label: string
  hint?: React.ReactNode
  error?: string | null
  required?: boolean
  children: React.ReactNode
  className?: string
}) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1 flex items-center gap-1 text-[11.5px] font-medium text-dim">
        {label}
        {required ? <span className="text-down">*</span> : null}
      </span>
      {children}
      {error ? (
        <span className="mt-1 block text-[10.5px] text-down">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-[10.5px] leading-relaxed text-faint">{hint}</span>
      ) : null}
    </label>
  )
}

export function Select({
  value,
  onChange,
  options,
  label,
  className,
  disabled,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  label?: string
  className?: string
  disabled?: boolean
}) {
  return (
    <span className={cn("group relative inline-flex shrink-0 items-center", className)}>
      {label ? <span className="sr-only">{label}</span> : null}
      <select
        value={value}
        disabled={disabled}
        aria-label={label}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          fieldShell,
          "h-8 cursor-pointer appearance-none pl-2.5 pr-7 disabled:cursor-not-allowed",
        )}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5 text-faint" />
    </span>
  )
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  className?: string
}) {
  return (
    <div className={cn("relative min-w-[180px] flex-1", className)}>
      <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(fieldShell, "h-8 pl-8 pr-7")}
      />
      {value ? (
        <button
          onClick={() => onChange("")}
          className="absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer text-faint hover:text-ink"
          aria-label="Clear search"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      ) : null}
    </div>
  )
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
  className?: string
}) {
  return (
    <div className={cn("inline-flex items-center gap-0.5 rounded-lg border border-line bg-surface-3 p-0.5", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "cursor-pointer rounded-[6px] px-2.5 py-1 text-[11.5px] font-medium transition-all",
            value === o.value
              ? "bg-surface text-ink shadow-[0_1px_2px_rgba(16,24,40,0.08)]"
              : "text-faint hover:text-dim",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Tabs({
  value,
  onChange,
  items,
  className,
}: {
  value: string
  onChange: (v: string) => void
  items: { value: string; label: string; count?: number }[]
  className?: string
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1 border-b border-line", className)}>
      {items.map((item) => {
        const active = item.value === value
        return (
          <button
            key={item.value}
            onClick={() => onChange(item.value)}
            className={cn(
              "relative -mb-px cursor-pointer px-3 pb-2.5 pt-1 text-[12px] font-medium transition-colors",
              active ? "text-ink" : "text-faint hover:text-dim",
            )}
          >
            <span className="flex items-center gap-1.5">
              {item.label}
              {item.count !== undefined ? (
                <span
                  className={cn(
                    "tabnum rounded-full px-1.5 py-[1px] text-[10px]",
                    active ? "bg-info-soft text-info" : "bg-surface-3 text-faint",
                  )}
                >
                  {item.count}
                </span>
              ) : null}
            </span>
            {active ? <span className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-info" /> : null}
          </button>
        )
      })}
    </div>
  )
}

/* ================================================================== *
 * Measures
 * ================================================================== */

export function Meter({
  pct,
  tone = "up",
  className,
}: {
  pct: number
  tone?: "up" | "down" | "neutral" | "info" | "warn"
  className?: string
}) {
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-3", className)}>
      <div
        className={cn(
          "h-full rounded-full transition-all",
          tone === "up" && "bg-up",
          tone === "down" && "bg-down",
          tone === "neutral" && "bg-faint",
          tone === "info" && "bg-info",
          tone === "warn" && "bg-warn",
        )}
        style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
      />
    </div>
  )
}

export function Progress({ pct, className }: { pct: number; className?: string }) {
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-surface-3", className)}>
      <div
        className="h-full rounded-full bg-gradient-to-r from-info via-[#5b93f5] to-mint transition-[width] duration-300"
        style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
      />
    </div>
  )
}

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
          tone === "up" && "text-up",
          tone === "down" && "text-down",
          tone === "neutral" && "text-dim",
        )}
      >
        {value}
      </span>
    </div>
  )
}

/* ================================================================== *
 * States
 * ================================================================== */

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-32 items-center justify-center rounded-xl border border-dashed border-line bg-surface-2 text-[12px] text-faint">
      {children}
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode
  title: string
  description?: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line bg-surface-2 px-6 py-9 text-center",
        className,
      )}
    >
      {icon ? <div className="grid h-10 w-10 place-items-center rounded-xl bg-surface-3 text-faint">{icon}</div> : null}
      <div className="text-[12.5px] font-medium text-ink">{title}</div>
      {description ? <p className="max-w-sm text-[11.5px] leading-relaxed text-faint">{description}</p> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  )
}

export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div style={style} className={cn("animate-pulse rounded-md bg-surface-3", className)} />
}

export function SkeletonRows({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2 px-5 py-4", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" style={{ opacity: 1 - i * 0.12 }} />
      ))}
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin text-faint", className)} />
}

/* ================================================================== *
 * Tables
 * ================================================================== */

export function Table({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <table className="w-full text-[12px]">{children}</table>
    </div>
  )
}

export function Th({
  children,
  align = "left",
  className,
}: {
  children?: React.ReactNode
  align?: "left" | "right" | "center"
  className?: string
}) {
  return (
    <th
      className={cn(
        "whitespace-nowrap border-b border-line bg-surface-2 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.07em] text-faint first:pl-5 last:pr-5",
        align === "right" && "text-right",
        align === "center" && "text-center",
        align === "left" && "text-left",
        className,
      )}
    >
      {children}
    </th>
  )
}

export function Td({
  children,
  align = "left",
  className,
  title,
}: {
  children?: React.ReactNode
  align?: "left" | "right" | "center"
  className?: string
  title?: string
}) {
  return (
    <td
      title={title}
      className={cn(
        "border-b border-line-soft px-3 py-2.5 align-middle text-dim first:pl-5 last:pr-5",
        align === "right" && "text-right",
        align === "center" && "text-center",
        className,
      )}
    >
      {children}
    </td>
  )
}

export function Tr({
  children,
  className,
  onClick,
}: {
  children: React.ReactNode
  className?: string
  onClick?: () => void
}) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        "transition-colors last:[&>td]:border-b-0 hover:bg-surface-2",
        onClick && "cursor-pointer",
        className,
      )}
    >
      {children}
    </tr>
  )
}

/* ================================================================== *
 * CountUp
 * ================================================================== */

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

export function CheckRow({
  ok,
  children,
  severity = "error",
}: {
  ok: boolean
  children: React.ReactNode
  severity?: "error" | "warning"
}) {
  const tone = ok ? "up" : severity === "warning" ? "warn" : "down"
  return (
    <div className="flex items-start gap-2 text-[11.5px] leading-relaxed">
      <span
        className={cn(
          "mt-[1px] grid h-4 w-4 shrink-0 place-items-center rounded-full",
          tone === "up" && "bg-up-soft text-up",
          tone === "warn" && "bg-warn-soft text-warn",
          tone === "down" && "bg-down-soft text-down",
        )}
      >
        {ok ? <Check className="h-2.5 w-2.5" /> : <X className="h-2.5 w-2.5" />}
      </span>
      <span className={cn(ok ? "text-dim" : tone === "warn" ? "text-warn" : "text-down")}>{children}</span>
    </div>
  )
}
