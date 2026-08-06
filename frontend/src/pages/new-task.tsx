import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { ArrowLeft, ArrowRight, Check, ImagePlus, Link2, Loader2, Wand2, X } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import {
  apiRequest,
  listStyleLanguages,
  uploadMedia,
  type GenerateResponse,
  type DesignSystem,
  type StyleLanguage,
  type Template,
} from "@/lib/api"
import { useDesignSystems, useTemplates, useTemplatePreview } from "@/hooks/use-library"
import { usePlatforms } from "@/hooks/use-platforms"
import { familyOfPlatform } from "@/lib/platforms"
import { PreviewFrame, FAMILY_DIMS } from "@/components/tasks/preview-frame"

function isCarouselPlatform(p: string): boolean {
  return p === "instagram-carousel" || p === "instagram-carousel-portrait"
}

const STEPS = ["Design System", "Content", "Template", "Media"]

const POST_TYPE_LABELS: Record<string, string> = {
  default: "Editorial",
  quote: "Quote",
  promo: "Promo / announcement",
  event: "Event",
  product: "Product drop",
  comparison: "Comparison",
  tutorial: "Tutorial",
}

/** Clearer labels for the carousel platforms (aspect encoded in the id). */
function platformLabel(p: { id: string; name: string }): string {
  if (p.id === "instagram-carousel") return "Instagram carousel 1:1"
  if (p.id === "instagram-carousel-portrait") return "Instagram carousel 4:5"
  return p.name || p.id
}

interface PlatformOverride {
  post_type?: string
  template_id?: string
}

interface MediaEntry {
  data?: string
  mime?: string
  url?: string
  alt: string
  placement?: string
  description?: string
}

