import { createContext, useCallback, useContext, useEffect, useState } from "react"
import type { ReactNode } from "react"

export type Theme = "light" | "dark" | "system"

const STORAGE_KEY = "tasbir:theme:v1"

interface ThemeContextValue {
  theme: Theme
  resolved: "light" | "dark"
  setTheme: (t: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "system",
  resolved: "light",
  setTheme: () => {},
})

function resolveTheme(t: Theme): "light" | "dark" {
  if (t === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
  }
  return t
}

function applyTheme(t: Theme): "light" | "dark" {
  const resolved = resolveTheme(t)
  document.documentElement.classList.toggle("dark", resolved === "dark")
  return resolved
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    try {
      return (localStorage.getItem(STORAGE_KEY) as Theme) || "system"
    } catch {
      return "system"
    }
  })
  const [resolved, setResolved] = useState<"light" | "dark">(() => applyTheme(theme))

  useEffect(() => {
    setResolved(applyTheme(theme))
  }, [theme])

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const onChange = () => {
      if (theme === "system") setResolved(applyTheme("system"))
    }
    mq.addEventListener("change", onChange)
    return () => mq.removeEventListener("change", onChange)
  }, [theme])

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t)
    try {
      localStorage.setItem(STORAGE_KEY, t)
    } catch {
      /* noop */
    }
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme }}>{children}</ThemeContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  return useContext(ThemeContext)
}
