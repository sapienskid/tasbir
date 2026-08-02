import { lazy, Suspense, useEffect } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { ApiKeyPrompt } from "@/components/settings/api-key-prompt"
import { Toaster } from "@/components/ui/sonner"
import { ThemeProvider } from "@/lib/theme"
import { loadPlatforms } from "@/lib/platforms"

// Route-level code splitting: every page ships in its own chunk so the shell
// and dashboard paint without pulling in page-specific code.
const TaskListPage = lazy(() =>
  import("@/pages/task-list").then((m) => ({ default: m.TaskListPage }))
)
const TaskDetailPage = lazy(() => import("@/pages/task-detail"))
const NewTaskPage = lazy(() => import("@/pages/new-task"))
const TemplatesPage = lazy(() => import("@/pages/templates"))
const DesignSystemsPage = lazy(() => import("@/pages/design-systems"))
const AgentsPage = lazy(() =>
  import("@/pages/agents").then((m) => ({ default: m.AgentsPage }))
)
const SettingsPage = lazy(() => import("@/pages/settings"))

function FullPageSkeleton() {
  return (
    <div className="grid gap-4">
      <div className="h-8 w-1/3 animate-pulse rounded-md bg-muted" />
      <div className="h-96 animate-pulse rounded-md border bg-muted/30" />
    </div>
  )
}

export default function App() {
  // Warm the DB-backed platform dimension cache on boot.
  useEffect(() => {
    void loadPlatforms().catch(() => {})
  }, [])

  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route
              index
              element={
                <Suspense fallback={<FullPageSkeleton />}>
                  <TaskListPage />
                </Suspense>
              }
            />
            <Route
              path="tasks/:taskId"
              element={
                <Suspense fallback={<FullPageSkeleton />}>
                  <TaskDetailPage />
                </Suspense>
              }
            />
            <Route
              path="new"
              element={
                <Suspense fallback={<FullPageSkeleton />}>
                  <NewTaskPage />
                </Suspense>
              }
            />
            <Route
              path="templates"
              element={
                <Suspense fallback={<FullPageSkeleton />}>
                  <TemplatesPage />
                </Suspense>
              }
            />
            <Route
              path="design-systems"
              element={
                <Suspense fallback={<FullPageSkeleton />}>
                  <DesignSystemsPage />
                </Suspense>
              }
            />
            <Route
              path="agents"
              element={
                <Suspense fallback={<FullPageSkeleton />}>
                  <AgentsPage />
                </Suspense>
              }
            />
            <Route
              path="settings"
              element={
                <Suspense fallback={<FullPageSkeleton />}>
                  <SettingsPage />
                </Suspense>
              }
            />
          </Route>
        </Routes>
        <Toaster richColors position="top-right" />
        <ApiKeyPrompt />
      </BrowserRouter>
    </ThemeProvider>
  )
}
