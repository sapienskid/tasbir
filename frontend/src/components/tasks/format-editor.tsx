import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { HtmlEditor } from "@/components/editor/html-editor"
import { useDebouncedValue } from "@/components/editor/use-debounce"
import { SlotPreview, type SlotPreviewHandle } from "@/components/tasks/slot-preview"
import { StructuredEditor } from "@/components/tasks/structured-editor"
import { parseSlots } from "@/components/tasks/slot-utils"
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
  RefreshCw,
  Save,
} from "lucide-react"
import { toast } from "sonner"
import {
  apiRequest,
  downloadBlob,
  fetchBlob,
  fetchText,
  refillFormat,
  type RefillRequest,
  type RerenderResponse,
  type RetryResponse,
  type TaskDetail,
} from "@/lib/api"
import { usePlatforms } from "@/hooks/use-platforms"
import { platformFamily } from "@/components/compose/model"
import { formatLabel } from "@/components/tasks/format-utils"

/**
 * Agent-post editor, compose-style: structured Content panel on the left,
 * always-live WYSIWYG preview in the center (click any text to edit it in
 * place), agent chat + quality on the right. Raw HTML stays available under
 * the Code tab for posts the designer LLM built freeform — template-built
 * posts never need it.
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
  const [mode, setMode] = useState<"content" | "code">("content")
  const [busy, setBusy] = useState(false)
  const [templateId, setTemplateId] = useState<string | null>(null)

  const previewRef = useRef<SlotPreviewHandle>(null)
  const { platforms } = usePlatforms()

  const livePreviewHtml = useDebouncedValue(draft, 300)
  const slots = useMemo(() => parseSlots(draft), [draft])

  const designSystemId =
    (task?.source_data as { design_system_id?: string } | undefined)?.design_system_id ??
    "default"
  const ground =
    ((task?.result?.strategic_brief as { ground?: string } | undefined)?.ground === "black"
      ? "black"
      : "white") as "white" | "black"
  const family = platformFamily(format, platforms)

  // Ctrl/Cmd ± / 0 and Ctrl+wheel zoom the preview, never the browser page.
  useEffect(() => {
    const applyZoom = (dir: "in" | "out" | "fit") => {
      if (dir === "fit") previewRef.current?.fit()
      else previewRef.current?.zoomBy(dir === "out" ? 1 / 1.25 : 1.25)
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
      applyZoom(dir)
    }
    const onWheel = (e: Event) => {
      const ev = e as WheelEvent
      if (!ev.ctrlKey) return
      ev.preventDefault()
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
  }, [])

  // Load the format into the editor whenever it changes. `loadedFormatRef`
  // guards resets to actual format switches — re-fetches triggered by a task
  // revalidation must not clobber the user's current tab.
  const loadedFormatRef = useRef<string | null>(null)
  useEffect(() => {
    let cancelled = false
    void (async () => {
      const html = await prefetchFormat(format)
      if (cancelled) return
      setDraft(html)
      if (loadedFormatRef.current !== format) {
        loadedFormatRef.current = format
        setMode("content")
      }
    })()
    return () => {
      cancelled = true
    }
  }, [format, prefetchFormat])

  // Keep QC + template id in sync with the latest task state.
  useEffect(() => {
    const p = task?.result?.platforms?.[format]
    setQc(
      p
        ? { score: p.quality_score, issues: p.quality_issues ?? [], critique: "", status: p.status }
        : null
    )
    setTemplateId((prev) => {
      const next = p?.template_id ?? null
      // A refill that switched templates already set this locally; only sync
      // when the server state actually moved.
      return prev === null || prev === next ? next : prev
    })
  }, [task, format])

  const applyServerHtml = useCallback(
    async (pngB64: string) => {
      const dataUri = pngB64 ? `data:image/png;base64,${pngB64}` : undefined
      if (dataUri) cachePng(format, dataUri)
      const fresh = await fetchText(`/tasks/${taskId}/files/${format}.html`).catch(() => "")
      if (fresh) {
        setDraft(fresh)
        cacheHtml(format, fresh)
      }
      onMutate()
    },
    [format, taskId, cachePng, cacheHtml, onMutate]
  )

  /** Structured edit (form or inline slot): refill → fresh HTML + QC. Throws. */
  const doRefill = useCallback(
    async (body: RefillRequest) => {
      setBusy(true)
      try {
        const res = await refillFormat(taskId, format, body)
        if (res.template_id) setTemplateId(res.template_id)
        setQc({
          score: res.quality.score,
          issues: res.quality.issues,
          critique: res.quality.critique,
          status: res.pass ? "verified" : "needs_review",
        })
        await applyServerHtml(res.png_b64)
      } finally {
        setBusy(false)
      }
    },
    [taskId, format, applyServerHtml]
  )

  const handleSlotCommit = useCallback(
    (slot: string, text: string) => {
      void doRefill({ slots: { [slot]: text } }).catch((err) => {
        toast.error(err instanceof Error ? err.message : "Inline edit failed")
      })
    },
    [doRefill]
  )

  const handleRerender = useCallback(
    async (audit: boolean) => {
      setBusy(true)
      try {
        const res = await apiRequest<RerenderResponse>(
          `/tasks/${taskId}/formats/${format}/rerender${audit ? "?audit=true" : ""}`,
          { method: "POST", body: JSON.stringify({ html: draft }) }
        )
        await applyServerHtml(res.png_b64)
        setQc({
          score: res.quality.score,
          issues: res.quality.issues,
          critique: res.quality.critique,
          status: res.pass ? "verified" : "needs_review",
        })
        toast.success(res.pass ? "Saved & rendered" : "Saved — review the issues")
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Re-render failed")
      } finally {
        setBusy(false)
      }
    },
    [format, taskId, draft, applyServerHtml]
  )

  const handleRetry = useCallback(async () => {
    setBusy(true)
    try {
      const res = await apiRequest<RetryResponse>(
        `/tasks/${taskId}/formats/${format}/retry`,
        { method: "POST" }
      )
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
      setBusy(false)
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
      setDraft(html)
      cacheHtml(format, html)
      await handleRerender(false)
    },
    [format, cacheHtml, handleRerender]
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
          {templateId ? (
            <span className="hidden rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground xl:inline">
              {templateId}
            </span>
          ) : null}
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
          {/* Manual (composed) posts never call the designer LLM. */}
          {task.source_data?.mode !== "manual" ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => void handleRetry()}
              disabled={busy}
              title="Re-run the designer LLM with the verifier critique, then re-verify"
            >
              <RefreshCw aria-hidden="true" className="size-4" />
              Retry designer
            </Button>
          ) : null}
          <Button size="sm" onClick={() => void handleRerender(false)} disabled={busy}>
            <Save aria-hidden="true" className="size-4" />
            {busy ? "Saving…" : "Save & Render"}
          </Button>
        </div>
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[340px_minmax(0,1fr)_360px]">
        <div className="grid min-w-0 content-start gap-2">
          <Tabs value={mode} onValueChange={(v) => setMode(v as "content" | "code")}>
            <TabsList className="h-8 w-full">
              <TabsTrigger value="content" className="flex-1 px-3 text-xs">
                Content
              </TabsTrigger>
              <TabsTrigger value="code" className="flex-1 px-3 text-xs">
                <FileCode2 aria-hidden="true" className="mr-1 size-3.5" />
                Code
              </TabsTrigger>
            </TabsList>
          </Tabs>
          <div className="min-h-[40vh] overflow-y-auto rounded-md border p-3 xl:h-[65vh]">
            {mode === "content" && templateId ? (
              <StructuredEditor
                format={format}
                slots={slots}
                templateId={templateId}
                designSystemId={designSystemId}
                ground={ground}
                family={family}
                refilling={busy}
                onRefill={doRefill}
              />
            ) : mode === "content" ? (
              <div className="grid gap-2 text-sm">
                <p className="font-medium">Freeform AI design</p>
                <p className="text-xs text-muted-foreground">
                  This post wasn't built from a template, so there are no structured
                  fields. Edit the HTML directly, or ask the agent chat to change it.
                </p>
                <Button size="sm" variant="outline" onClick={() => setMode("code")}>
                  Open Code
                </Button>
              </div>
            ) : (
              <div className="h-[50vh] xl:h-full">
                <HtmlEditor value={draft} onChange={setDraft} />
              </div>
            )}
          </div>
        </div>

        <div className="h-[60vh] min-w-0 overflow-hidden rounded-md border xl:h-[calc(65vh+44px)]">
          <SlotPreview
            ref={previewRef}
            html={livePreviewHtml}
            width={dims.width}
            height={dims.height}
            editable={Boolean(templateId) && !busy}
            onSlotCommit={handleSlotCommit}
          />
        </div>

        <aside className="h-[60vh] min-w-0 xl:h-[calc(65vh+44px)]">
          <InspectorRail
            qc={qc}
            taskId={taskId}
            format={format}
            currentHtml={draft}
            defaultTab="agent"
            onApplyHtml={applyHtml}
            onApplyAndRender={(html) => void applyAndRender(html)}
            onAudit={() => void handleRerender(true)}
            auditing={busy}
          />
        </aside>
      </div>
    </div>
  )
}
