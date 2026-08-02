import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { HtmlEditor } from "@/components/editor/html-editor"
import { VisualEditor, type VisualEditorHandle } from "@/components/editor/visual-editor"
import { useDebouncedValue } from "@/components/editor/use-debounce"
import { ZoomableFrame, formatDims, type PreviewZoomHandle } from "@/components/tasks/preview-frame"
import { InspectorRail, type QcState } from "@/components/tasks/inspector-rail"
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { StatusBadge } from "@/components/tasks/status-badge"
import { SaveTemplateDialog } from "@/components/tasks/save-template-dialog"
import {
  ArrowLeft,
  Archive,
  ChevronDown,
  FileCode2,
  FileImage,
  FilePlus,
  PanelRight,
  Save,
  Trash2,
} from "lucide-react"
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

export default function TaskDetailPage() {
  const { taskId = "" } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const { task, files, error, isLoading, mutate } = useTask(taskId)

  const [selectedFormat, setSelectedFormat] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [qc, setQc] = useState<QcState | null>(null)
  const [rerendering, setRerendering] = useState(false)
  const [mode, setMode] = useState<"code" | "visual">("code")
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [templateOpen, setTemplateOpen] = useState(false)

  const visualEditorRef = useRef<VisualEditorHandle>(null)
  const previewFrameRef = useRef<PreviewZoomHandle>(null)

  // Ctrl/Cmd ± / 0 and Ctrl+wheel zoom the editing surface (visual canvas or
  // live preview), never the browser page. Capture phase on the parent
  // document as the outer net; the GrapesJS frame attaches its own handlers
  // and tags the event (__tasbirZoomHandled) so we don't zoom twice.
  useEffect(() => {
    const applyZoom = (dir: "in" | "out" | "fit") => {
      if (mode === "visual") {
        if (dir === "fit") visualEditorRef.current?.zoomToFit()
        else visualEditorRef.current?.zoomBy(dir === "out" ? 1 / 1.2 : 1.2)
      } else {
        if (dir === "fit") previewFrameRef.current?.fit()
        else previewFrameRef.current?.zoomBy(dir === "out" ? 1 / 1.25 : 1.25)
      }
    }
    const alreadyHandled = (e: Event) =>
      (e as unknown as { __tasbirZoomHandled?: boolean }).__tasbirZoomHandled === true

    const onKeyDown = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return
      const k = e.key.toLowerCase()
      let dir: "in" | "out" | "fit" | null = null
      if (k === "-") dir = "out"
      else if (k === "+" || k === "=") dir = "in"
      else if (k === "0") dir = "fit"
      else return
      e.preventDefault()
      if (alreadyHandled(e)) return
      applyZoom(dir)
    }
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return
      e.preventDefault()
      if (alreadyHandled(e)) return
      applyZoom(e.deltaY > 0 ? "out" : "in")
    }

    document.addEventListener("keydown", onKeyDown, true)
    document.addEventListener("wheel", onWheel, { passive: false, capture: true })
    return () => {
      document.removeEventListener("keydown", onKeyDown, true)
      document.removeEventListener("wheel", onWheel, { capture: true })
    }
  }, [mode])

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
  const dims = formatDims(selectedFormat ?? "")
  const livePreviewHtml = useDebouncedValue(draft, 300)
  const hasQcIssues = Boolean(qc && (qc.issues.length > 0 || (qc.score ?? 100) < 100))

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
      const [html] = await Promise.all([
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
    async (audit: boolean, htmlOverride?: string) => {
      if (!selectedFormat) return
      let html = htmlOverride
      // In visual mode the live canvas is the source of truth — capture it so
      // Save/Audit never persist a stale draft (the user may not have hit
      // "Apply to editor" yet).
      if (html === undefined && mode === "visual") {
        html = visualEditorRef.current?.exportHtml() ?? undefined
      }
      if (html === undefined) html = draft
      setRerendering(true)
      try {
        const res = await apiRequest<RerenderResponse>(
          `/tasks/${taskId}/formats/${selectedFormat}/rerender${audit ? "?audit=true" : ""}`,
          { method: "POST", body: JSON.stringify({ html }) }
        )
        const dataUri = `data:image/png;base64,${res.png_b64}`
        pngRef.current.set(selectedFormat, dataUri)
        draftsRef.current.set(selectedFormat, html)
        // Keep the editor/preview in sync with what was actually saved.
        if (html !== draft) {
          setDraft(html)
        }
        setQc({
          score: res.quality.score,
          issues: res.quality.issues,
          critique: res.quality.critique,
          status: res.pass ? "verified" : "needs_review",
        })
        toast.success(res.pass ? "Saved & rendered" : "Saved — review the issues")
        void mutate()
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Re-render failed")
      } finally {
        setRerendering(false)
      }
    },
    [selectedFormat, taskId, draft, mutate, mode]
  )

  const applyHtml = useCallback((html: string) => {
    if (!selectedFormat) return
    setDraft(html)
    draftsRef.current.set(selectedFormat, html)
    toast.success("Applied to editor")
  }, [selectedFormat])

  const applyAndRender = useCallback(
    async (html: string) => {
      if (!selectedFormat) return
      applyHtml(html)
      await handleRerender(false, html)
    },
    [selectedFormat, applyHtml, handleRerender]
  )

  const downloadPng = useCallback(() => {
    if (!selectedFormat) return
    const file = files.find((f) => f.format === selectedFormat && f.ext === "png")
    if (!file) {
      toast.error("No PNG available — render this format first")
      return
    }
    void (async () => {
      try {
        const blob = await fetchBlob(`/tasks/${taskId}/files/${file.filename}`)
        downloadBlob(blob, file.filename)
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Download failed")
      }
    })()
  }, [selectedFormat, files, taskId])

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
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Download failed")
      }
    })()
  }, [selectedFormat, files, taskId])

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
            <div className="flex flex-wrap items-center gap-2">
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
                Template
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" disabled={!selectedFormat}>
                    <Archive className="size-4" />
                    Download
                    <ChevronDown className="size-3.5 opacity-70" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52">
                  <DropdownMenuItem onClick={downloadPng} disabled={!selectedFormat}>
                    <FileImage className="size-4" />
                    PNG
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={downloadHtml} disabled={!selectedFormat}>
                    <FileCode2 className="size-4" />
                    HTML
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => void downloadAll()} disabled={!selectedFormat}>
                    <Archive className="size-4" />
                    All assets (ZIP)
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                size="sm"
                onClick={() => void handleRerender(false)}
                disabled={rerendering || !selectedFormat}
              >
                <Save className="size-4" />
                {rerendering ? "Saving…" : "Save & Render"}
              </Button>
              <Button
                variant={inspectorOpen ? "default" : "outline"}
                size="sm"
                onClick={() => setInspectorOpen((o) => !o)}
                disabled={!selectedFormat}
              >
                <PanelRight className="size-4" />
                Chat
                {hasQcIssues && !inspectorOpen ? (
                  <span className="ml-1 inline-block size-1.5 rounded-full bg-destructive" />
                ) : null}
              </Button>
            </div>
          </div>

          <div className="flex items-stretch gap-4">
            <div className="grid min-w-0 flex-1 gap-4 lg:grid-cols-2">
              <div className="grid gap-2">
                <div className="flex items-center gap-1">
                  <Button
                    variant={mode === "code" ? "default" : "outline"}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setMode("code")}
                  >
                    <FileCode2 className="size-3.5" />
                    Code
                  </Button>
                  <Button
                    variant={mode === "visual" ? "default" : "outline"}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setMode("visual")}
                  >
                    Visual
                  </Button>
                </div>
                <div className="h-[65vh] overflow-hidden rounded-md border">
                  {mode === "code" ? (
                    <HtmlEditor value={draft} onChange={setDraft} />
                  ) : (
                    <VisualEditor
                      ref={visualEditorRef}
                      html={draft}
                      width={dims.width}
                      height={dims.height}
                      onExport={applyHtml}
                    />
                  )}
                </div>
              </div>
              <div className="grid gap-2">
                <p className="text-xs text-muted-foreground">
                  Live preview — updates as you edit ({dims.width}×{dims.height}).
                </p>
                <div className="h-[65vh] overflow-hidden rounded-md border">
                  <ZoomableFrame
                    ref={previewFrameRef}
                    html={livePreviewHtml}
                    width={dims.width}
                    height={dims.height}
                  />
                </div>
              </div>
            </div>

            {inspectorOpen ? (
              <aside className="h-[65vh] w-[360px] shrink-0">
                <InspectorRail
                  onClose={() => setInspectorOpen(false)}
                  qc={qc}
                  taskId={taskId}
                  format={selectedFormat ?? ""}
                  currentHtml={draft}
                  onApplyHtml={applyHtml}
                  onApplyAndRender={applyAndRender}
                  onAudit={() => void handleRerender(true)}
                  auditing={rerendering}
                />
              </aside>
            ) : null}
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
