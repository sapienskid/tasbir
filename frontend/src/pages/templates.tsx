import { lazy, Suspense, useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
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
import { ArrowLeft, ChevronDown, Copy, Eye, EyeOff, Loader2, PenLine, Plus, Power, PowerOff, Trash2 } from "lucide-react"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import { Dropzone } from "@/components/tasks/dropzone"
import { FAMILY_DIMS, FitScaledFrame, ZoomableFrame } from "@/components/tasks/preview-frame"
import {
  createTemplate,
  createTemplateBuild,
  deleteTemplate,
  getTemplate,
  previewDraft,
  updateTemplate,
  type Template,
} from "@/lib/api"
import { useDesignSystems, useTemplates, useTemplatePreview, useAgentJob, isJobDone } from "@/hooks/use-library"

const LazyHtmlEditor = lazy(() =>
  import("@/components/editor/html-editor").then((m) => ({ default: m.HtmlEditor }))
)

export default function TemplatesPage() {
  const { data: systems } = useDesignSystems()
  const [dsId, setDsId] = useState<string>("")
  const [includeInactive, setIncludeInactive] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  const activeSystems = (systems ?? []).filter((s) => s.is_active)
  const current = activeSystems.find((s) => s.id === dsId) ?? activeSystems[0]
  const { data: templates, isLoading, mutate } = useTemplates(
    current?.id ?? null,
    undefined,
    true
  )
  const activeTemplates = (templates ?? []).filter((t) => t.is_active)
  const inactiveCount = (templates ?? []).filter((t) => !t.is_active).length

  const [editTarget, setEditTarget] = useState<Template | null>(null)
  const [toggleTarget, setToggleTarget] = useState<Template | null>(null)

  // ?open={templateId} → jump straight into the edit dialog.
  useEffect(() => {
    const openId = searchParams.get("open")
    if (!openId || !templates) return
    const t = templates.find((x) => x.id === openId)
    if (t) {
      setEditTarget(t)
      setSearchParams({}, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, templates])

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
            {includeInactive ? <EyeOff aria-hidden="true" className="size-4" /> : <Eye aria-hidden="true" className="size-4" />}
            {includeInactive ? "Hide inactive" : "Show inactive"}
            {inactiveCount > 0 ? (
              <span className="rounded bg-background/30 px-1.5 text-xs font-semibold">
                {inactiveCount}
              </span>
            ) : null}
          </Button>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus aria-hidden="true" className="size-4" />
            New template
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="sm">
          <Link to="/">
            <ArrowLeft aria-hidden="true" className="size-4" />
            Tasks
          </Link>
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <CountPill label="Total" value={(templates ?? []).length} />
        <CountPill label="Active" value={activeTemplates.length} />
        <CountPill label="Inactive" value={inactiveCount} muted />
        {(["square", "portrait", "story", "landscape"] as const).map((f) => (
          <CountPill
            key={f}
            label={f}
            value={(templates ?? []).filter((t) => t.family === f).length}
            muted
          />
        ))}
      </div>

      {isLoading || !templates ? (
        <div className="columns-1 gap-4 sm:columns-2 md:columns-3 xl:columns-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="mb-4 break-inside-avoid">
              <Skeleton className="aspect-[1/1.1] w-full rounded-lg" />
            </div>
          ))}
        </div>
      ) : (includeInactive ? templates : activeTemplates).length === 0 ? (
        <div className="rounded-md border p-8 text-center text-sm text-muted-foreground">
          {includeInactive
            ? "No templates yet — create one from an image, HTML, or a description."
            : "No active templates — tick “Show inactive” to see deactivated ones, or create one."}
        </div>
      ) : (
        <div className="columns-1 gap-4 sm:columns-2 md:columns-3 xl:columns-4">
          {(includeInactive ? templates : activeTemplates).map((t) => (
            <div key={t.id} className="mb-4 break-inside-avoid">
              <TemplateCard
                t={t}
                onEdit={() => setEditTarget(t)}
                onOpen={() => setEditTarget(t)}
                onDuplicate={() => void handleDuplicate(t)}
                onToggle={() => setToggleTarget(t)}
                onDelete={() => void handleDelete(t)}
              />
            </div>
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

      <CreateTemplateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        designSystemId={current.id}
        onDone={() => {
          setCreateOpen(false)
          void mutate()
        }}
      />
    </div>
  )
}

function CountPill({
  label,
  value,
  muted,
}: {
  label: string
  value: number
  muted?: boolean
}) {
  return (
    <span
      className={
        "flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs " +
        (muted ? "text-muted-foreground" : "font-semibold")
      }
    >
      <span className="uppercase tracking-wide">{label}</span>
      <span className={muted ? "" : "rounded bg-muted px-1.5"}>
        {value}
      </span>
    </span>
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
  const dims = FAMILY_DIMS[t.family] ?? FAMILY_DIMS.square
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onOpen()}
      className={`group flex cursor-pointer flex-col gap-2 rounded-lg border bg-card p-2 transition-colors hover:border-primary/50 hover:shadow-sm ${t.is_active ? "" : "opacity-60"}`}
    >
      <div
        className="relative w-full overflow-hidden rounded-md border bg-muted/10"
        style={{ aspectRatio: `${dims.width}/${dims.height}` }}
      >
        {preview ? (
          <FitScaledFrame html={preview.html} width={dims.width} height={dims.height} gap={4} bordered={false} />
        ) : failed ? (
          <button
            onClick={(e) => {
              e.stopPropagation()
              retry()
            }}
            className="flex h-full w-full items-center justify-center text-xs text-muted-foreground hover:underline"
          >
            Preview failed — retry
          </button>
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <Loader2 className="size-4 animate-spin text-muted-foreground" />
          </div>
        )}
        <div className="absolute inset-x-0 bottom-0 hidden items-center justify-end gap-0.5 bg-gradient-to-t from-black/60 to-transparent p-1.5 group-hover:flex">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Edit HTML"
            className="size-7 text-white hover:bg-white/20 hover:text-white"
            onClick={(e) => {
              e.stopPropagation()
              onEdit()
            }}
          >
            <PenLine aria-hidden="true" className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Duplicate"
            className="size-7 text-white hover:bg-white/20 hover:text-white"
            onClick={(e) => {
              e.stopPropagation()
              onDuplicate()
            }}
          >
            <Copy aria-hidden="true" className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t.is_active ? "Deactivate template" : "Activate template"}
            className="size-7 text-white hover:bg-white/20 hover:text-white"
            onClick={(e) => {
              e.stopPropagation()
              onToggle()
            }}
          >
            {t.is_active ? (
              <Power aria-hidden="true" className="size-3.5 text-emerald-300" />
            ) : (
              <PowerOff aria-hidden="true" className="size-3.5" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Delete"
            className="size-7 text-white hover:bg-red-500/40 hover:text-white"
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
          >
            <Trash2 aria-hidden="true" className="size-3.5" />
          </Button>
        </div>
      </div>
      <div className="px-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-semibold">{t.name || t.id}</span>
          <Badge variant="outline" className="shrink-0 text-[10px]">
            {t.family}
          </Badge>
        </div>
        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{t.description || "—"}</p>
        <div className="mt-2 flex flex-wrap items-center gap-1">
          {(t.grounds ?? []).map((g) => (
            <span key={g} className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
              {g}
            </span>
          ))}
          {(t.categories ?? []).slice(0, 2).map((c) => (
            <span key={c} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {c}
            </span>
          ))}
          <span
            className={`ml-auto text-[10px] font-medium uppercase tracking-wide ${
              t.is_active ? "text-emerald-600" : "text-muted-foreground"
            }`}
          >
            {t.is_active ? "active" : "inactive"}
          </span>
        </div>
      </div>
    </div>
  )
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
  const [name, setName] = useState(template.name)
  const [description, setDescription] = useState(template.description)
  const [categories, setCategories] = useState<string[]>(template.categories)
  const [hintTags, setHintTags] = useState<string[]>(template.hint_tags)
  const [weight, setWeight] = useState(template.weight)
  const [isActive, setIsActive] = useState(template.is_active)
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
        setName(full.name ?? template.name)
        setDescription(full.description ?? template.description)
        setCategories(full.categories ?? template.categories)
        setHintTags(full.hint_tags ?? template.hint_tags)
        setWeight(full.weight ?? template.weight)
        setIsActive(full.is_active ?? template.is_active)
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
      await updateTemplate(template.id, {
        html,
        grounds,
        name,
        description,
        categories,
        hint_tags: hintTags,
        weight,
        is_active: isActive,
      })
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
          <details className="group rounded-md border p-3">
            <summary className="cursor-pointer select-none text-sm font-medium">
              Metadata
              <ChevronDown aria-hidden="true" className="ml-1 inline size-4 align-text-bottom transition-transform group-open:rotate-180" />
            </summary>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="tpl-name">Name</Label>
                <Input id="tpl-name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="tpl-weight">Weight (selection bias, 0.1–10)</Label>
                <Input
                  id="tpl-weight"
                  type="number"
                  step={0.1}
                  min={0.1}
                  max={10}
                  value={weight}
                  onChange={(e) => setWeight(Number(e.target.value))}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="tpl-cat">Categories (comma-separated)</Label>
                <Input
                  id="tpl-cat"
                  value={categories.join(", ")}
                  onChange={(e) =>
                    setCategories(e.target.value.split(",").map((s) => s.trim()).filter(Boolean))
                  }
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="tpl-tags">Hint tags (comma-separated)</Label>
                <Input
                  id="tpl-tags"
                  value={hintTags.join(", ")}
                  onChange={(e) =>
                    setHintTags(e.target.value.split(",").map((s) => s.trim()).filter(Boolean))
                  }
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="tpl-desc">Description</Label>
                <Textarea
                  id="tpl-desc"
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className="flex flex-col justify-between gap-2">
                <div className="space-y-1">
                  <Label>Identity (read-only)</Label>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="outline">{template.family}</Badge>
                    <Badge variant="secondary">{template.id}</Badge>
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                  />
                  Active (selectable by the pipeline)
                </label>
              </div>
            </div>
          </details>

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
            <div className="h-full min-h-0 overflow-hidden rounded-md border bg-muted/10">
              {previewError ? (
                <p className="flex h-full items-center justify-center p-4 text-sm text-destructive">
                  {previewError}
                </p>
              ) : previewHtml ? (
                <ZoomableFrame
                  html={previewHtml}
                  width={FAMILY_DIMS[template.family]?.width ?? 1080}
                  height={FAMILY_DIMS[template.family]?.height ?? 1080}
                />
              ) : (
                <div className="flex h-full items-center justify-center">
                  <Loader2 className="size-5 animate-spin text-muted-foreground" />
                </div>
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

function CreateTemplateDialog({
  open,
  onOpenChange,
  designSystemId,
  onDone,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  designSystemId: string
  onDone: () => void
}) {
  const [mode, setMode] = useState<"image" | "html" | "text">("text")
  const [message, setMessage] = useState("")
  const [html, setHtml] = useState("")
  const [image, setImage] = useState<File | null>(null)
  const [family, setFamily] = useState("square")
  const [ground, setGround] = useState("white")
  const [starting, setStarting] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const { data: job } = useAgentJob(jobId)

  const canStart = mode === "image" ? Boolean(image) : mode === "html" ? html.trim().length >= 50 : message.trim().length > 0
  const done = isJobDone(job)

  async function handleImage(file: File) {
    setImage(file)
  }

  async function start() {
    if (!canStart) return
    setStarting(true)
    try {
      const res = await createTemplateBuild({
        designSystemId,
        message: mode === "text" ? message : message || undefined,
        html: mode === "html" ? html : undefined,
        family,
        ground,
        image: mode === "image" ? image : undefined,
      })
      toast.success("Template job started")
      setJobId(res.job_id)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Start failed")
    } finally {
      setStarting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New template</DialogTitle>
          <DialogDescription>
            The agent builds a validated template in the background — paste an
            image, HTML, or describe the layout for context.
          </DialogDescription>
        </DialogHeader>
        {jobId ? (
          <div className="grid gap-3">
            <p className="flex items-center gap-2 text-sm">
              Job status:{" "}
              <Badge variant={job?.status === "completed" ? "default" : "outline"}>
                {job?.status ?? "starting"}
              </Badge>
            </p>
            {job?.status === "completed" ? (
              <p className="text-sm text-muted-foreground">
                Template created:{" "}
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                  {(job.result as { template_id?: string } | null)?.template_id ?? "—"}
                </code>
              </p>
            ) : null}
            {job?.status === "failed" ? (
              <p className="text-sm text-destructive">{job.error}</p>
            ) : null}
            {done ? (
              <Button onClick={onDone}>Done</Button>
            ) : (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                Analyzing & validating… runs in the background, close anytime.
              </p>
            )}
          </div>
        ) : (
          <div className="grid gap-3">
            <Tabs value={mode} onValueChange={(v) => setMode(v as typeof mode)}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="text">Describe</TabsTrigger>
                <TabsTrigger value="image">Image</TabsTrigger>
                <TabsTrigger value="html">HTML</TabsTrigger>
              </TabsList>
              <TabsContent value="text" className="grid gap-2">
                <Textarea
                  rows={4}
                  aria-label="Describe the template"
                  placeholder="e.g. a bold square post, big serif headline, thin rule under the footer"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                />
              </TabsContent>
              <TabsContent value="image" className="grid gap-2">
                {image ? (
                  <div className="flex items-center justify-between rounded-md border p-2 text-sm">
                    <span className="truncate">{image.name}</span>
                    <Button variant="ghost" size="sm" onClick={() => setImage(null)}>
                      Remove
                    </Button>
                  </div>
                ) : (
                  <Dropzone onFile={(f) => void handleImage(f)} hint="Paste or drop a mockup — PNG, JPEG, WebP or GIF" />
                )}
              </TabsContent>
              <TabsContent value="html" className="grid gap-2">
                <Textarea
                  rows={6}
                  aria-label="Paste template HTML"
                  placeholder="Paste an existing template's HTML (Jinja2) to convert into a validated library template…"
                  value={html}
                  onChange={(e) => setHtml(e.target.value)}
                />
              </TabsContent>
            </Tabs>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <Label className="text-xs text-muted-foreground">Ratio</Label>
                <Select value={family} onValueChange={setFamily}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="square">Square</SelectItem>
                    <SelectItem value="portrait">Portrait</SelectItem>
                    <SelectItem value="story">Story</SelectItem>
                    <SelectItem value="landscape">Landscape</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <Label className="text-xs text-muted-foreground">Ground</Label>
                <Select value={ground} onValueChange={setGround}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="white">White</SelectItem>
                    <SelectItem value="black">Black</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={starting}>
                Cancel
              </Button>
              <Button onClick={() => void start()} disabled={!canStart || starting}>
                {starting ? (
                  <>
                    <Loader2 aria-hidden="true" className="size-4 animate-spin" /> Starting…
                  </>
                ) : (
                  "Create template"
                )}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
