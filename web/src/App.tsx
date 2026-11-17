import { useEffect, useMemo, useState } from "react"
import { CircleDot } from "lucide-react"
import { fetchSession, logoutSession, useAppData, type SessionInfo } from "@/lib/api"
import { useRoute } from "@/lib/router"
import type { CustomRange, Range } from "@/lib/range"
import { useLibrary } from "@/lib/library"
import { buildScannerRows } from "@/lib/scanners"
import { MobileNav, Sidebar, Topbar } from "@/components/layout"
import { ToastProvider } from "@/components/feedback"
import { ShareDialog } from "@/components/share"
import { Card, Skeleton } from "@/components/ui"
import { OverviewPage } from "@/pages/Overview"
import { ScannerManagementPage } from "@/pages/ScannerManagement"
import { ScannerDetailPage } from "@/pages/ScannerDetail"
import { UploadScannerPage } from "@/pages/UploadScanner"
import { AlertsPage } from "@/pages/Alerts"
import { UploadHistoryPage } from "@/pages/UploadHistory"
import { RecycleBinPage } from "@/pages/RecycleBin"
import { SystemMonitorPage } from "@/pages/SystemMonitor"
import { SettingsPage } from "@/pages/Settings"
import { SetupPage } from "@/pages/Setup"
import { LoginPage } from "@/pages/Login"
import { SignalsPage } from "@/pages/Signals"

const TITLES: Record<string, string> = {
  overview: "Overview",
  system: "System monitor",
  scanners: "Scanner management",
  upload: "Upload scanner",
  history: "Signal history",
  uploads: "Upload history",
  alerts: "Alert management",
  settings: "Settings",
  setup: "Setup",
}

/* Skipping the wizard must stick: without this the gate below drags the user
 * straight back to /setup and the dashboard becomes unreachable. */
const SKIP_KEY = "asta.setup.skipped.v1"

function readSkip(): boolean {
  try {
    return window.localStorage.getItem(SKIP_KEY) === "1"
  } catch {
    return false
  }
}

function writeSkip(skipped: boolean): void {
  try {
    if (skipped) window.localStorage.setItem(SKIP_KEY, "1")
    else window.localStorage.removeItem(SKIP_KEY)
  } catch {
    /* private mode: the gate simply stays strict for this session */
  }
}

