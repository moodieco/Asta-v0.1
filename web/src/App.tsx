import { useEffect, useMemo, useState } from "react"
import { CircleDot } from "lucide-react"
import { useAppData } from "@/lib/api"
import { useRoute } from "@/lib/router"
import type { Range } from "@/lib/range"
import { usePreview } from "@/lib/preview"
import { buildScannerRows } from "@/lib/scanners"
import { MobileNav, Sidebar, Topbar } from "@/components/layout"
import { ToastProvider } from "@/components/feedback"
import { Card, Skeleton } from "@/components/ui"
import { OverviewPage } from "@/pages/Overview"
import { ScannerManagementPage } from "@/pages/ScannerManagement"
import { ScannerDetailPage } from "@/pages/ScannerDetail"
import { UploadScannerPage } from "@/pages/UploadScanner"
import { AlertsPage } from "@/pages/Alerts"
import { UploadHistoryPage } from "@/pages/UploadHistory"
import { SystemMonitorPage } from "@/pages/SystemMonitor"
import { SettingsPage } from "@/pages/Settings"
import { SetupPage } from "@/pages/Setup"
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

export default function App() {
  const data = useAppData()
  const route = useRoute()
  const preview = usePreview()
  const [range, setRange] = useState<Range>("all")
  const [menuOpen, setMenuOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const root = route.segments[0] ?? "overview"

  /* Setup gate: an unconfigured engine opens the wizard first. */
  useEffect(() => {
    if (!data.setup?.available) return
    if (!data.setup.complete && root !== "setup") route.navigate("/setup", { replace: true })
  }, [data.setup, root, route])

  useEffect(() => {
    const title = TITLES[root] ?? "ASTA"
    document.title = `${title} · ASTA`
  }, [root])

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
        overrides: preview.enabledOverrides,
      }),
    [data.setup, data.config, data.system, data.dataset, preview.enabledOverrides],
  )

  const engineStatus = data.health ? (scanners.some((row) => row.health === "error") ? "warning" : "running") : "stopped"
  const engineLabel = data.health ? (engineStatus === "warning" ? "Degraded" : "Running") : "Offline"

  const title =
    root === "scanners" && route.segments[1]
      ? scanners.find((row) => row.id.toLowerCase() === route.segments[1].toLowerCase())?.name ??
        "Scanner detail"
      : TITLES[root] ?? "ASTA"

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
          />

          <main className="min-w-0 flex-1 px-3 pb-8 pt-4 sm:px-5">
            {data.loading && !data.dataset && !data.setup ? (
              <ShellSkeleton />
            ) : (
              <>
                {root === "overview" ? (
                  <OverviewPage data={data} range={range} onRange={setRange} dataset={data.dataset} />
                ) : null}
                {root === "system" ? <SystemMonitorPage data={data} navigate={route.navigate} /> : null}
                {root === "scanners" && !route.segments[1] ? (
                  <ScannerManagementPage data={data} navigate={route.navigate} />
                ) : null}
                {root === "scanners" && route.segments[1] ? (
                  <ScannerDetailPage
                    data={data}
                    scannerId={route.segments[1]}
                    navigate={route.navigate}
                  />
                ) : null}
                {root === "upload" ? <UploadScannerPage data={data} navigate={route.navigate} /> : null}
                {root === "history" ? <SignalsPage data={data} range={range} onRange={setRange} /> : null}
                {root === "uploads" ? <UploadHistoryPage data={data} navigate={route.navigate} /> : null}
                {root === "alerts" ? <AlertsPage data={data} /> : null}
                {root === "settings" ? <SettingsPage data={data} navigate={route.navigate} /> : null}
                {root === "setup" ? <SetupPage data={data} navigate={route.navigate} /> : null}
                {!TITLES[root] ? <NotFound onHome={() => route.navigate("/overview")} /> : null}
              </>
            )}
          </main>

          <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-3 text-[10px] text-faint sm:px-5">
            <span className="inline-flex items-center gap-1.5">
              <CircleDot className="h-2.5 w-2.5 text-up" />
              ASTA v0.1 · signal engine · dashboard reads data/history/asta.db read-only
            </span>
            <span className="tabnum">
              {data.dataset?.meta.total.toLocaleString() ?? "—"} signals ·{" "}
              {data.dataset?.meta.closed.toLocaleString() ?? "—"} closed · snapshot{" "}
              {data.snapshotAt ? new Date(data.snapshotAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
            </span>
          </footer>
        </div>
      </div>
    </ToastProvider>
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
