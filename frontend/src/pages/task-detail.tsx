import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { StatusBadge } from "@/components/tasks/status-badge"
import { SaveTemplateDialog } from "@/components/tasks/save-template-dialog"
import { GalleryView } from "@/components/tasks/artifact-gallery"
import { FormatEditor } from "@/components/tasks/format-editor"
import { formatDims } from "@/lib/platforms"
import { ArrowLeft, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { useTask, useTaskProgress } from "@/hooks/use-task"
import { apiRequest, ApiError, fetchBlob, fetchText, downloadBlob } from "@/lib/api"
import { formatLabel, StepDot } from "@/components/tasks/format-utils"

export default function TaskDetailPage() {
  const { taskId = "" } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const { task, files, error, isLoading, mutate } = useTask(taskId)

  const [view, setView] = useState<"gallery" | "edit">("gallery")
  const [selectedFormat, setSelectedFormat] = useState<string | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [templateOpen, setTemplateOpen] = useState(false)

  // Per-format caches so gallery↔editor switches never re-fetch or consume
  // files twice, and edits survive leaving the editor. HTML content lives in a
  // ref (the editor holds it as state); thumbnail URLs live in state so the
  // gallery re-renders as renders finish loading.
  const draftsRef = useRef(new Map<string, string>())
  const inflightRef = useRef(new Set<string>())
  const [pngUrls, setPngUrls] = useState<Record<string, string>>({})
  const [htmls, setHtmls] = useState<Record<string, string>>({})
  const pngUrlsRef = useRef(pngUrls)
  useEffect(() => {
    pngUrlsRef.current = pngUrls
  }, [pngUrls])
  // Mirror the latest task so `prefetchFormat` stays stable across SWR polls.
  const taskRef = useRef(task)
  useEffect(() => {
    taskRef.current = task
  }, [task])

  // Hooks must run before the early returns below.
  const running = task?.status === "pending" || task?.status === "running"
  const { data: progress } = useTaskProgress(taskId, running)

  const formats = useMemo(() => {
    const fromResult = Object.keys(task?.result?.platforms ?? {})
    const fromFiles = files.map((f) => f.format)
    return [...new Set([...fromResult, ...fromFiles])]
  }, [task, files])

  // Fetch (or resolve from cache) a format's HTML + PNG. DB-persisted edited
  // HTML wins over files. Results are committed to state so the gallery
  // re-renders as each render finishes loading.
  const prefetchFormat = useCallback(
    async (fmt: string): Promise<string> => {
      const cached = draftsRef.current.get(fmt)
      if (cached !== undefined) return cached
      if (inflightRef.current.has(fmt)) return ""
      const htmlFile = files.find((f) => f.format === fmt && f.ext === "html")
      const pngFile = files.find((f) => f.format === fmt && f.ext === "png")
      if (!htmlFile && !pngFile) return ""
      const dbHtml = taskRef.current?.edited_html?.[fmt]
      inflightRef.current.add(fmt)
      try {
        const html =
          dbHtml !== undefined
            ? dbHtml
            : htmlFile
              ? await fetchText(`/tasks/${taskId}/files/${htmlFile.filename}`).catch(() => "")
              : ""
        draftsRef.current.set(fmt, html)
        setHtmls((prev) => (prev[fmt] === html ? prev : { ...prev, [fmt]: html }))
        if (pngFile) {
          try {
            const blob = await fetchBlob(`/tasks/${taskId}/files/${pngFile.filename}`)
            const url = URL.createObjectURL(blob)
            setPngUrls((prev) => {
              const old = prev[fmt]
              if (old && old !== url && old.startsWith("blob:")) URL.revokeObjectURL(old)
              return { ...prev, [fmt]: url }
            })
          } catch {
            /* PNG is optional — the gallery falls back to HTML */
          }
        }
        return html
      } finally {
        inflightRef.current.delete(fmt)
      }
    },
    [files, taskId]
  )

  const pngUrlFor = useCallback((fmt: string) => pngUrls[fmt], [pngUrls])
  const htmlFor = useCallback((fmt: string) => htmls[fmt], [htmls])

  const cachePng = useCallback((fmt: string, dataUri: string) => {
    setPngUrls((prev) => {
      const old = prev[fmt]
      if (old && old !== dataUri && old.startsWith("blob:")) URL.revokeObjectURL(old)
      return { ...prev, [fmt]: dataUri }
    })
  }, [])

  const cacheHtml = useCallback((fmt: string, html: string) => {
    draftsRef.current.set(fmt, html)
  }, [])

  const openFormat = useCallback((fmt: string) => {
    setSelectedFormat(fmt)
    setView("edit")
  }, [])

  const downloadAll = useCallback(async () => {
    try {
      const blob = await fetchBlob(`/tasks/${taskId}/files/archive`)
      downloadBlob(blob, `${taskId}.zip`)
      toast.success("All assets downloaded")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Archive download failed")
    }
  }, [taskId])

  const deleteTask = useCallback(async () => {
    try {
      await apiRequest(`/tasks/${taskId}`, { method: "DELETE" })
      toast.success("Task deleted")
      navigate("/")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed")
    }
  }, [taskId, navigate])

  // Revoke prefetched object URLs on unmount.
  useEffect(() => {
    return () => {
      for (const url of Object.values(pngUrlsRef.current)) {
        if (url.startsWith("blob:")) URL.revokeObjectURL(url)
      }
    }
  }, [])

  if (isLoading && !task) {
    return <p className="text-sm text-muted-foreground">Loading task…</p>
  }

  if (error || !task) {
    return (
      <div className="rounded-md border border-destructive/50 p-4 text-sm text-destructive">
        {error instanceof ApiError && error.status === 401
          ? "Authentication required — set your API key in the header."
          : error?.message ?? "Task not found."}
      </div>
    )
  }

  const dims = formatDims(selectedFormat ?? "")

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="icon" aria-label="Back">
            <Link to="/">
              <ArrowLeft aria-hidden="true" className="size-4" />
            </Link>
          </Button>
          <div className="grid gap-0.5">
            <h1 className="text-xl font-semibold truncate max-w-xl">
              {(task.source_data as { title?: string })?.title || task.id}
            </h1>
            <span className="text-xs text-muted-foreground">{task.id}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={task.status} />
          <Button variant="ghost" size="icon" aria-label="Delete task" onClick={() => setDeleteOpen(true)}>
            <Trash2 aria-hidden="true" className="size-4" />
          </Button>
        </div>
      </div>

      {task.status === "failed" ? (
        <div className="rounded-md border border-destructive/50 p-4 text-sm text-destructive">
          {task.error ?? "Task failed"}
        </div>
      ) : null}

      {running ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Pipeline running</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Progress value={progress?.pct ?? 10} />
            <p className="text-sm text-muted-foreground">
              {progress?.node ?? "Analyzing content…"}
              {progress && progress.total > 0
                ? ` · ${progress.done}/${progress.total} formats verified`
                : ""}
            </p>
            {progress && progress.total > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(progress.per_format).map(([fmt, v]) => (
                  <span
                    key={fmt}
                    className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs"
                  >
                    <StepDot status={v.status} />
                    {formatLabel(fmt)}
                    <span className="text-muted-foreground">{v.step ?? v.status}</span>
                  </span>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : view === "gallery" ? (
        <GalleryView
          task={task}
          formats={formats}
          pngUrlFor={pngUrlFor}
          htmlFor={htmlFor}
          prefetch={(fmt) => prefetchFormat(fmt)}
          onOpenFormat={openFormat}
          onDownloadZip={() => void downloadAll()}
        />
      ) : selectedFormat ? (
        <FormatEditor
          task={task}
          taskId={taskId}
          format={selectedFormat}
          dims={{ width: dims.width, height: dims.height }}
          prefetchFormat={prefetchFormat}
          pngUrlFor={pngUrlFor}
          cachePng={cachePng}
          cacheHtml={cacheHtml}
          onBack={() => setView("gallery")}
          onSaveTemplate={() => setTemplateOpen(true)}
          onMutate={() => void mutate()}
        />
      ) : null}

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this task?</AlertDialogTitle>
            <AlertDialogDescription>
              Removes the task record and its generated files from the server.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void deleteTask()}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <SaveTemplateDialog
        taskId={taskId}
        format={selectedFormat ?? ""}
        sourceTemplateId={task?.result?.platforms?.[selectedFormat ?? ""]?.template_id}
        open={templateOpen}
        onOpenChange={setTemplateOpen}
      />
    </div>
  )
}
