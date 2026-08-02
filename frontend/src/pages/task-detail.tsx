import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { HtmlEditor } from "@/components/editor/html-editor"
import { PreviewPane } from "@/components/editor/preview-pane"
import { QCReport } from "@/components/editor/qc-report"
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
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { StatusBadge } from "@/components/tasks/status-badge"
import { SaveTemplateDialog } from "@/components/tasks/save-template-dialog"
import { ArrowLeft, Eye, FileCode2, FileImage, FilePlus, RefreshCw, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { useTask } from "@/hooks/use-task"
import {
  apiRequest,
  ApiError,
  downloadBlob,
  fetchBlob,
  fetchText,
  type RerenderResponse,
} from "@/lib/api"

interface QCState {
  score?: number
  issues: string[]
  critique: string
  status?: string
}

export default function TaskDetailPage() {
  const { taskId = "" } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const { task, files, error, isLoading, mutate } = useTask(taskId)

  const [selectedFormat, setSelectedFormat] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [previewSrc, setPreviewSrc] = useState<string | undefined>(undefined)
  const [qc, setQc] = useState<QCState | null>(null)
  const [rerendering, setRerendering] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [templateOpen, setTemplateOpen] = useState(false)

  // Per-format caches so tab switches don't lose edits or consume files twice.
  const draftsRef = useRef(new Map<string, string>())
  const pngRef = useRef(new Map<string, string>())
  // Mirror the latest task so `loadFormat` stays stable across SWR polls
  // (the polling object identity would otherwise re-run the effect every tick).
  const taskRef = useRef(task)
  useEffect(() => {
    taskRef.current = task
  }, [task])

  const [, startTransition] = useTransition()

  const formats = useMemo(() => {
    const fromResult = Object.keys(task?.result?.platforms ?? {})
    const fromFiles = files.map((f) => f.format)
    return [...new Set([...fromResult, ...fromFiles])]
  }, [task, files])

  const platform = selectedFormat ? task?.result?.platforms?.[selectedFormat] : undefined

  useEffect(() => {
    if (formats.length > 0 && !formats.includes(selectedFormat ?? "")) {
      setSelectedFormat(formats[0])
    }
  }, [formats, selectedFormat])

  const loadFormat = useCallback(
    async (fmt: string) => {
      const cachedHtml = draftsRef.current.get(fmt)
      const cachedPng = pngRef.current.get(fmt)
      const htmlFile = files.find((f) => f.format === fmt && f.ext === "html")
      const pngFile = files.find((f) => f.format === fmt && f.ext === "png")

      // Fetch HTML and PNG in parallel — no serial waterfall.
      const [html, previewSrc] = await Promise.all([
        cachedHtml !== undefined
          ? Promise.resolve(cachedHtml)
          : htmlFile
            ? fetchText(`/tasks/${taskId}/files/${htmlFile.filename}`)
                .then((t) => {
                  draftsRef.current.set(fmt, t)
                  return t
                })
                .catch(() => "")
            : Promise.resolve(""),
        cachedPng !== undefined
          ? Promise.resolve(cachedPng)
          : pngFile
            ? fetchBlob(`/tasks/${taskId}/files/${pngFile.filename}`)
                .then((blob) => {
                  const url = URL.createObjectURL(blob)
                  pngRef.current.set(fmt, url)
                  return url
                })
                .catch(() => undefined)
            : Promise.resolve(undefined),
      ])

      setDraft(html)
      setPreviewSrc(previewSrc)

      const platform = taskRef.current?.result?.platforms?.[fmt]
      setQc(
        platform
          ? {
              score: platform.quality_score,
              issues: platform.quality_issues ?? [],
              critique: "",
              status: platform.status,
            }
          : null
      )
    },
    [files, taskId]
  )

  useEffect(() => {
    if (selectedFormat) void loadFormat(selectedFormat)
  }, [selectedFormat, loadFormat])

  useEffect(() => {
    return () => {
      pngRef.current.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [])

  const handleRerender = useCallback(
    async (audit: boolean) => {
      if (!selectedFormat) return
      setRerendering(true)
      try {
        const res = await apiRequest<RerenderResponse>(
          `/tasks/${taskId}/formats/${selectedFormat}/rerender${audit ? "?audit=true" : ""}`,
          { method: "POST", body: JSON.stringify({ html: draft }) }
        )
        const dataUri = `data:image/png;base64,${res.png_b64}`
        setPreviewSrc(dataUri)
        pngRef.current.set(selectedFormat, dataUri)
        draftsRef.current.set(selectedFormat, draft)
        setQc({
          score: res.quality.score,
          issues: res.quality.issues,
          critique: res.quality.critique,
          status: res.pass ? "verified" : "needs_review",
        })
        toast.success(audit ? "Audit complete" : "Re-rendered")
        void mutate()
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Re-render failed")
      } finally {
        setRerendering(false)
      }
    },
    [selectedFormat, taskId, draft, mutate]
  )

  const downloadPng = useCallback(() => {
    if (!selectedFormat) return
    const src = previewSrc
    if (src?.startsWith("data:")) {
      const a = document.createElement("a")
      a.href = src
      a.download = `${selectedFormat}.png`
      a.click()
      return
    }
    const file = files.find((f) => f.format === selectedFormat && f.ext === "png")
    if (!file) {
      toast.error("No PNG available — render this format first")
      return
    }
    void (async () => {
      try {
        const blob = await fetchBlob(`/tasks/${taskId}/files/${file.filename}`)
        downloadBlob(blob, file.filename)
        void mutate()
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Download failed")
      }
    })()
  }, [selectedFormat, previewSrc, files, taskId, mutate])

  const downloadHtml = useCallback(() => {
    if (!selectedFormat) return
    const cached = draftsRef.current.get(selectedFormat)
    if (cached !== undefined) {
      downloadBlob(new Blob([cached], { type: "text/html" }), `${selectedFormat}.html`)
      return
    }
    const file = files.find((f) => f.format === selectedFormat && f.ext === "html")
    if (!file) {
      toast.error("No HTML available")
      return
    }
    void (async () => {
      try {
        const text = await fetchText(`/tasks/${taskId}/files/${file.filename}`)
        downloadBlob(new Blob([text], { type: "text/html" }), file.filename)
        void mutate()
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Download failed")
      }
    })()
  }, [selectedFormat, files, taskId, mutate])

  const deleteTask = useCallback(async () => {
    try {
      await apiRequest(`/tasks/${taskId}`, { method: "DELETE" })
      toast.success("Task deleted")
      navigate("/")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed")
    }
  }, [taskId, navigate])

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

  const running = task.status === "pending" || task.status === "running"

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="icon" aria-label="Back">
            <Link to="/">
              <ArrowLeft className="size-4" />
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
            <Trash2 className="size-4" />
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
          <CardContent>
            <Progress value={45} />
            <p className="mt-2 text-sm text-muted-foreground">Rendering & verifying…</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex items-center justify-between gap-2">
            <Tabs
              value={selectedFormat ?? undefined}
              onValueChange={(v) => startTransition(() => setSelectedFormat(v))}
            >
              <TabsList className="flex-wrap">
                {formats.map((fmt) => (
                  <TabsTrigger key={fmt} value={fmt}>
                    {fmt}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <div className="flex items-center gap-2">
              {platform?.template_id ? (
                <Badge variant="outline" className="font-mono text-xs">
                  {platform.template_id}
                </Badge>
              ) : null}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setTemplateOpen(true)}
                disabled={!selectedFormat}
              >
                <FilePlus className="size-4" />
                Save as Template
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleRerender(false)}
                disabled={rerendering || !selectedFormat}
              >
                <RefreshCw className={rerendering ? "size-4 animate-spin" : "size-4"} />
                Re-render
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleRerender(true)} disabled={rerendering || !selectedFormat}>
                <Eye className="size-4" />
                Audit
              </Button>
              <Button variant="outline" size="sm" onClick={downloadPng} disabled={!selectedFormat}>
                <FileImage className="size-4" />
                PNG
              </Button>
              <Button variant="outline" size="sm" onClick={downloadHtml} disabled={!selectedFormat}>
                <FileCode2 className="size-4" />
                HTML
              </Button>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="grid gap-4">
              <div className="h-[65vh] overflow-hidden rounded-md border">
                <HtmlEditor value={draft} onChange={setDraft} />
              </div>
            </div>
            <div className="grid gap-4">
              <div className="h-[45vh]">
                <PreviewPane src={previewSrc} loading={rerendering} width={1080} height={1080} />
              </div>
              <QCReport
                score={qc?.score}
                issues={qc?.issues}
                critique={qc?.critique}
                status={qc?.status}
              />
            </div>
          </div>
        </>
      )}

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
        sourceTemplateId={platform?.template_id}
        open={templateOpen}
        onOpenChange={setTemplateOpen}
      />
    </div>
  )
}
