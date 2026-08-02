import { Link, Outlet } from "react-router-dom"
import { ApiKeyDialog } from "@/components/settings/api-key-dialog"
import { NewTaskDialog } from "@/components/tasks/new-task-dialog"
import { ThemeToggle } from "@/components/layout/theme-toggle"

export function AppShell() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-background">
        <div className="mx-auto flex h-14 w-full max-w-screen-2xl items-center justify-between px-6">
          <Link to="/" className="font-display text-sm font-bold tracking-[0.2em] uppercase">
            Tasbir
          </Link>
          <div className="flex items-center gap-2">
            <ApiKeyDialog />
            <ThemeToggle />
            <NewTaskDialog />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-screen-2xl flex-1 px-6 py-6">
        <Outlet />
      </main>
    </div>
  )
}
