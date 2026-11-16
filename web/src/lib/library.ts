import { useEffect, useState } from "react"
import { apiGet, apiSend } from "@/lib/api"

/* ------------------------------------------------------------------ *
 * Scanner library + recycle bin + share + alert delivery log.
 * These read and write the real engine API (no more localStorage preview).
 * ------------------------------------------------------------------ */

export interface LibraryScanner {
  id: string
  scannerId: string
  name: string
  market: string
  version: string
  uploadedAt: string
  status: string
  enabled?: boolean
  sizeBytes: number
  timeframes: string[]
  description: string
  dependencies: string[]
  changes: string[]
  compatibility: string
  sha256?: string
  sourceName?: string
  sourcePath?: string
}

export interface TrashItem extends LibraryScanner {
  deletedAt: string
  deletedReason: string
}

export interface HistoryEvent {
  at: string
  action: string
  scannerId: string
  name?: string
  market?: string
  version?: string
  detail?: string
}

export interface LibraryInfo {
  available: boolean
  installed: LibraryScanner[]
  trash: TrashItem[]
  history: HistoryEvent[]
  root: string
  trashRoot: string
}

export interface AlertEntry {
  at: string
  kind: string
  market?: string
  ok?: boolean
  status?: number | string
  error?: string
  dry_run?: boolean
}

export interface ShareInfo {
  enabled: boolean
  host?: string
  port?: number
  lanIps?: string[]
  editorToken?: string
  viewerToken?: string
  editorUrl?: string
  viewUrl?: string
  note?: string
}

export type Access = "editor" | "viewer"

const EMPTY_LIBRARY: LibraryInfo = {
  available: false,
  installed: [],
  trash: [],
  history: [],
  root: "",
  trashRoot: "",
}

export interface LibraryState {
  library: LibraryInfo
  access: Access
  loading: boolean
  refresh: () => void
}

export function useLibrary(): LibraryState {
  const [library, setLibrary] = useState<LibraryInfo>(EMPTY_LIBRARY)
  const [access, setAccess] = useState<Access>("editor")
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const refresh = () => setTick((n) => n + 1)

  useEffect(() => {
    let alive = true
    const load = () => {
      apiGet<LibraryInfo>("/api/scanners/library")
        .then((next) => {
          if (alive) setLibrary(next)
        })
        .catch(() => undefined)
      apiGet<{ access: Access }>("/api/access")
        .then((next) => {
          if (alive) setAccess(next.access)
        })
        .catch(() => {
          if (alive) setAccess("editor")
        })
        .finally(() => {
          if (alive) setLoading(false)
        })
    }
    load()
    const timer = setInterval(load, 20_000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [tick])

  return { library, access, loading, refresh }
}

export const libraryActions = {
  install(payload: unknown) {
    return apiSend<{ installed: boolean; record: LibraryScanner }>("/api/scanners/install", "POST", payload)
  },
  uninstall(scannerId: string, reason = "") {
    return apiSend<{ uninstalled: boolean; record: TrashItem }>(
      `/api/scanners/${encodeURIComponent(scannerId)}/uninstall`,
      "POST",
      { reason },
    )
  },
  restore(scannerId: string) {
    return apiSend<{ restored: boolean; record: LibraryScanner }>(
      `/api/scanners/${encodeURIComponent(scannerId)}/restore`,
      "POST",
      {},
    )
  },
  purge(scannerId: string) {
    return apiSend<{ purged: boolean }>(`/api/scanners/${encodeURIComponent(scannerId)}/purge`, "POST", {})
  },
  setEnabled(scannerId: string, enabled: boolean) {
    return apiSend<{ enabled: boolean; restartRequired: boolean }>(
      `/api/scanners/${encodeURIComponent(scannerId)}/set-enabled`,
      "POST",
      { enabled },
    )
  },
  testAlert(market?: string) {
    return apiSend<{ results: AlertEntry[] }>("/api/alerts/test", "POST", market ? { market } : {})
  },
  sampleAlert(market?: string) {
    return apiSend<{ results: AlertEntry[] }>("/api/alerts/sample", "POST", market ? { market } : {})
  },
  alertLog() {
    return apiGet<{ entries: AlertEntry[] }>("/api/alerts/log")
  },
  share() {
    return apiGet<ShareInfo>("/api/share")
  },
  regenerateShare() {
    return apiSend<{ tokens: Record<string, string> }>("/api/share/regenerate", "POST", {})
  },
}
