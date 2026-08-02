import { lazy, Suspense } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { Toaster } from "@/components/ui/sonner"
import { TaskListPage } from "@/pages/task-list"
import { ThemeProvider } from "@/lib/theme"

const TaskDetailPage = lazy(() => import("@/pages/task-detail"))

function FullPageSkeleton() {
  return (
    <div className="grid gap-4">
      <div className="h-8 w-1/3 animate-pulse rounded-md bg-muted" />
      <div className="h-96 animate-pulse rounded-md border bg-muted/30" />
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<TaskListPage />} />
            <Route
              path="tasks/:taskId"
              element={
                <Suspense fallback={<FullPageSkeleton />}>
                  <TaskDetailPage />
                </Suspense>
              }
            />
          </Route>
        </Routes>
        <Toaster richColors position="top-right" />
      </BrowserRouter>
    </ThemeProvider>
  )
}
