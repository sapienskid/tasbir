import { useCallback, useEffect, useRef, useState } from "react"
import { HtmlEditor } from "@/components/editor/html-editor"
import { VisualEditor, type VisualEditorHandle } from "@/components/editor/visual-editor"
import { useDebouncedValue } from "@/components/editor/use-debounce"
import { ZoomableFrame, type PreviewZoomHandle } from "@/components/tasks/preview-frame"
import { InspectorRail, type QcState } from "@/components/tasks/inspector-rail"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  ArrowLeft,
  Eye,
  FileCode2,
  FileImage,
  MoreVertical,
  PanelRight,
  RefreshCw,
  Save,
} from "lucide-react"
import { toast } from "sonner"
import {
  apiRequest,
  downloadBlob,
  fetchBlob,
  type RerenderResponse,
  type RetryResponse,
  type TaskDetail,
} from "@/lib/api"
import { formatLabel } from "@/components/tasks/format-utils"

type Rail = "preview" | "inspector" | null

/**
 * Full-width editor for a single artifact. The toolbar holds the mode
 * (Code | Visual), the preview/chat rail toggles, Save & Render, and a compact
 * overflow menu (downloads, audit, save-as-template).
 */
export function FormatEditor({
  task,
  taskId,
  format,
  dims,
  prefetchFormat,
  pngUrlFor,
  cachePng,
  cacheHtml,
  onBack,
  onSaveTemplate,
  onMutate,
}: {
  task: TaskDetail
  taskId: string
  format: string
  dims: { width: number; height: number }
  prefetchFormat: (fmt: string) => Promise<string>
  pngUrlFor: (fmt: string) => string | undefined
  cachePng: (fmt: string, dataUri: string) => void
  cacheHtml: (fmt: string, html: string) => void
  onBack: () => void
  onSaveTemplate: () => void
  onMutate: () => void
}) {
  const [draft, setDraft] = useState("")
  const [qc, setQc] = useState<QcState | null>(null)
  const [mode, setMode] = useState<"code" | "visual">("code")
  const [rail, setRail] = useState<Rail>(null)
  const [rerendering, setRerendering] = useState(false)

  const visualEditorRef = useRef<VisualEditorHandle>(null)
  const previewFrameRef = useRef<PreviewZoomHandle>(null)

  const livePreviewHtml = useDebouncedValue(draft, 300)
  const hasQcIssues = Boolean(qc && (qc.issues.length > 0 || (qc.score ?? 100) < 100))

  // Ctrl/Cmd ± / 0 and Ctrl+wheel zoom the editing surface (visual canvas or
  // live preview), never the browser page.
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
    const fromCanvasFrame = (e: Event) => {
      if (mode !== "visual") return false
      const frame = document.querySelector("[data-visual-editor] .gjs-frame")
      return !!frame && e.composedPath().includes(frame)
    }

    const onKeyDown = (e: Event) => {
      const ev = e as KeyboardEvent
      if (!(ev.ctrlKey || ev.metaKey)) return
      const k = ev.key.toLowerCase()
      let dir: "in" | "out" | "fit" | null = null
      if (k === "-") dir = "out"
      else if (k === "+" || k === "=") dir = "in"
      else if (k === "0") dir = "fit"
      else return
      ev.preventDefault()
      if (fromCanvasFrame(e)) return
      const tag = ev as unknown as { __tasbirZoomHandled?: boolean }
      if (tag.__tasbirZoomHandled) return
      tag.__tasbirZoomHandled = true
      applyZoom(dir)
    }
    const onWheel = (e: Event) => {
      const ev = e as WheelEvent
      if (!ev.ctrlKey) return
      ev.preventDefault()
      if (fromCanvasFrame(e)) return
      const tag = ev as unknown as { __tasbirZoomHandled?: boolean }
      if (tag.__tasbirZoomHandled) return
      tag.__tasbirZoomHandled = true
      applyZoom(ev.deltaY > 0 ? "out" : "in")
    }

    for (const target of [window, document]) {
      target.addEventListener("keydown", onKeyDown, true)
      target.addEventListener("wheel", onWheel, { passive: false, capture: true })
    }
    return () => {
      for (const target of [window, document]) {
        target.removeEventListener("keydown", onKeyDown, true)
        target.removeEventListener("wheel", onWheel, { capture: true })
      }
    }
  }, [mode])

  // Load the format into the editor whenever it changes. `loadedFormatRef`
  // guards resets (mode/rail) to actual format switches — re-fetches triggered
  // by a task revalidation must not clobber the user's current mode.
  const loadedFormatRef = useRef<string | null>(null)
  useEffect(() => {
    let cancelled = false
    void (async () => {
      const html = await prefetchFormat(format)
      if (cancelled) return
      setDraft(html)
      if (loadedFormatRef.current !== format) {
        loadedFormatRef.current = format
        setMode("code")
        setRail(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [format, prefetchFormat])

  // Keep QC in sync with the latest task state.
  useEffect(() => {
    const p = task?.result?.platforms?.[format]
    setQc(
      p
        ? { score: p.quality_score, issues: p.quality_issues ?? [], critique: "", status: p.status }
        : null
    )
  }, [task, format])

  const handleRerender = useCallback(
    async (audit: boolean, htmlOverride?: string) => {
      let html = htmlOverride
      if (html === undefined && mode === "visual") {
        html = visualEditorRef.current?.exportHtml() ?? undefined
      }
      if (html === undefined) html = draft
      setRerendering(true)
      try {
        const res = await apiRequest<RerenderResponse>(
          `/tasks/${taskId}/formats/${format}/rerender${audit ? "?audit=true" : ""}`,
          { method: "POST", body: JSON.stringify({ html }) }
        )
        const dataUri = res.png_b64 ? `data:image/png;base64,${res.png_b64}` : undefined
        if (dataUri) cachePng(format, dataUri)
        cacheHtml(format, html)
        if (html !== draft) setDraft(html)
        setQc({
          score: res.quality.score,
          issues: res.quality.issues,
          critique: res.quality.critique,
          status: res.pass ? "verified" : "needs_review",
        })
        toast.success(res.pass ? "Saved & rendered" : "Saved — review the issues")
        onMutate()
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Re-render failed")
      } finally {
        setRerendering(false)
      }
    },
    [format, taskId, draft, mode, cachePng, cacheHtml, onMutate]
  )

  const handleRetry = useCallback(async () => {
    setRerendering(true)
    try {
      const res = await apiRequest<RetryResponse>(
        `/tasks/${taskId}/formats/${format}/retry`,
        { method: "POST" }
      )
      // Refresh the editor with the freshly designed HTML + PNG.
      const fresh = await prefetchFormat(format)
      if (fresh) setDraft(fresh)
      try {
        const png = await fetchBlob(`/tasks/${taskId}/files/${format}.png`)
        if (png) cachePng(format, URL.createObjectURL(png))
      } catch {
        /* PNG may be unavailable — gallery will retry from the file */
      }
      setQc({
        score: res.score,
        issues: res.issues,
        critique: res.critique,
        status: res.pass ? "verified" : "needs_review",
      })
      toast.success(res.pass ? "Retry passed verification" : "Retry done — still has issues")
      onMutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Retry failed")
    } finally {
      setRerendering(false)
    }
  }, [taskId, format, prefetchFormat, cachePng, onMutate])

  const applyHtml = useCallback(
    (html: string) => {
      setDraft(html)
      cacheHtml(format, html)
      toast.success("Applied to editor — click Save & Render to persist")
    },
    [format, cacheHtml]
  )

  const applyAndRender = useCallback(
    async (html: string) => {
      applyHtml(html)
      await handleRerender(false, html)
    },
    [applyHtml, handleRerender]
  )

  const downloadPng = useCallback(() => {
    const cached = pngUrlFor(format)
    if (cached) {
      fetch(cached)
        .then((r) => r.blob())
        .then((blob) => downloadBlob(blob, `${format}.png`))
        .catch(() => toast.error("Download failed"))
      return
    }
    toast.error("No PNG available — render this format first")
  }, [format, pngUrlFor])

  const downloadHtml = useCallback(() => {
    if (draft) {
      downloadBlob(new Blob([draft], { type: "text/html" }), `${format}.html`)
      return
    }
    toast.error("No HTML available")
  }, [draft, format])

  const toggleRail = (which: Exclude<Rail, null>) => {
    setRail((r) => (r === which ? null : which))
  }

  const railBody =
    rail === "preview" ? (
      <div className="flex h-full flex-col overflow-hidden rounded-md border">
        <ZoomableFrame
          ref={previewFrameRef}
          html={livePreviewHtml}
          width={dims.width}
          height={dims.height}
        />
      </div>
    ) : rail === "inspector" ? (
      <InspectorRail
        onClose={() => setRail(null)}
        qc={qc}
        taskId={taskId}
        format={format}
        currentHtml={draft}
        onApplyHtml={applyHtml}
        onApplyAndRender={(html) => void applyAndRender(html)}
        onAudit={() => void handleRerender(true)}
        auditing={rerendering}
      />
    ) : null

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onBack} className="h-7 gap-1 px-2">
            <ArrowLeft aria-hidden="true" className="size-4" />
            All artifacts
          </Button>
          <span className="text-sm font-medium">{formatLabel(format)}</span>
          <span className="text-xs text-muted-foreground">
            {dims.width}×{dims.height}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" aria-label="More options">
                <MoreVertical aria-hidden="true" className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={downloadPng}>
                <FileImage className="size-4" />
                Download PNG
              </DropdownMenuItem>
              <DropdownMenuItem onClick={downloadHtml}>
                <FileCode2 className="size-4" />
                Download HTML
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => void handleRerender(true)}>
                <Eye className="size-4" />
                Run audit
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onSaveTemplate}>
                <FileCode2 className="size-4" />
                Save as template
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void handleRetry()}
            disabled={rerendering}
            title="Re-run the designer LLM with the verifier critique, then re-verify"
          >
            <RefreshCw aria-hidden="true" className="size-4" />
            Retry designer
          </Button>
          <Button
            size="sm"
            onClick={() => void handleRerender(false)}
            disabled={rerendering}
          >
            <Save aria-hidden="true" className="size-4" />
            {rerendering ? "Saving…" : "Save & Render"}
          </Button>
        </div>
      </div>

      <div className="flex items-stretch gap-4">
        <div className="grid min-w-0 flex-1 gap-2">
          <div className="flex items-center justify-between gap-2">
            <Tabs
              value={mode}
              onValueChange={(v) => setMode(v as "code" | "visual")}
            >
              <TabsList className="h-8">
                <TabsTrigger value="code" className="px-3 text-xs">
                  <FileCode2 aria-hidden="true" className="mr-1 size-3.5" />
                  Code
                </TabsTrigger>
                <TabsTrigger value="visual" className="px-3 text-xs">
                  Visual
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="flex items-center gap-2">
              <Button
                variant={rail === "preview" ? "default" : "outline"}
                size="sm"
                className="h-8"
                onClick={() => toggleRail("preview")}
              >
                <Eye aria-hidden="true" className="size-4" />
                Preview
              </Button>
              <Button
                variant={rail === "inspector" ? "default" : "outline"}
                size="sm"
                className="h-8"
                onClick={() => toggleRail("inspector")}
              >
                <PanelRight aria-hidden="true" className="size-4" />
                Chat
                {hasQcIssues && rail !== "inspector" ? (
                  <span className="ml-1 inline-block size-1.5 rounded-full bg-destructive" />
                ) : null}
              </Button>
            </div>
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

        {railBody ? (
          <aside className="h-[65vh] w-[360px] shrink-0">{railBody}</aside>
        ) : null}
      </div>
    </div>
  )
}