export default function App() {
  const data = useAppData()
  const route = useRoute()
  const { access, refresh: refreshAccess } = useLibrary()
  const [range, setRange] = useState<Range>("all")
  const [custom, setCustom] = useState<CustomRange | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [shareOpen, setShareOpen] = useState(false)
  const [setupSkipped, setSetupSkipped] = useState(readSkip)
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [sessionState, setSessionState] = useState<"loading" | "ready" | "offline">("loading")

  const loadSession = () => {
    setSessionState("loading")
    fetchSession()
      .then((next) => {
        setSession(next)
        setSessionState("ready")
      })
      .catch(() => {
        setSession(null)
        setSessionState("offline")
      })
  }

  useEffect(() => {
    loadSession()
  }, [])

  const root = route.segments[0] ?? "overview"
  const isTrash = root === "scanners" && route.segments[1] === "trash"

  /* Setup gate: an unconfigured engine opens the wizard first — once.
   * "Skip to dashboard" and a completed setup both release it, otherwise the
   * redirect fights the user and every route snaps back to /setup. */
  useEffect(() => {
    if (!data.setup?.available) return
    if (data.setup.complete) {
      if (setupSkipped) {
        writeSkip(false)
        setSetupSkipped(false)
      }
      return
    }
    if (setupSkipped) return
    if (root !== "setup") route.navigate("/setup", { replace: true })
  }, [data.setup, root, route, setupSkipped])

  const skipSetup = () => {
    writeSkip(true)
    setSetupSkipped(true)
    route.navigate("/overview")
  }

  useEffect(() => {
    const title = TITLES[root] ?? "ASTA"
    document.title = `${title} · ASTA`
  }, [root])

  /* A preset clears the custom window and vice versa — one source of truth. */
  const selectRange = (next: Range) => {
    setRange(next)
    setCustom(null)
  }
  const selectCustom = (next: CustomRange | null) => {
    setCustom(next)
    if (next) setRange("all")
  }

  const refresh = () => {
    setRefreshing(true)
    data.refresh()
    window.setTimeout(() => setRefreshing(false), 900)
  }

  const scanners = useMemo(
    () =>
      buildScannerRows({
        scanners: data.setup?.scanners ?? data.config?.scanners ?? [],
        setup: data.setup,
        system: data.system,
        signals: data.dataset?.signals ?? [],
        overrides: {},
      }),
    [data.setup, data.config, data.system, data.dataset],
  )

  const engineStatus = data.health ? (scanners.some((row) => row.health === "error") ? "warning" : "running") : "stopped"
  const engineLabel = data.health ? (engineStatus === "warning" ? "Degraded" : "Running") : "Offline"

  const title = isTrash
    ? "Recycle bin"
    : root === "scanners" && route.segments[1]
      ? scanners.find((row) => row.id.toLowerCase() === route.segments[1].toLowerCase())?.name ?? "Scanner detail"
      : TITLES[root] ?? "ASTA"

  const signOut = () => {
    /* Wait for the cookie to be cleared before asking who we are — otherwise
     * the next /api/session still sees the old session and nothing changes. */
    logoutSession()
      .catch(() => undefined)
      .finally(() => loadSession())
  }

  /* No credential yet: the role + PIN screen replaces the shell entirely. */
  if (sessionState === "loading") {
    return <BootScreen title="ASTA" note="Checking your session…" />
  }
  if (sessionState === "offline") {
    return (
      <BootScreen
        title="ASTA is not answering"
        note="The dashboard could not reach the engine. Start it with `asta serve` and try again."
        onRetry={loadSession}
      />
    )
  }
  if (session && !session.authenticated) {
    return (
      <LoginPage
        session={session}
        onAuthed={(role) => {
          setSession((current) => (current ? { ...current, authenticated: true, role } : current))
          data.refresh()
          refreshAccess()
        }}
      />
    )
  }

  return (
    <ToastProvider>
      <div className="flex min-h-screen">
        <Sidebar
          activePath={`/${root}`}
          onNavigate={route.navigate}
          engineStatus={engineStatus}
          engineLabel={engineLabel}
          setupComplete={data.setup?.complete ?? true}
          signals={data.dataset?.meta.total ?? data.health?.database.signals ?? 0}
          lastRefresh={data.lastRefresh}
        />
        <MobileNav
          open={menuOpen}
          onClose={() => setMenuOpen(false)}
          activePath={`/${root}`}
          onNavigate={route.navigate}
          setupComplete={data.setup?.complete ?? true}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar
            title={title}
            crumbs={root === "overview" ? [] : ["ASTA"]}
            engineStatus={engineStatus}
            engineLabel={engineLabel}
            onRefresh={refresh}
            refreshing={refreshing}
            onOpenMenu={() => setMenuOpen(true)}
            showMenu
            onShare={access === "editor" ? () => setShareOpen(true) : undefined}
            viewOnly={access === "viewer"}
            onSignOut={session && !session.loopback ? signOut : undefined}
          />

          <main className="min-w-0 flex-1 px-3 pb-8 pt-4 sm:px-5">
            {data.loading && !data.dataset && !data.setup ? (
              <ShellSkeleton />
            ) : (
              <>
                {root === "overview" ? (
                  <OverviewPage
                    data={data}
                    range={range}
                    onRange={selectRange}
                    custom={custom}
                    onCustom={selectCustom}
                    dataset={data.dataset}
                  />
                ) : null}
                {root === "system" ? <SystemMonitorPage data={data} navigate={route.navigate} /> : null}
                {isTrash ? <RecycleBinPage navigate={route.navigate} /> : null}
                {root === "scanners" && !route.segments[1] ? (
                  <ScannerManagementPage data={data} navigate={route.navigate} />
                ) : null}
                {root === "scanners" && route.segments[1] && !isTrash ? (
                  <ScannerDetailPage data={data} scannerId={route.segments[1]} navigate={route.navigate} />
                ) : null}
                {root === "upload" ? <UploadScannerPage data={data} navigate={route.navigate} /> : null}
                {root === "history" ? (
                  <SignalsPage data={data} range={range} onRange={selectRange} custom={custom} onCustom={selectCustom} />
                ) : null}
                {root === "uploads" ? <UploadHistoryPage data={data} navigate={route.navigate} /> : null}
                {root === "alerts" ? <AlertsPage data={data} /> : null}
                {root === "settings" ? <SettingsPage data={data} navigate={route.navigate} /> : null}
                {root === "setup" ? <SetupPage data={data} navigate={route.navigate} onSkip={skipSetup} /> : null}
                {!TITLES[root] ? <NotFound onHome={() => route.navigate("/overview")} /> : null}
              </>
            )}
          </main>

          <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-3 text-[10px] text-faint sm:px-5">
            <span className="inline-flex items-center gap-1.5">
              <CircleDot className="h-2.5 w-2.5 text-up" />
              ASTA v0.1 · signal engine · scanners + recycle bin on disk
            </span>
            <span className="tabnum">
              {data.dataset?.meta.total.toLocaleString() ?? "—"} signals ·{" "}
              {data.dataset?.meta.closed.toLocaleString() ?? "—"} closed · snapshot{" "}
              {data.snapshotAt
                ? new Date(data.snapshotAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                : "—"}
            </span>
          </footer>
        </div>
      </div>

      <ShareDialog open={shareOpen} onClose={() => setShareOpen(false)} />
    </ToastProvider>
  )
}

function BootScreen({
  title,
  note,
  onRetry,
}: {
  title: string
  note: string
  onRetry?: () => void
}) {
  return (
    <div className="grid min-h-screen place-items-center px-6">
      <div className="w-full max-w-sm text-center">
        <div className="mx-auto mb-3 grid h-9 w-9 place-items-center rounded-xl bg-info text-[13px] font-bold text-white">
          A
        </div>
        <div className="text-[13px] font-semibold text-ink">{title}</div>
        <p className="mt-1 text-[11.5px] leading-relaxed text-faint">{note}</p>
        {onRetry ? (
          <button
            onClick={onRetry}
            className="mt-3 cursor-pointer rounded-lg border border-line bg-surface px-3 py-1.5 text-[11.5px] font-medium text-dim hover:text-ink"
          >
            Try again
          </button>
        ) : (
          <div className="mx-auto mt-3 h-1 w-24 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full w-1/2 animate-pulse rounded-full bg-info/70" />
          </div>
        )}
      </div>
    </div>
  )
}

function ShellSkeleton() {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-7 w-32" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Card key={index} className="px-4 py-4">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-2 h-6 w-20" />
            <Skeleton className="mt-3 h-2 w-full" />
          </Card>
        ))}
      </div>
      <Card className="p-4">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="mt-3 h-[240px] w-full" />
      </Card>
    </div>
  )
}

function NotFound({ onHome }: { onHome: () => void }) {
  return (
    <Card className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="text-[13px] font-semibold text-ink">Page not found</div>
      <p className="mt-1 max-w-sm text-[11.5px] text-faint">
        That route does not exist in this build. The sidebar has every screen.
      </p>
      <button
        onClick={onHome}
        className="mt-3 cursor-pointer rounded-lg border border-line bg-surface px-3 py-1.5 text-[11.5px] font-medium text-dim hover:text-ink"
      >
        Back to overview
      </button>
    </Card>
  )
}
