import { useCallback, useEffect, useState } from "react"

/* Light is the product default; the choice is remembered per browser and
 * applied by the inline script in index.html before first paint. */
export type Theme = "light" | "dark"

const STORAGE_KEY = "asta.theme"

function readTheme(): Theme {
  if (typeof document === "undefined") return "light"
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light"
}

function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* storage disabled — the theme still applies for this page view */
  }
}

export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(readTheme)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const toggle = useCallback(() => setTheme((current) => (current === "dark" ? "light" : "dark")), [])

  return { theme, toggle }
}