export default function NewTaskPage() {
  const navigate = useNavigate()
  const { data: systems, isLoading: dsLoading } = useDesignSystems()
  const { platforms: dbPlatforms } = usePlatforms()

  const [step, setStep] = useState(0)
  const [dsId, setDsId] = useState<string>("")
  const [styles, setStyles] = useState<StyleLanguage[]>([])
  const [styleLang, setStyleLang] = useState<string>("")
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")
  const [category, setCategory] = useState("")
  const [campaign, setCampaign] = useState("default")
  const [platforms, setPlatforms] = useState<string[]>(["instagram-square"])
  const [slides, setSlides] = useState(3)
  const [sequenceAudit, setSequenceAudit] = useState(false)
  const [verbatim, setVerbatim] = useState(false)
  const [templateId, setTemplateId] = useState<string>("")
  const [templateMode, setTemplateMode] = useState<"auto" | "template" | "designer">("auto")
  const [postType, setPostType] = useState("default")
  // Step-2 gallery scope: "__all__" applies a template post-wide, a platform id
  // assigns a template to that one platform (visual per-platform selection).
  const [templateScope, setTemplateScope] = useState<string>("__all__")
  const [platformOverrides, setPlatformOverrides] = useState<Record<string, PlatformOverride>>({})
  // Per-platform media uploads: {platform_id: {slot_key: MediaEntry}}.
  const [media, setMedia] = useState<Record<string, Record<string, MediaEntry>>>({})
  const [submitting, setSubmitting] = useState(false)

  const activeSystems = useMemo(
    () => (systems ?? []).filter((s) => s.is_active),
    [systems]
  )
  const ds: DesignSystem | undefined = activeSystems.find((s) => s.id === dsId)
  const { data: templates, error: templatesError, isLoading: tplLoading } = useTemplates(dsId || null)

  // Auto-select the only (or default) design system.
  useEffect(() => {
    if (!dsId && activeSystems.length > 0) {
      const preferred = activeSystems.find((s) => s.id === "default") ?? activeSystems[0]
      setDsId(preferred.id)
    }
  }, [activeSystems, dsId])

  useEffect(() => {
    listStyleLanguages()
      .then(setStyles)
      .catch(() => setStyles([]))
  }, [])

  const families = useMemo(
    () => [...new Set(platforms.map((p) => familyOfPlatform(p)).filter(Boolean))],
    [platforms]
  )
  const scopeFamily = useMemo(
    () => (templateScope === "__all__" ? null : familyOfPlatform(templateScope) || null),
    [templateScope]
  )
  const gallery = useMemo(() => {
    const fams = scopeFamily ? [scopeFamily] : families
    return (templates ?? []).filter(
      (t) =>
        fams.includes(t.family) &&
        (!verbatim || t.supports_text !== false) // verbatim needs a body slot
    )
  }, [templates, families, scopeFamily, verbatim])
  const selected = useMemo(
    () => (templates ?? []).find((t) => t.id === templateId),
    [templates, templateId]
  )
  const concretePlatforms = useMemo(() => platforms.filter((p) => p !== "auto"), [platforms])
  const platformById = useMemo(() => {
    const map: Record<string, { id: string; name: string }> = {}
    for (const p of dbPlatforms) map[p.id] = p
    return map
  }, [dbPlatforms])

  /** The template that actually applies to a platform (override or global). */
  function effectiveTemplate(pid: string): Template | undefined {
    const overrideId = platformOverrides[pid]?.template_id
    if (overrideId) return (templates ?? []).find((t) => t.id === overrideId)
    if (selected && selected.family === familyOfPlatform(pid)) return selected
    return undefined
  }

  /** The effective template id for a platform ("" = auto). */
  function effectiveTemplateId(pid: string): string {
    return effectiveTemplate(pid)?.id ?? ""
  }

  /** Assign a template visually. scope "__all__" → global; else per-platform. */
  function pickTemplate(scope: string, tid: string) {
    if (scope === "__all__") {
      setTemplateId(tid)
    } else {
      setPlatformOverride(scope, { template_id: tid || undefined })
    }
  }

  /** Whether a card is the active choice for the current scope. */
  function isTemplateSelected(scope: string, tid: string): boolean {
    if (scope === "__all__") return templateId === tid
    return (platformOverrides[scope]?.template_id ?? "") === tid
  }

  /** Platforms explicitly assigned this template id (for gallery badges). */
  function assignedPlatforms(tid: string): string[] {
    return Object.entries(platformOverrides)
      .filter(([, v]) => v.template_id === tid)
      .map(([pid]) => pid)
  }

  function togglePlatform(p: string, checked: boolean) {
    setPlatforms((prev) => {
      const next = checked ? [...prev, p] : prev.filter((x) => x !== p)
      if (!checked) {
        setPlatformOverrides((overrides) => {
          const copy = { ...overrides }
          delete copy[p]
          return copy
        })
      }
      return next
    })
  }

  function setPlatformOverride(pid: string, patch: Partial<PlatformOverride>) {
    setPlatformOverrides((prev) => {
      const cur = prev[pid] ?? {}
      const next = { ...cur, ...patch }
      const copy = { ...prev }
      if (next.post_type || next.template_id) copy[pid] = next
      else delete copy[pid]
      return copy
    })
  }

  async function submit() {
    if (!content.trim()) {
      toast.error("Content is required")
      return
    }
    if (platforms.length === 0) {
      toast.error("Pick at least one platform")
      return
    }
    setSubmitting(true)
    try {
      const allImages: Array<{
        data?: string
        mime?: string
        url?: string
        alt: string
        description: string
        placement: string
      }> = []
      const platformImages: Record<string, typeof allImages> = {}
      for (const [pid, slots] of Object.entries(media)) {
        const list = Object.entries(slots)
          .filter(([, v]) => v.data || v.url)
          .map(([slotKey, v]) => ({
            data: v.data || undefined,
            mime: v.mime,
            url: v.url || undefined,
            alt: v.alt || `Image ${slotKey}`,
            description: v.description ?? "",
            placement: v.placement ?? "auto",
          }))
        if (list.length > 0) {
          platformImages[pid] = list
          allImages.push(...list)
        }
      }
      const hasCarousel = platforms.some(isCarouselPlatform)
      const config = Object.entries(platformOverrides)
        .filter(([, v]) => v.post_type || v.template_id)
        .reduce<Record<string, PlatformOverride>>((acc, [pid, v]) => {
          acc[pid] = {
            ...(v.post_type ? { post_type: v.post_type } : {}),
            ...(v.template_id ? { template_id: v.template_id } : {}),
          }
          return acc
        }, {})
      const res = await apiRequest<GenerateResponse>("/generate", {
        method: "POST",
        body: JSON.stringify({
          content,
          title,
          category: category || undefined,
          campaign,
          platforms,
          slides: hasCarousel ? slides : undefined,
          sequence_audit: sequenceAudit,
          verbatim,
          design_system_id: dsId,
          template_id: templateId,
          template_mode: templateMode,
          post_type: postType,
          platforms_config: Object.keys(config).length > 0 ? config : undefined,
          style_language: styleLang || undefined,
          images: allImages.length > 0 ? allImages : undefined,
          platform_images:
            Object.keys(platformImages).length > 0 ? platformImages : undefined,
        }),
      })
      toast.success("Task queued")
      navigate(`/tasks/${res.task_id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to queue task")
    } finally {
      setSubmitting(false)
    }
  }

  async function handleMediaUpload(pid: string, slotKey: string, file: File) {
    try {
      const res = await uploadMedia(file)
      setMedia((prev) => ({
        ...prev,
        [pid]: {
          ...(prev[pid] ?? {}),
          [slotKey]: {
            ...(prev[pid]?.[slotKey] ?? { alt: "", placement: "auto" }),
            data: res.data,
            mime: res.mime,
            url: undefined,
          },
        },
      }))
      toast.success("Image uploaded")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed")
    }
  }

  function setSlotMedia(pid: string, slotKey: string, patch: Partial<MediaEntry>) {
    setMedia((prev) => ({
      ...prev,
      [pid]: {
        ...(prev[pid] ?? {}),
        [slotKey]: { ...(prev[pid]?.[slotKey] ?? { alt: "", placement: "auto" }), ...patch },
      },
    }))
  }

  // Media step surfaces every selected platform's effective template slots.
  const mediaPlatforms = concretePlatforms.filter((pid) => {
    const t = effectiveTemplate(pid)
    return Boolean(t && (t.image_slots?.length ?? 0) > 0)
  })
  const hasMediaStep = mediaPlatforms.length > 0

  if (dsLoading && !systems) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }
  if (systems && activeSystems.length === 0) {
    return (
      <div className="grid gap-4">
        <h1 className="text-xl font-semibold">New Task</h1>
        <div className="rounded-md border p-6 text-sm">
          <p className="font-medium">No design systems yet.</p>
          <p className="text-muted-foreground">
            Create one in{" "}
            <Link to="/design-systems" className="underline">
              Design Systems
            </Link>{" "}
            first.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto grid max-w-3xl gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">New Task</h1>
          <p className="text-sm text-muted-foreground">
            Pick a design system, add content, choose a template, attach media.
          </p>
        </div>
        <Button asChild variant="ghost" size="sm">
          <Link to="/">
            <ArrowLeft aria-hidden="true" className="size-4" />
            Back
          </Link>
        </Button>
      </div>

      <div className="flex items-center gap-2">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <span
              className={`flex size-6 items-center justify-center rounded-full text-xs font-medium ${
                i < step || (i === 3 && !hasMediaStep && step === 3)
                  ? "bg-primary text-primary-foreground"
                  : i === step
                    ? "bg-muted text-foreground"
                    : "bg-muted/50 text-muted-foreground"
              }`}
            >
              {i < step || (i === 3 && !hasMediaStep && step === 3) ? (
                <Check aria-hidden="true" className="size-3" />
              ) : (
                i + 1
              )}
            </span>
            <span className={`text-xs ${i === step ? "font-medium" : "text-muted-foreground"}`}>
              {label}
            </span>
          </div>
        ))}
      </div>

      {step === 0 ? (
        <Card>
          <CardContent className="grid gap-3 p-6">
            <Label>Design System</Label>
            {activeSystems.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  setDsId(s.id)
                  setStyleLang("")
                  // Templates are scoped per design system — a stale choice
                  // from another DS would 422 on submit.
                  setTemplateId("")
                  setPlatformOverrides({})
                }}
                className={`flex items-center justify-between rounded-md border p-4 text-left transition-colors ${
                  dsId === s.id ? "border-primary bg-muted/50" : "hover:bg-muted/30"
                }`}
              >
                <div>
                  <p className="font-medium">{s.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {s.description || s.id} · {s.template_count ?? "?"} templates ·{" "}
                    {(s.design_instruction as { style_language?: string } | undefined)?.style_language ??
                      "swiss-editorial"}
                  </p>
                </div>
                {dsId === s.id ? <Check aria-hidden="true" className="size-4 text-primary" /> : null}
              </button>
            ))}
            {styles.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <Label className="shrink-0 text-xs text-muted-foreground">
                  Design language (optional override)
                </Label>
                <Select value={styleLang} onValueChange={setStyleLang}>
                  <SelectTrigger className="w-56">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Use this system's language</SelectItem>
                    {styles.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="flex justify-end">
              <Button onClick={() => setStep(1)} disabled={!dsId}>
                Continue <ArrowRight aria-hidden="true" className="size-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {step === 1 ? (
        <Card>
          <CardContent className="grid gap-4 p-6">
            <div className="grid gap-2">
              <Label htmlFor="nt-title">Title</Label>
              <Input id="nt-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Article title" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="nt-content">Content</Label>
              <Textarea id="nt-content" className="min-h-40" value={content} onChange={(e) => setContent(e.target.value)} placeholder="Paste the full article / blog post…" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="nt-category">Category</Label>
                <Input id="nt-category" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="WRITING (optional)" />
              </div>
              <div className="grid gap-2">
                <Label>Campaign</Label>
                <Select value={campaign} onValueChange={setCampaign}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.keys(ds?.campaigns ?? { default: {} }).length > 0
                      ? Object.entries(ds?.campaigns ?? {}).map(([key, c]) => (
                          <SelectItem key={key} value={key}>
                            {c.label || key}
                          </SelectItem>
                        ))
                      : ["default"].map((c) => (
                          <SelectItem key={c} value={c}>
                            {c}
                          </SelectItem>
                        ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-2">
              <Label>Platforms</Label>
              <div className="grid grid-cols-2 gap-2">
                {dbPlatforms.map((p) => (
                  <div key={p.id} className="flex items-center gap-2 text-sm">
                    <Checkbox id={`nt-${p.id}`} checked={platforms.includes(p.id)} onCheckedChange={(c) => togglePlatform(p.id, c === true)} />
                    <Label htmlFor={`nt-${p.id}`} className="font-normal">
                      {platformLabel(p)}
                    </Label>
                  </div>
                ))}
                <div className="flex items-center gap-2 text-sm">
                  <Checkbox
                    id="nt-auto"
                    checked={platforms.includes("auto")}
                    onCheckedChange={(c) => togglePlatform("auto", c === true)}
                  />
                  <Label htmlFor="nt-auto" className="font-normal">
                    auto — planner decides
                  </Label>
                </div>
              </div>
              {verbatim ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  The exact text is split across the slides — no rewording (essays /
                  stories / poems). Every slide shows its i/N counter.
                </p>
              ) : null}
              <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                <Label className="shrink-0">Content mode</Label>
                <div className="flex overflow-hidden rounded-md border">
                  {(["ai", "verbatim"] as const).map((m) => {
                    const active = (m === "verbatim") === verbatim
                    return (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setVerbatim(m === "verbatim")}
                        className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                          active
                            ? "bg-primary text-primary-foreground"
                            : "bg-background text-muted-foreground hover:bg-muted"
                        }`}
                      >
                        {m === "ai" ? "AI copy" : "Keep text verbatim"}
                      </button>
                    )
                  })}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                <Label className="shrink-0">Template mode</Label>
                <Select value={templateMode} onValueChange={(v) => setTemplateMode(v as typeof templateMode)}>
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Auto (template, then AI)</SelectItem>
                    <SelectItem value="template">Template only</SelectItem>
                    <SelectItem value="designer">AI designer only</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Auto tries a template first and falls back to the AI designer; Template only
                  fails a format with no matching template; AI designer only skips templates.
                </p>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                <Label className="shrink-0">Post type</Label>
                <Select value={postType} onValueChange={setPostType}>
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Editorial</SelectItem>
                    <SelectItem value="quote">Quote</SelectItem>
                    <SelectItem value="promo">Promo / announcement</SelectItem>
                    <SelectItem value="event">Event</SelectItem>
                    <SelectItem value="product">Product drop</SelectItem>
                    <SelectItem value="comparison">Comparison</SelectItem>
                    <SelectItem value="tutorial">Tutorial</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Steers the copy and optional extras (price / date / location / cta) the
                  copywriter fills.
                </p>
              </div>
              {platforms.some(isCarouselPlatform) ? (
                <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="nt-slides" className="shrink-0">
                      Slides
                    </Label>
                    <Input
                      id="nt-slides"
                      type="number"
                      min={2}
                      max={10}
                      className="w-20"
                      value={slides}
                      onChange={(e) => setSlides(Math.min(10, Math.max(2, Number(e.target.value) || 3)))}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="nt-seqaudit"
                      checked={sequenceAudit}
                      onCheckedChange={(c) => setSequenceAudit(c === true)}
                    />
                    <Label htmlFor="nt-seqaudit" className="font-normal">
                      sequence audit (vision)
                    </Label>
                  </div>
                </div>
              ) : null}
              {concretePlatforms.length > 0 ? (
                <div className="mt-4 grid gap-3">
                  <Label className="text-xs text-muted-foreground">
                    Per-platform settings (optional) — override the post-wide post
                    type / template for a platform; unlisted platforms inherit the
                    global choices above.
                  </Label>
                  {concretePlatforms.map((pid) => {
                    const family = familyOfPlatform(pid)
                    const override = platformOverrides[pid] ?? {}
                    return (
                      <div key={pid} className="grid gap-3 rounded-md border p-3">
                        <div className="flex items-center justify-between">
                          <Label className="text-sm font-medium">
                            {platformLabel(platformById[pid] ?? { id: pid, name: pid })}
                          </Label>
                          <Badge variant="outline" className="text-[10px]">
                            {family}
                          </Badge>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="grid gap-1.5">
                            <Label className="text-[11px] text-muted-foreground">
                              Post type
                            </Label>
                            <Select
                              value={override.post_type ?? "__inherit__"}
                              onValueChange={(v) =>
                                setPlatformOverride(pid, {
                                  post_type: v === "__inherit__" ? undefined : v,
                                })
                              }
                            >
                              <SelectTrigger className="w-full">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="__inherit__">
                                  Inherit ({POST_TYPE_LABELS[postType] ?? postType})
                                </SelectItem>
                                {Object.entries(POST_TYPE_LABELS).map(([key, label]) => (
                                  <SelectItem key={key} value={key}>
                                    {label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="grid gap-1.5">
                            <Label className="text-[11px] text-muted-foreground">
                              Template
                            </Label>
                            <div className="flex items-center gap-1 rounded-md border px-2 py-1.5">
                              <span className="min-w-0 flex-1 truncate text-xs">
                                {effectiveTemplateId(pid) ? (
                                  <Badge variant="outline" className="text-[10px]">
                                    {effectiveTemplateId(pid)}
                                  </Badge>
                                ) : (
                                  <span className="text-muted-foreground">Auto</span>
                                )}
                              </span>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-2 text-xs"
                                onClick={() => {
                                  setTemplateScope(pid)
                                  setStep(2)
                                }}
                              >
                                Change
                              </Button>
                              {override.template_id ? (
                                <button
                                  type="button"
                                  title="Reset to auto"
                                  className="text-muted-foreground hover:text-foreground"
                                  onClick={() =>
                                    setPlatformOverride(pid, { template_id: undefined })
                                  }
                                >
                                  <X aria-hidden="true" className="size-3.5" />
                                </button>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : null}
            </div>
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => setStep(0)}>
                Back
              </Button>
              <Button onClick={() => setStep(2)} disabled={platforms.length === 0}>
                Choose Template <ArrowRight aria-hidden="true" className="size-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {step === 2 ? (
        <div className="grid gap-4">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Label className="shrink-0 text-muted-foreground">
              Template applies to
            </Label>
            <Select value={templateScope} onValueChange={setTemplateScope}>
              <SelectTrigger className="w-64">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All platforms (post-wide)</SelectItem>
                {concretePlatforms.map((pid) => (
                  <SelectItem key={pid} value={pid}>
                    {platformLabel(platformById[pid] ?? { id: pid, name: pid })}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {scopeFamily ? (
              <Badge variant="outline" className="text-[10px]">
                {scopeFamily} family
              </Badge>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground">
            Templates for <Badge variant="outline">{ds?.name}</Badge> matching{" "}
            {scopeFamily ?? families.join(", ")}. "Auto" lets the pipeline pick.
            {Object.keys(platformOverrides).length > 0 ? (
              <>
                {" "}
                Per-platform overrides are set for{" "}
                {Object.keys(platformOverrides).length} platform
                {Object.keys(platformOverrides).length > 1 ? "s" : ""} and take
                precedence.
              </>
            ) : null}
            {verbatim ? " Verbatim mode shows text-capable templates only." : ""}
            {" "}Every carousel slide shows its i/N counter.
          </p>
          {tplLoading ? (
            <div className="flex flex-wrap justify-center gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-64 w-[280px]" />
              ))}
            </div>
          ) : templatesError ? (
            <p className="rounded-md border border-destructive/40 p-4 text-sm text-destructive">
              Failed to load templates:{" "}
              {templatesError instanceof Error ? templatesError.message : "unknown error"}
            </p>
          ) : (
            <div className="flex flex-wrap justify-center gap-4">
              <div
                role="button"
                tabIndex={0}
                onClick={() => pickTemplate(templateScope, "")}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    pickTemplate(templateScope, "")
                  }
                }}
                className={`flex w-[280px] cursor-pointer flex-col items-center justify-center gap-2 rounded-md border p-4 text-center transition-colors ${
                  templateScope === "__all__"
                    ? templateId === ""
                      ? "border-primary bg-muted/50"
                      : "hover:bg-muted/30"
                    : !platformOverrides[templateScope]?.template_id
                      ? "border-primary bg-muted/50"
                      : "hover:bg-muted/30"
                }`}
              >
                <Wand2 aria-hidden="true" className="size-6 text-muted-foreground" />
                <span className="text-sm font-medium">Auto</span>
                <span className="text-xs text-muted-foreground">Pipeline picks the best match</span>
              </div>
              {gallery.map((t) => {
                const assigned = assignedPlatforms(t.id)
                return (
                  <div
                    key={t.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => pickTemplate(templateScope, t.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        pickTemplate(templateScope, t.id)
                      }
                    }}
                    className={`flex w-[280px] cursor-pointer flex-col gap-2 rounded-md border p-2 transition-colors ${
                      isTemplateSelected(templateScope, t.id)
                        ? "border-primary"
                        : "hover:border-muted-foreground/40"
                    }`}
                  >
                    <TemplatePreviewCard t={t} />
                    <div className="flex items-center justify-between gap-2 px-1">
                      <span className="truncate text-xs font-medium">{t.id}</span>
                      <div className="flex shrink-0 items-center gap-1">
                        {assigned.length > 0 ? (
                          <Badge variant="secondary" className="text-[10px]">
                            {assigned.length} platform{assigned.length > 1 ? "s" : ""}
                          </Badge>
                        ) : null}
                        {verbatim && t.supports_text !== false ? (
                          <Badge variant="secondary" className="text-[10px]">
                            text
                          </Badge>
                        ) : null}
                        <Badge variant="outline" className="text-[10px]">
                          {t.family}
                        </Badge>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
          <div className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(1)}>
              Back
            </Button>
            <Button
              onClick={() => setStep(hasMediaStep ? 3 : 4)}
              disabled={templateMode === "template" && !templateId && gallery.length === 0}
            >
              {hasMediaStep ? "Add Media" : "Generate"}
              <ArrowRight aria-hidden="true" className="size-4" />
            </Button>
          </div>
        </div>
      ) : null}

      {step === 3 ? (
        <Card>
          <CardContent className="grid gap-4 p-6">
            <div className="flex items-center gap-2">
              <ImagePlus aria-hidden="true" className="size-4" />
              <Label>Media slots</Label>
            </div>
            <p className="text-sm text-muted-foreground">
              Upload or paste a URL per platform. Images apply to that platform's
              template; carousels distribute image i → slide i.
            </p>
            {mediaPlatforms.map((pid) => {
              const t = effectiveTemplate(pid)
              const slots = t?.image_slots ?? []
              return (
                <div key={pid} className="grid gap-3 rounded-md border p-4">
                  <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                    {platformLabel(platformById[pid] ?? { id: pid, name: pid })} ·{" "}
                    {t?.id ?? "auto"}
                  </Label>
                  {slots.map((slot) => {
                    const entry = media[pid]?.[slot.key]
                    return (
                      <div key={slot.key} className="grid gap-2">
                        <div className="grid grid-cols-2 gap-3">
                          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed p-3 text-sm text-muted-foreground hover:bg-muted/30">
                            <ImagePlus aria-hidden="true" className="size-4" />
                            {entry?.data ? "Replace image" : "Upload image"}
                            <input
                              type="file"
                              accept="image/png,image/jpeg,image/webp,image/gif"
                              className="hidden"
                              onChange={(e) => {
                                const f = e.target.files?.[0]
                                if (f) void handleMediaUpload(pid, slot.key, f)
                              }}
                            />
                          </label>
                          <div className="flex items-center gap-2">
                            <Link2 aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
                            <Input
                              placeholder="https://… image URL"
                              value={entry?.url ?? ""}
                              onChange={(e) =>
                                setSlotMedia(pid, slot.key, { url: e.target.value, data: undefined })
                              }
                            />
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <Input
                            placeholder="Alt text (optional)"
                            value={entry?.alt ?? ""}
                            onChange={(e) => setSlotMedia(pid, slot.key, { alt: e.target.value })}
                          />
                          <Select
                            value={entry?.placement ?? "auto"}
                            onValueChange={(v) => setSlotMedia(pid, slot.key, { placement: v })}
                          >
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Placement" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="auto">Auto</SelectItem>
                              <SelectItem value="background">Background (full-bleed)</SelectItem>
                              <SelectItem value="top-left">Top-left</SelectItem>
                              <SelectItem value="center">Center</SelectItem>
                              <SelectItem value="bottom-right">Bottom-right</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <Input
                          placeholder="Description / placement note (optional)"
                          value={entry?.description ?? ""}
                          onChange={(e) =>
                            setSlotMedia(pid, slot.key, { description: e.target.value })
                          }
                        />
                      </div>
                    )
                  })}
                </div>
              )
            })}
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button onClick={() => void submit()} disabled={submitting}>
                {submitting ? (
                  <>
                    <Loader2 aria-hidden="true" className="size-4 animate-spin" /> Queuing…
                  </>
                ) : (
                  <>
                    Generate <ArrowRight aria-hidden="true" className="size-4" />
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {step === 4 ? (
        <Card>
          <CardContent className="grid gap-4 p-6">
            <p className="text-sm text-muted-foreground">
              {templateId ? `Using ${templateId}` : "Auto template"} on {platforms.join(", ")} for{" "}
              {ds?.name}.
            </p>
            <div className="flex justify-end">
              <Button onClick={() => void submit()} disabled={submitting}>
                {submitting ? (
                  <>
                    <Loader2 aria-hidden="true" className="size-4 animate-spin" /> Queuing…
                  </>
                ) : (
                  <>
                    Generate <ArrowRight aria-hidden="true" className="size-4" />
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

function TemplatePreviewCard({ t }: { t: Template }) {
  const { data, failed, retry } = useTemplatePreview(t.id)
  const dims = FAMILY_DIMS[t.family] ?? FAMILY_DIMS.square
  if (data) return <PreviewFrame html={data.html} family={t.family} />
  if (failed) {
    return (
      <button
        onClick={retry}
        className="flex w-full items-center justify-center rounded-md border bg-muted/20 text-xs text-muted-foreground hover:underline"
        style={{ height: Math.round((dims.height / dims.width) * 264) }}
      >
        Preview failed — retry
      </button>
    )
  }
  return (
    <div
      className="flex items-center justify-center rounded-md border bg-muted/20"
      style={{ width: 264, height: Math.round((dims.height / dims.width) * 264) }}
    >
      <Loader2 aria-hidden="true" className="size-4 animate-spin text-muted-foreground" />
    </div>
  )
}
