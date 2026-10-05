import { lazy, useEffect } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { ApiKeyPrompt } from "@/components/settings/api-key-prompt"
import { Toaster } from "@/components/ui/sonner"
import { ThemeProvider } from "@/lib/theme"
import { page } from "@/lib/route-page"
import { loadPlatforms } from "@/lib/platforms"
import { settingsRoutes } from "@/pages/settings/routes"

// Route-level code splitting: every page ships in its own chunk so the shell
// and dashboard paint without pulling in page-specific code.
const TaskListPage = lazy(() =>
  import("@/pages/task-list").then((m) => ({ default: m.TaskListPage }))
)
const TaskDetailPage = lazy(() => import("@/pages/task-detail"))
const JobDetailPage = lazy(() => import("@/pages/job-detail"))
const NewTaskPage = lazy(() => import("@/pages/new-task"))
const ComposePage = lazy(() => import("@/pages/compose"))
const TemplatesPage = lazy(() => import("@/pages/templates"))
const DesignSystemsPage = lazy(() => import("@/pages/design-systems"))
const AgentsPage = lazy(() =>
  import("@/pages/agents").then((m) => ({ default: m.AgentsPage }))
)

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
            <Route index element={page(<TaskListPage />)} />
            <Route path="tasks/:taskId" element={page(<TaskDetailPage />)} />
            <Route path="jobs/:jobId" element={page(<JobDetailPage />)} />
            <Route path="new" element={page(<NewTaskPage />)} />
            <Route path="compose" element={page(<ComposePage />)} />
            <Route path="compose/:batchId" element={page(<ComposePage />)} />
            <Route path="templates" element={page(<TemplatesPage />)} />
            <Route path="design-systems" element={page(<DesignSystemsPage />)} />
            <Route path="agents" element={page(<AgentsPage />)} />
            {/* Settings is a nested layout with one route per section — see
                pages/settings/routes.tsx for the route-tree invariant. */}
            {settingsRoutes}
          </Route>
        </Routes>
        <Toaster richColors position="top-right" />
        <ApiKeyPrompt />
      </BrowserRouter>
    </ThemeProvider>
  )
}
