import { useCallback, useEffect, useState } from "react"

/* ================================================================== *
 * Hash routing — no dependency, works with the SPA fallback in
 * asta.web.server (unknown paths return index.html).
 * ================================================================== */

export function useRoute(): {
  path: string
  segments: string[]
  navigate: (to: string, options?: { replace?: boolean }) => void
} {
  const [path, setPath] = useState(() => normalize(window.location.hash))

  useEffect(() => {
    const onChange = () => setPath(normalize(window.location.hash))
    window.addEventListener("hashchange", onChange)
    return () => window.removeEventListener("hashchange", onChange)
  }, [])

  const navigate = useCallback((to: string, options?: { replace?: boolean }) => {
    const target = `#${to.startsWith("/") ? to : `/${to}`}`
    if (window.location.hash === target) return
    if (options?.replace) {
      window.history.replaceState(null, "", target)
      setPath(normalize(target))
    } else {
      window.location.hash = target
    }
    window.scrollTo({ top: 0 })
  }, [])

  const segments = path.split("/").filter(Boolean)
  return { path, segments, navigate }
}

function normalize(hash: string): string {
  const raw = (hash || "").replace(/^#/, "")
  if (!raw || raw === "/") return "/overview"
  return raw.startsWith("/") ? raw : `/${raw}`
}
