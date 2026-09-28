import { useCallback, useEffect, useRef, useState } from "react"
import { HtmlEditor } from "@/components/editor/html-editor"
import { useDebouncedValue } from "@/components/editor/use-debounce"
import { SlotPreview, type FrameKey, type SlotPreviewHandle } from "@/components/tasks/slot-preview"
import { SavePill } from "@/components/tasks/save-pill"
import { useEditorSession } from "@/hooks/use-editor-session"
import { StructuredEditor } from "@/components/tasks/structured-editor"
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
  Redo2,
  RefreshCw,
  Save,
  Undo2,
} from "lucide-react"
import { toast } from "sonner"
import {
  apiRequest,
  downloadBlob,
  fetchBlob,
  fetchText,
  mapComposeTemplates,
  refillFormat,
  type RerenderResponse,
  type RetryResponse,
  type TaskDetail,
} from "@/lib/api"
import { useDesignSystems } from "@/hooks/use-library"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { formatLabel } from "@/components/tasks/format-utils"

/** Carousel slide ids (instagram-carousel-2) → their base platform for mapping. */
function carouselBase(fmt: string): string {
  const m = /^(instagram-carousel(?:-portrait)?)-\d+$/.exec(fmt)
  return m ? m[1] : fmt
}

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

  // Structured editing session: one shared store (form + inline), latest-wins
  // server previews and a coalesced background save. Survives navigation.
  const { session, snap } = useEditorSession(taskId, format, () => prefetchFormat(format), {
    onPersisted: ({ html, pngB64 }) => {
      if (pngB64) cachePng(format, `data:image/png;base64,${pngB64}`)
      if (html) cacheHtml(format, html)
      onMutate()
    },
    onNotify: ({ level, message }) => (level === "error" ? toast.error(message) : toast(message)),
  })
  const structured = snap.phase === "ready" && snap.info !== null

  const { data: systems } = useDesignSystems()
  const activeSystems = (systems ?? []).filter((s) => s.is_active !== false)
  const taskDs =
    (task?.source_data as { design_system_id?: string } | undefined)?.design_system_id ??
    "default"
  const curDs = snap.info?.design_system_id ?? taskDs
  const [remapping, setRemapping] = useState(false)

  // Design-system switch, manual-compose style: remap the current template
  // onto the new system, then re-fill under it in one store commit (one undo
  // step). Designer posts convert via a direct refill that auto-picks.
  const switchDesignSystem = useCallback(
    async (newId: string) => {
      if (!newId || newId === curDs || remapping) return
      const name = activeSystems.find((d) => d.id === newId)?.name ?? newId
      if (!structured) {
        setRemapping(true)
        try {
          await refillFormat(taskId, format, { design_system_id: newId })
          toast.success(`Switched to ${name} — re-rendered under the new system`)
          onMutate()
          await session.load(() => prefetchFormat(format))
        } catch (err) {
          toast.error(
            `Couldn't switch design system — ${err instanceof Error ? err.message : "unknown error"}`
          )
        } finally {
          setRemapping(false)
        }
        return
      }
      const curTpl = session.store.doc.templateId
      setRemapping(true)
      try {
        let mapped = ""
        if (curTpl) {
          const res = await mapComposeTemplates({
            from_design_system_id: curDs,
            to_design_system_id: newId,
            template_ids: [curTpl],
            platform: carouselBase(format),
          })
          mapped = res.mapping?.[curTpl] ?? ""
        }
        session.store.setDesignSystem(newId, mapped)
        if (mapped && mapped !== curTpl) {
          toast.success(`Switched to ${name} — remapped ${curTpl} → ${mapped}`)
        } else if (mapped) {
          toast.success(`Switched to ${name} — template kept`)
        } else {
          toast.success(`Switched to ${name} — picking a matching template`)
        }
        await session.flush()
        await session.load(() => prefetchFormat(format))
        onMutate()
      } catch (err) {
        toast.error(
          `Couldn't switch design system — ${err instanceof Error ? err.message : "unknown error"}`
        )
      } finally {
        setRemapping(false)
      }
    },
    [curDs, remapping, structured, session, taskId, format, activeSystems, prefetchFormat, onMutate]
  )

  const livePreviewHtml = useDebouncedValue(draft, 300)

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
        void session.load(() => prefetchFormat(format))
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Re-render failed")
      } finally {
        setBusy(false)
      }
    },
    [format, taskId, draft, applyServerHtml, session, prefetchFormat]
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
      void session.load(() => prefetchFormat(format))
      onMutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Retry failed")
    } finally {
      setBusy(false)
    }
  }, [taskId, format, prefetchFormat, cachePng, onMutate, session])

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

  const flushNow = useCallback(
    async (announce: boolean) => {
      const ok = await session.flush()
      if (announce) {
        if (ok) toast.success("Saved")
        else toast.error("Couldn't save — see the status pill")
      }
    },
    [session]
  )

  // Undo / redo / save shortcuts (also forwarded from inside the preview frame).
  const handleKey = useCallback(
    (e: { key: string; ctrl: boolean; shift: boolean; preventDefault: () => void }) => {
      if (mode !== "content" || !structured) return false
      const k = e.key.toLowerCase()
      if (e.ctrl && k === "z") {
        e.preventDefault()
        if (e.shift) session.redo()
        else session.undo()
        return true
      }
      if (e.ctrl && k === "y") {
        e.preventDefault()
        session.redo()
        return true
      }
      if (e.ctrl && k === "s") {
        e.preventDefault()
        void flushNow(true)
        return true
      }
      return false
    },
    [mode, structured, session, flushNow]
  )
  const onFrameKey = useCallback((e: FrameKey) => void handleKey(e), [handleKey])
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if (!(ev.ctrlKey || ev.metaKey)) return
      const t = ev.target as HTMLElement | null
      // Leave the agent chat / code editor's own undo alone.
      if (t?.closest("aside, .monaco-editor")) return
      handleKey({
        key: ev.key,
        ctrl: true,
        shift: ev.shiftKey,
        preventDefault: () => ev.preventDefault(),
      })
    }
    window.addEventListener("keydown", onKey, true)
    return () => window.removeEventListener("keydown", onKey, true)
  }, [handleKey])

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
          {snap.info?.template_id || templateId ? (
            <span className="hidden rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground xl:inline">
              {snap.info?.template_id || templateId}
            </span>
          ) : null}
          {activeSystems.length > 1 ? (
            <Select
              value={activeSystems.some((s) => s.id === curDs) ? curDs : undefined}
              onValueChange={(id) => void switchDesignSystem(id)}
              disabled={
                remapping ||
                snap.phase === "loading" ||
                (snap.info !== null && !snap.info.editable && snap.info.reason !== "designer")
              }
            >
              <SelectTrigger
                className="h-7 w-40 text-xs"
                aria-label="Design system"
                title={
                  snap.info !== null && !snap.info.editable && snap.info.reason !== "designer"
                    ? "Design system switching needs a convertible post"
                    : undefined
                }
              >
                <SelectValue placeholder="Design system" />
              </SelectTrigger>
              <SelectContent>
                {activeSystems.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name || s.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {structured && mode === "content" ? (
            <>
              <SavePill save={snap.save} onRetry={() => void session.retrySave()} />
              <div className="flex items-center">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  aria-label="Undo"
                  title="Undo (Ctrl/Cmd+Z)"
                  disabled={!snap.canUndo}
                  onClick={() => session.undo()}
                >
                  <Undo2 aria-hidden="true" className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  aria-label="Redo"
                  title="Redo (Shift+Ctrl/Cmd+Z)"
                  disabled={!snap.canRedo}
                  onClick={() => session.redo()}
                >
                  <Redo2 aria-hidden="true" className="size-4" />
                </Button>
              </div>
            </>
          ) : null}
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
          {structured && mode === "content" ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => void flushNow(true)}
              disabled={snap.save.phase === "saved"}
              title="Save now (Ctrl/Cmd+S)"
            >
              <Save aria-hidden="true" className="size-4" />
              Save
            </Button>
          ) : (
            <Button size="sm" onClick={() => void handleRerender(false)} disabled={busy}>
              <Save aria-hidden="true" className="size-4" />
              {busy ? "Saving…" : "Save & Render"}
            </Button>
          )}
        </div>
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[340px_minmax(0,1fr)_360px]">
        <div className="grid min-w-0 content-start gap-2">
          <Tabs
            value={mode}
            onValueChange={(v) => {
              if (v === "code" && structured) {
                void session.flush().then(() => setDraft(snap.html))
              }
              setMode(v as "content" | "code")
            }}
          >
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
            {mode === "content" && structured && snap.info ? (
              <StructuredEditor session={session} info={snap.info} />
            ) : mode === "content" && snap.phase === "loading" ? (
              <p className="text-xs text-muted-foreground">Loading editor…</p>
            ) : mode === "content" && snap.phase === "error" ? (
              <p className="rounded-md border border-destructive/50 p-3 text-xs text-destructive">
                {snap.error ?? "Couldn't load the editor."}
              </p>
            ) : mode === "content" ? (
              <div className="grid gap-2 text-sm">
                <p className="font-medium">Freeform AI design</p>
                <p className="text-xs text-muted-foreground">
                  {snap.info?.reason === "manual"
                    ? "Manually composed posts are edited from their composition."
                    : "This post wasn't built from a template, so there are no structured fields. Edit the HTML directly, or ask the agent chat to change it."}
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
            html={mode === "content" && structured ? snap.html : livePreviewHtml}
            htmlVersion={mode === "content" && structured ? snap.htmlVersion : 0}
            width={dims.width}
            height={dims.height}
            store={mode === "content" && structured ? session.store : null}
            editable={mode === "content" && structured}
            updating={snap.updating}
            onHotkey={onFrameKey}
          />
        </div>

        <aside className="h-[60vh] min-w-0 xl:h-[calc(65vh+44px)]">
          <InspectorRail
            qc={
              snap.qc
                ? {
                    score: snap.qc.score,
                    issues: snap.qc.issues,
                    critique: snap.qc.critique,
                    status: snap.qc.pass ? "verified" : "needs_review",
                  }
                : qc
            }
            taskId={taskId}
            format={format}
            currentHtml={mode === "content" && structured ? snap.html : draft}
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
