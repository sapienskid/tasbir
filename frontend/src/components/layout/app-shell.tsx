import { Link, Outlet, useLocation } from "react-router-dom"
import { ApiKeyDialog } from "@/components/settings/api-key-dialog"
import { ThemeToggle } from "@/components/layout/theme-toggle"
import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"

const NAV = [
  { to: "/", label: "Tasks", match: /^\/$/ },
  { to: "/templates", label: "Templates", match: /^\/templates/ },
  { to: "/design-systems", label: "Design Systems", match: /^\/design-systems/ },
]

export function AppShell() {
  const { pathname } = useLocation()
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-background">
        <div className="mx-auto flex h-14 w-full max-w-screen-2xl items-center justify-between px-6">
          <div className="flex items-center gap-6">
            <Link to="/" className="font-display text-sm font-bold tracking-[0.2em] uppercase">
              Tasbir
            </Link>
            <nav className="hidden items-center gap-1 sm:flex">
              {NAV.map((item) => (
                <Button
                  key={item.to}
                  asChild
                  variant="ghost"
                  size="sm"
                  className={item.match.test(pathname) ? "bg-muted" : ""}
                >
                  <Link to={item.to}>{item.label}</Link>
                </Button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <ApiKeyDialog />
            <ThemeToggle />
            <Button asChild size="sm">
              <Link to="/new">
                <Plus className="size-4" />
                New Task
              </Link>
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-screen-2xl flex-1 px-6 py-6">
        <Outlet />
      </main>
    </div>
  )
}
