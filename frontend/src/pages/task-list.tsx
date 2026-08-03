import { useMemo, useState } from "react"
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
import { Badge } from "@/components/ui/badge"
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
import { useAgentJobs } from "@/hooks/use-library"
import { apiRequest, ApiError, deleteAgentJob, type AgentJob } from "@/lib/api"

type Row =
  | { kind: "post"; id: string; title: string; status: string; created_at: string | null }
  | { kind: AgentJob["kind"]; id: string; title: string; status: string; created_at: string | null }

const TYPE_LABEL: Record<Row["kind"], string> = {
  post: "Post",
  template: "Template",
  design_system: "Design system",
}

export function TaskListPage() {
  const { data: tasks, error, isLoading, mutate: mutateTasks } = useTasks()
  const {
    data: jobs,
    error: jobsError,
    isLoading: jobsLoading,
    mutate: mutateJobs,
  } = useAgentJobs()
  const [deleting, setDeleting] = useState<Row | null>(null)
  const navigate = useNavigate()

  const rows: Row[] = useMemo(() => {
    const t: Row[] = (tasks ?? []).map((task) => ({
      kind: "post",
      id: task.id,
      title: task.title || task.id.slice(0, 8),
      status: task.status,
      created_at: task.created_at,
    }))
    const j: Row[] = (jobs ?? []).map((job) => ({
      kind: job.kind,
      id: job.id,
      title: job.title || (job.kind === "template" ? "Template job" : "Brand builder job"),
      status: job.status,
      created_at: job.created_at,
    }))
    return [...t, ...j].sort((a, b) => {
      const at = a.created_at ? new Date(a.created_at).getTime() : 0
      const bt = b.created_at ? new Date(b.created_at).getTime() : 0
      return bt - at
    })
  }, [tasks, jobs])

  function rowHref(r: Row): string {
    return r.kind === "post" ? `/tasks/${r.id}` : `/jobs/${r.id}`
  }

  async function confirmDelete() {
    if (!deleting) return
    try {
      if (deleting.kind === "post") {
        await apiRequest(`/tasks/${deleting.id}`, { method: "DELETE" })
        await mutateTasks()
      } else {
        await deleteAgentJob(deleting.id)
        await mutateJobs()
      }
      toast.success("Deleted")
      setDeleting(null)
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
          Posts, template builders, and brand builder jobs run in the background.
        </span>
      </div>

      {error || jobsError ? (
        <div className="rounded-md border border-destructive/50 p-4 text-sm text-destructive">
          {(error ?? jobsError) instanceof ApiError && (error ?? jobsError)?.status === 401
            ? "Authentication required — open the API Key dialog in the header to set your key."
            : error instanceof Error
              ? error.message
              : jobsError instanceof Error
                ? jobsError.message
                : "Failed to load tasks."}
        </div>
      ) : null}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Title</TableHead>
            <TableHead className="w-28">Type</TableHead>
            <TableHead className="w-32">Status</TableHead>
            <TableHead className="w-44">Created</TableHead>
            <TableHead className="w-28 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading || jobsLoading || !tasks || !jobs
            ? Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-4 w-64" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
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
            : rows.map((row) => (
                <TableRow
                  key={`${row.kind}-${row.id}`}
                  className="cursor-pointer"
                  tabIndex={0}
                  role="link"
                  onClick={() => navigate(rowHref(row))}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      navigate(rowHref(row))
                    }
                  }}
                  onPointerEnter={preloadMonacoEditor}
                >
                  <TableCell className="max-w-xl truncate font-medium">
                    <Link to={rowHref(row)} className="hover:underline">
                      {row.title}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="text-[10px]">
                      {TYPE_LABEL[row.kind]}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={row.status} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {row.created_at ? new Date(row.created_at).toLocaleString() : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete"
                      onClick={(e) => {
                        e.stopPropagation()
                        setDeleting(row)
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
            <AlertDialogTitle>Delete this {deleting ? TYPE_LABEL[deleting.kind] : ""}?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleting?.kind === "post"
                ? "This removes the task record and its generated files from the server."
                : "This removes the job record and its chat thread from the server."}
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