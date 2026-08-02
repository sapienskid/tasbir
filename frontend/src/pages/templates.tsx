import { lazy, Suspense, useEffect, useState } from "react"
import { Link } from "react-router-dom"
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
import { ArrowLeft, Copy, Eye, EyeOff, Loader2, PenLine, Plus, Power, PowerOff, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Dropzone } from "@/components/tasks/dropzone"
import { PreviewFrame, ScaledFrame, FAMILY_DIMS } from "@/components/tasks/preview-frame"
import {
  createTemplateFromImage,
  createTemplate,
  deleteTemplate,
  getTemplate,
  previewDraft,
  previewTemplate,
  updateTemplate,
  type Template,
} from "@/lib/api"
import { useDesignSystems, useTemplates, useAgentJob, isJobDone } from "@/hooks/use-library"

const LazyHtmlEditor = lazy(() =>
  import("@/components/editor/html-editor").then((m) => ({ default: m.HtmlEditor }))
)

export default function TemplatesPage() {
  const { data: systems } = useDesignSystems()
  const [dsId, setDsId] = useState<string>("")
  const [includeInactive, setIncludeInactive] = useState(false)
  const activeSystems = (systems ?? []).filter((s) => s.is_active)
  const current = activeSystems.find((s) => s.id === dsId) ?? activeSystems[0]
  const { data: templates, isLoading, mutate } = useTemplates(
    current?.id ?? null,
    undefined,
    includeInactive
  )
  const inactiveCount = (templates ?? []).filter((t) => !t.is_active).length

  const [editTarget, setEditTarget] = useState<Template | null>(null)
  const [toggleTarget, setToggleTarget] = useState<Template | null>(null)
  const [imageOpen, setImageOpen] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const { data: job } = useAgentJob(jobId)

  async function handleDuplicate(t: Template) {
    try {
      const id = `${t.id}-copy`
      await createTemplate({
        id,
        name: `${t.name} (copy)`,
        design_system_id: t.design_system_id,
        family: t.family,
        grounds: t.grounds,
        categories: t.categories,
        hint_tags: t.hint_tags,
        weight: t.weight,
        description: t.description,
        html: t.html ?? "",
      })
      toast.success("Duplicated")
      void mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Duplicate failed")
    }
  }

  async function handleToggle(t: Template) {
    try {
      await updateTemplate(t.id, { is_active: !t.is_active })
      toast.success(t.is_active ? "Template deactivated" : "Template activated")
      void mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed")
    } finally {
      setToggleTarget(null)
    }
  }

  async function handleDelete(t: Template) {
    try {
      await deleteTemplate(t.id)
      toast.success("Deleted")
      void mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed")
    }
  }

  if (!current) {
    return (
      <div className="grid gap-4">
        <h1 className="text-xl font-semibold">Templates</h1>
        <p className="text-sm text-muted-foreground">
          No design systems — create one in{" "}
          <Link to="/design-systems" className="underline">
            Design Systems
          </Link>
          .
        </p>
      </div>
    )
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Templates</h1>
          <p className="text-sm text-muted-foreground">
            Reusable compositions for the {current.name} design system.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={current.id}
            onValueChange={(v) => {
              setDsId(v)
              setJobId(null)
            }}
          >
            <SelectTrigger className="w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {activeSystems.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant={includeInactive ? "default" : "outline"}
            size="sm"
            onClick={() => setIncludeInactive((v) => !v)}
            aria-pressed={includeInactive}
            title={
              inactiveCount > 0
                ? `${inactiveCount} inactive template(s)`
                : "No inactive templates"
            }
          >
            {includeInactive ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            {includeInactive ? "Hide inactive" : "Show inactive"}
            {inactiveCount > 0 ? (
              <span className="rounded bg-background/30 px-1.5 text-xs font-semibold">
                {inactiveCount}
              </span>
            ) : null}
          </Button>
          <Button onClick={() => setImageOpen(true)}>
            <Plus className="size-4" />
            From Image
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="sm">
          <Link to="/">
            <ArrowLeft className="size-4" />
            Tasks
          </Link>
        </Button>
      </div>

      {isLoading || !templates ? (
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-72 w-full" />
          ))}
        </div>
      ) : templates.length === 0 ? (
        <div className="rounded-md border p-8 text-center text-sm text-muted-foreground">
          {includeInactive
            ? "No templates yet — generate one from an image."
            : "No active templates — tick “Show inactive” to see deactivated ones, or create one from an image."}
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-4">
          {templates.map((t) => (
            <TemplateCard
              key={t.id}
              t={t}
              onEdit={() => setEditTarget(t)}
              onOpen={() => setEditTarget(t)}
              onDuplicate={() => void handleDuplicate(t)}
              onToggle={() => setToggleTarget(t)}
              onDelete={() => void handleDelete(t)}
            />
          ))}
        </div>
      )}

      {toggleTarget ? (
        <AlertDialog open={Boolean(toggleTarget)} onOpenChange={(o) => !o && setToggleTarget(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {toggleTarget.is_active ? "Deactivate" : "Activate"} template?
              </AlertDialogTitle>
              <AlertDialogDescription>
                {toggleTarget.is_active
                  ? "Inactive templates are hidden from the pipeline selection and the /new gallery."
                  : "Activated templates become available for selection again."}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={() => void handleToggle(toggleTarget)}>
                {toggleTarget.is_active ? "Deactivate" : "Activate"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : null}

      {editTarget ? (
        <EditTemplateDialog
          template={editTarget}
          open={Boolean(editTarget)}
          onOpenChange={(o) => !o && setEditTarget(null)}
          onSaved={() => {
            setEditTarget(null)
            void mutate()
          }}
        />
      ) : null}

      <FromImageDialog
        open={imageOpen}
        onOpenChange={setImageOpen}
        designSystemId={current.id}
        jobId={jobId}
        onJobStarted={setJobId}
        job={job}
        onDone={() => {
          setImageOpen(false)
          setJobId(null)
          void mutate()
        }}
      />
    </div>
  )
}

function TemplateCard({
  t,
  onEdit,
  onOpen,
  onDuplicate,
  onToggle,
  onDelete,
}: {
  t: Template
  onEdit: () => void
  onOpen: () => void
  onDuplicate: () => void
  onToggle: () => void
  onDelete: () => void
}) {
  const { data: preview, failed, retry } = useTemplatePreview(t.id)
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onOpen()}
      className={`grid cursor-pointer gap-2 rounded-md border p-2 transition-colors hover:border-primary/50 ${t.is_active ? "" : "opacity-60"}`}
    >
      <div className="flex justify-center rounded-md border bg-muted/10">
        {preview ? (
          <PreviewFrame html={preview.html} family={t.family} />
        ) : failed ? (
          <button
            onClick={(e) => {
              e.stopPropagation()
              retry()
            }}
            className="flex h-40 w-full items-center justify-center text-xs text-muted-foreground hover:underline"
          >
            Preview failed — retry
          </button>
        ) : (
          <div className="flex h-40 items-center justify-center">
            <Loader2 className="size-4 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>
      <div className="px-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-medium">{t.id}</span>
          <Badge variant="outline" className="shrink-0 text-[10px]">
            {t.family}
          </Badge>
        </div>
        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{t.description || "—"}</p>
        <div className="mt-2 flex items-center justify-between">
          <span className={`text-[10px] uppercase tracking-wide ${t.is_active ? "text-emerald-600" : "text-muted-foreground"}`}>
            {t.is_active ? "active" : "inactive"}
          </span>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" aria-label="Edit HTML" onClick={(e) => { e.stopPropagation(); onEdit() }}>
              <PenLine className="size-3.5" />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Duplicate" onClick={(e) => { e.stopPropagation(); onDuplicate() }}>
              <Copy className="size-3.5" />
            </Button>
            <TooltipProvider delayDuration={200}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t.is_active ? "Deactivate template" : "Activate template"}
                    onClick={(e) => { e.stopPropagation(); onToggle() }}
                  >
                    {t.is_active ? (
                      <Power className="size-3.5 text-emerald-600" />
                    ) : (
                      <PowerOff className="size-3.5 text-muted-foreground" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {t.is_active ? "Active — used by the pipeline. Click to deactivate." : "Inactive. Click to activate."}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <Button variant="ghost" size="icon" aria-label="Delete" onClick={(e) => { e.stopPropagation(); onDelete() }}>
              <Trash2 className="size-3.5 text-destructive" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function useTemplatePreview(id: string) {
  const [html, setHtml] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let alive = true
    setHtml(null)
    setFailed(false)
    const t = setTimeout(() => {
      previewTemplate(id)
        .then((r) => {
          if (alive) setHtml(r.html)
        })
        .catch(() => {
          if (alive) setFailed(true)
        })
    }, 60)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [id, attempt])

  return {
    data: html !== null ? { html } : null,
    failed,
    retry: () => setAttempt((a) => a + 1),
  }
}

function EditTemplateDialog({
  template,
  open,
  onOpenChange,
  onSaved,
}: {
  template: Template
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}) {
  const [html, setHtml] = useState("")
  const [grounds, setGrounds] = useState<string[]>(template.grounds)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [previewHtml, setPreviewHtml] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)

  // The list payload has no HTML body — fetch the full template on open.
  useEffect(() => {
    let alive = true
    setLoading(true)
    getTemplate(template.id)
      .then((full) => {
        if (!alive) return
        setHtml(full.html ?? "")
        setGrounds(full.grounds ?? template.grounds)
        setLoading(false)
      })
      .catch((e) => {
        if (!alive) return
        setLoading(false)
        toast.error(e instanceof Error ? e.message : "Failed to load template")
      })
    return () => {
      alive = false
    }
  }, [template.id, open]) // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced live preview of the draft — no save required.
  useEffect(() => {
    if (loading) return
    let alive = true
    setPreviewHtml(null)
    setPreviewError(null)
    const t = setTimeout(() => {
      previewDraft({
        html,
        family: template.family,
        design_system_id: template.design_system_id,
        ground: grounds[0] ?? "white",
      })
        .then((r) => {
          if (alive) setPreviewHtml(r.html)
        })
        .catch((e) => {
          if (alive) setPreviewError(e instanceof Error ? e.message : "Preview failed")
        })
    }, 600)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [html, grounds, loading, template.family, template.design_system_id])

  async function save() {
    setSaving(true)
    try {
      await updateTemplate(template.id, { html, grounds })
      toast.success("Template saved")
      onSaved()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex flex-col gap-4"
        style={{
          width: "calc(100vw - 3rem)",
          maxWidth: 1500,
          height: "92vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <DialogHeader>
          <DialogTitle>Edit {template.id}</DialogTitle>
          <DialogDescription>
            HTML is validated for overflow on save. The preview updates live as you type.
          </DialogDescription>
        </DialogHeader>
        <div className="grid min-h-0 flex-1 gap-4">
          <div className="flex items-center gap-3">
            <Label className="shrink-0">Grounds</Label>
            {(["white", "black"] as const).map((g) => (
              <label key={g} className="flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={grounds.includes(g)}
                  onChange={(e) =>
                    setGrounds((prev) =>
                      e.target.checked ? [...prev, g] : prev.filter((x) => x !== g)
                    )
                  }
                />
                {g}
              </label>
            ))}
            <span className="ml-auto text-xs text-muted-foreground">Live preview</span>
          </div>
          <div className="grid min-h-0 flex-1 grid-cols-2 gap-4">
            <div className="h-full min-h-0 overflow-hidden rounded-md border">
              {loading ? (
                <div className="flex h-full items-center justify-center">
                  <Loader2 className="size-5 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <Suspense fallback={<Skeleton className="h-full w-full" />}>
                  <LazyHtmlEditor value={html} onChange={setHtml} />
                </Suspense>
              )}
            </div>
            <div className="flex h-full min-h-0 items-center justify-center overflow-hidden rounded-md border bg-muted/10 p-4">
              {previewError ? (
                <p className="max-w-sm text-sm text-destructive">{previewError}</p>
              ) : previewHtml ? (
                <ScaledFrame
                  html={previewHtml}
                  width={FAMILY_DIMS[template.family]?.width ?? 1080}
                  height={FAMILY_DIMS[template.family]?.height ?? 1080}
                  maxWidth={560}
                  maxHeight={620}
                />
              ) : (
                <Loader2 className="size-5 animate-spin text-muted-foreground" />
              )}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => void save()} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function FromImageDialog({
  open,
  onOpenChange,
  designSystemId,
  jobId,
  onJobStarted,
  job,
  onDone,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  designSystemId: string
  jobId: string | null
  onJobStarted: (id: string) => void
  job: ReturnType<typeof useAgentJob>["data"]
  onDone: () => void
}) {
  const [busy, setBusy] = useState(false)

  async function handleFile(file: File) {
    setBusy(true)
    try {
      const res = await createTemplateFromImage(designSystemId, file)
      onJobStarted(res.job_id)
      toast.success("Template job started")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setBusy(false)
    }
  }

  const done = isJobDone(job)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Template from Image</DialogTitle>
          <DialogDescription>
            Drop a design mockup — the agent analyzes it and writes a validated template.
          </DialogDescription>
        </DialogHeader>
        {jobId ? (
          <div className="grid gap-2">
            <p className="text-sm">
              Job status:{" "}
              <Badge variant={job?.status === "completed" ? "default" : "outline"}>
                {job?.status ?? "starting"}
              </Badge>
            </p>
            {job?.status === "completed" ? (
              <p className="text-sm text-muted-foreground">
                Template created: <code>{(job.result as { template_id?: string })?.template_id}</code>
              </p>
            ) : null}
            {job?.status === "failed" ? (
              <p className="text-sm text-destructive">{job.error}</p>
            ) : null}
            {done ? (
              <Button onClick={onDone}>Done</Button>
            ) : (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Analyzing & validating…
              </p>
            )}
          </div>
        ) : (
          <Dropzone busy={busy} onFile={(f) => void handleFile(f)} hint="PNG, JPEG, WebP or GIF" />
        )}
      </DialogContent>
    </Dialog>
  )
}
