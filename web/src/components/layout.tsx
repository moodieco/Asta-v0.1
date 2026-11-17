import * as React from "react"
import {
  Activity,
  Bell,
  Boxes,
  ChevronLeft,
  CloudUpload,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  PackageCheck,
  Recycle,
  RefreshCw,
  Settings,
  Share2,
  ShieldAlert,
  Sun,
  X,
  Zap,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { relTime } from "@/lib/format"
import { useTheme } from "@/lib/theme"
import { Badge, Button, IconButton, StatusPill } from "@/components/ui"

export interface NavItem {
  path: string
  label: string
  hint: string
  icon: React.ElementType
  group: string
  soon?: boolean
}

export const NAV_ITEMS: NavItem[] = [
  { path: "/overview", label: "Overview", hint: "Health, edge, activity", icon: LayoutDashboard, group: "Monitor" },
  { path: "/system", label: "System Monitor", hint: "Components & resources", icon: Activity, group: "Monitor" },
  { path: "/scanners", label: "Scanner Management", hint: "Installed scanners", icon: Boxes, group: "Scanners" },
  { path: "/upload", label: "Upload Scanner", hint: "Validate & install", icon: CloudUpload, group: "Scanners", soon: true },
  { path: "/scanners/trash", label: "Recycle Bin", hint: "Restore deleted", icon: Recycle, group: "Scanners", soon: true },
  { path: "/history", label: "Signal History", hint: "Every signal", icon: History, group: "Signals" },
  { path: "/uploads", label: "Upload History", hint: "Versions & changes", icon: PackageCheck, group: "Signals" },
  { path: "/alerts", label: "Alert Management", hint: "Discord webhooks", icon: Bell, group: "Configuration" },
  { path: "/settings", label: "Settings", hint: "General & system", icon: Settings, group: "Configuration" },
]

const GROUP_ORDER = ["Monitor", "Scanners", "Signals", "Configuration"]

export function Sidebar({
  activePath,
  onNavigate,
  engineStatus,
  engineLabel,
  setupComplete,
  signals,
  lastRefresh,
}: {
  activePath: string
  onNavigate: (path: string) => void
  engineStatus: "running" | "warning" | "error" | "stopped"
  engineLabel: string
  setupComplete: boolean
  signals: number
  lastRefresh: number
}) {
  return (
    <aside className="sticky top-0 hidden h-screen w-[244px] shrink-0 flex-col border-r border-line bg-surface/80 backdrop-blur-xl lg:flex">
      <button
        onClick={() => onNavigate("/overview")}
        className="flex cursor-pointer items-center gap-2.5 px-4 pb-4 pt-5 text-left"
      >
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-info via-[#6f9df7] to-mint text-white shadow-[var(--shadow-pastel)]">
          <Zap className="h-4 w-4" strokeWidth={2.4} />
        </span>
        <span className="leading-tight">
          <span className="block text-[14px] font-semibold tracking-tight text-ink">ASTA</span>
          <span className="block text-[10px] text-faint">signal engine · v0.1</span>
        </span>
      </button>

      <nav className="flex-1 overflow-y-auto overflow-x-hidden px-2.5 pb-3">
        {GROUP_ORDER.map((group) => {
          const items = NAV_ITEMS.filter((item) => item.group === group)
          if (!items.length) return null
          return (
            <div key={group} className="mb-3.5">
              <div className="px-2 pb-1 text-[9.5px] font-semibold uppercase tracking-[0.11em] text-faint">
                {group}
              </div>
              <div className="space-y-0.5">
                {items.map((item) => {
                  const Icon = item.icon
                  const active = activePath === item.path || activePath.startsWith(`${item.path}/`)
                  return (
                    <button
                      key={item.path}
                      onClick={() => onNavigate(item.path)}
                      className={cn(
                        "group flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-2 py-[7px] text-left transition-colors",
                        active
                          ? "bg-info-soft text-ink"
                          : "text-dim hover:bg-surface-3 hover:text-ink",
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-[15px] w-[15px] shrink-0",
                          active ? "text-info" : "text-faint group-hover:text-dim",
                        )}
                        strokeWidth={1.9}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[12px] font-medium leading-tight">
                          {item.label}
                        </span>
                      </span>
                      {item.soon ? (
                        <span className="shrink-0 rounded-full border border-warn/20 bg-warn-soft px-1.5 py-px text-[9px] font-semibold uppercase tracking-[0.06em] text-warn">
                          Soon
                        </span>
                      ) : null}
                      {active ? <span className="h-1.5 w-1.5 rounded-full bg-info" /> : null}
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}

        {!setupComplete ? (
          <button
            onClick={() => onNavigate("/setup")}
            className="flex w-full cursor-pointer items-center gap-2 rounded-lg border border-warn/25 bg-warn-soft/70 px-2.5 py-2 text-left text-[11.5px] font-medium text-warn"
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            Finish setup
          </button>
        ) : null}
      </nav>

      <div className="space-y-2 border-t border-line px-3 py-3">
        <div className="rounded-xl border border-line bg-surface-2 px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">
              Engine
            </span>
            <StatusPill status={engineStatus} label={engineLabel} />
          </div>
          <div className="mt-2 space-y-1 text-[10.5px] text-faint">
            <div className="flex justify-between gap-2">
              <span>signals stored</span>
              <span className="tabnum text-dim">{signals.toLocaleString()}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span>refreshed</span>
              <span className="text-dim">{relTime(new Date(lastRefresh).toISOString())}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between gap-2 px-1 text-[9.5px] text-faint">
          <span>sqlite · live api · recycle bin</span>
        </div>
      </div>
    </aside>
  )
}

export function MobileNav({
  open,
  onClose,
  activePath,
  onNavigate,
  setupComplete,
}: {
  open: boolean
  onClose: () => void
  activePath: string
  onNavigate: (path: string) => void
  setupComplete: boolean
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[60] lg:hidden">
      <div className="absolute inset-0 bg-ink/20 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div className="relative flex h-full w-[270px] flex-col border-r border-line bg-surface">
        <div className="flex items-center justify-between px-4 py-3">
          <span className="text-[13px] font-semibold text-ink">ASTA</span>
          <IconButton label="Close menu" onClick={onClose}>
            <X className="h-4 w-4" />
          </IconButton>
        </div>
        <nav className="flex-1 overflow-y-auto px-2.5 pb-4">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const active = activePath === item.path
            return (
              <button
                key={item.path}
                onClick={() => {
                  onNavigate(item.path)
                  onClose()
                }}
                className={cn(
                  "mb-0.5 flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[12px] font-medium",
                  active ? "bg-info-soft text-ink" : "text-dim",
                )}
              >
                <Icon className={cn("h-4 w-4", active ? "text-info" : "text-faint")} />
                <span className="flex-1">{item.label}</span>
                {item.soon ? (
                  <span className="rounded-full border border-warn/20 bg-warn-soft px-1.5 py-px text-[9px] font-semibold uppercase tracking-[0.06em] text-warn">
                    Soon
                  </span>
                ) : null}
              </button>
            )
          })}
          {!setupComplete ? (
            <button
              onClick={() => {
                onNavigate("/setup")
                onClose()
              }}
              className="mt-2 flex w-full cursor-pointer items-center gap-2 rounded-lg border border-warn/25 bg-warn-soft/70 px-2.5 py-2 text-[11.5px] font-medium text-warn"
            >
              <ShieldAlert className="h-3.5 w-3.5" /> Finish setup
            </button>
          ) : null}
        </nav>
      </div>
    </div>
  )
}

export function Topbar({
  title,
  crumbs,
  engineStatus,
  engineLabel,
  onRefresh,
  refreshing,
  onOpenMenu,
  showMenu,
  onShare,
  viewOnly = false,
  onSignOut,
}: {
  title: string
  crumbs?: string[]
  engineStatus: "running" | "warning" | "error" | "stopped"
  engineLabel: string
  onRefresh: () => void
  refreshing: boolean
  onOpenMenu: () => void
  showMenu: boolean
  onShare?: () => void
  viewOnly?: boolean
  onSignOut?: () => void
}) {
  const { theme, toggle } = useTheme()
  const dark = theme === "dark"

  return (
    <header className="sticky top-0 z-40 flex h-[54px] items-center gap-2 border-b border-line bg-bg/85 px-3 backdrop-blur-xl sm:px-5">
      {showMenu ? (
        <IconButton label="Open menu" onClick={onOpenMenu} className="lg:hidden">
          <Menu className="h-4 w-4" />
        </IconButton>
      ) : null}
      <div className="flex min-w-0 items-center gap-1.5 text-[11.5px] text-faint">
        {crumbs?.length ? (
          <>
            {crumbs.map((crumb) => (
              <React.Fragment key={crumb}>
                <span className="hidden truncate sm:inline">{crumb}</span>
                <span className="hidden text-line sm:inline">/</span>
              </React.Fragment>
            ))}
          </>
        ) : null}
        <span className="truncate text-[12.5px] font-medium text-ink">{title}</span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        {viewOnly ? <Badge tone="warn">view only</Badge> : null}
        <span className="hidden sm:inline">
          <StatusPill status={engineStatus} label={engineLabel} />
        </span>
        <IconButton
          label={dark ? "Switch to light theme" : "Switch to dark theme"}
          onClick={toggle}
        >
          {dark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </IconButton>
        {onShare ? (
          <Button variant="secondary" onClick={onShare} className="gap-1.5">
            <Share2 className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Share</span>
          </Button>
        ) : null}
        {onSignOut ? (
          <IconButton label="Sign out" onClick={onSignOut}>
            <LogOut className="h-3.5 w-3.5" />
          </IconButton>
        ) : null}
        <Button variant="secondary" onClick={onRefresh} className="gap-1.5">
          <RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} />
          <span className="hidden sm:inline">Refresh</span>
        </Button>
      </div>
    </header>
  )
}

export function PageHeader({
  title,
  description,
  actions,
  back,
  onBack,
  badge,
}: {
  title: React.ReactNode
  description?: React.ReactNode
  actions?: React.ReactNode
  back?: string
  onBack?: () => void
  badge?: React.ReactNode
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        {back ? (
          <button
            onClick={onBack}
            className="mb-1.5 inline-flex cursor-pointer items-center gap-1 text-[11.5px] font-medium text-faint transition-colors hover:text-ink"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            {back}
          </button>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-[19px] font-semibold leading-tight tracking-tight text-ink">{title}</h1>
          {badge}
        </div>
        {description ? (
          <p className="mt-1 max-w-3xl text-[12px] leading-relaxed text-faint">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  )
}

export function Notice({
  tone = "info",
  title,
  children,
  action,
}: {
  tone?: "info" | "warn" | "down" | "up"
  title: string
  children?: React.ReactNode
  action?: React.ReactNode
}) {
  const map = {
    info: "border-info/20 bg-info-soft/70 text-info",
    warn: "border-warn/25 bg-warn-soft/70 text-warn",
    down: "border-down/20 bg-down-soft/70 text-down",
    up: "border-up/20 bg-up-soft/70 text-up",
  } as const
  return (
    <div className={cn("mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border px-3.5 py-2.5", map[tone])}>
      <div className="min-w-0 flex-1">
        <div className="text-[11.5px] font-semibold">{title}</div>
        {children ? <div className="mt-0.5 text-[11px] leading-relaxed opacity-90">{children}</div> : null}
      </div>
      {action}
    </div>
  )
}
