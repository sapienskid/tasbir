import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusBadge } from "@/components/tasks/status-badge"
import { preloadMonacoEditor } from "@/components/editor/html-editor"
import { Trash2 } from "lucide-react"
import { toast } from "sonner"
import { useTasks } from "@/hooks/use-task"
import { apiRequest, ApiError } from "@/lib/api"

export function TaskListPage() {
  const { data, error, isLoading, mutate } = useTasks()
  const [deleting, setDeleting] = useState<string | null>(null)
  const navigate = useNavigate()

  async function confirmDelete() {
    if (!deleting) return
    try {
      await apiRequest(`/tasks/${deleting}`, { method: "DELETE" })
      toast.success("Task deleted")
      setDeleting(null)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed")
      setDeleting(null)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Tasks</h1>
        <span className="text-sm text-muted-foreground">
          Files auto-expire after the retention window (one-time download).
        </span>
      </div>

      {error ? (
        <div className="rounded-md border border-destructive/50 p-4 text-sm text-destructive">
          {error instanceof ApiError && error.status === 401
            ? "Authentication required — open the API Key dialog in the header to set your key."
            : error.message}
        </div>
      ) : null}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Title</TableHead>
            <TableHead className="w-32">Status</TableHead>
            <TableHead className="w-44">Created</TableHead>
            <TableHead className="w-28 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading || !data
            ? Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-64" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-12" />
                  </TableCell>
                </TableRow>
              ))
            : data.map((task) => (
                <TableRow
                  key={task.id}
                  className="cursor-pointer"
                  tabIndex={0}
                  role="link"
                  onClick={() => navigate(`/tasks/${task.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      navigate(`/tasks/${task.id}`)
                    }
                  }}
                  onPointerEnter={preloadMonacoEditor}
                >
                  <TableCell className="max-w-xl truncate font-medium">
                    <Link to={`/tasks/${task.id}`} className="hover:underline">
                      {task.title || task.id.slice(0, 8)}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={task.status} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {task.created_at ? new Date(task.created_at).toLocaleString() : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete"
                      onClick={(e) => {
                        e.stopPropagation()
                        setDeleting(task.id)
                      }}
                    >
                      <Trash2 aria-hidden="true" className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
        </TableBody>
      </Table>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(o) => !o && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this task?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the task record and its generated files from the server.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
