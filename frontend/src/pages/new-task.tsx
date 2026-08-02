import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { ArrowLeft, ArrowRight, Check, ImagePlus, Link2, Loader2, Wand2 } from "lucide-react"
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
  previewTemplate,
  uploadMedia,
  type GenerateResponse,
  type DesignSystem,
  type Template,
} from "@/lib/api"
import { useDesignSystems, useTemplates } from "@/hooks/use-library"
import { usePlatforms } from "@/hooks/use-platforms"
import { familyOfPlatform } from "@/lib/platforms"
import { PreviewFrame, FAMILY_DIMS } from "@/components/tasks/preview-frame"

function isCarouselPlatform(p: string): boolean {
  return p === "instagram-carousel" || p === "instagram-carousel-portrait"
}

const STEPS = ["Design System", "Content", "Template", "Media"]

interface MediaEntry {
  data?: string
  mime?: string
  url?: string
  alt: string
}

export default function NewTaskPage() {
  const navigate = useNavigate()
  const { data: systems, isLoading: dsLoading } = useDesignSystems()
  const { platforms: dbPlatforms } = usePlatforms()

  const [step, setStep] = useState(0)
  const [dsId, setDsId] = useState<string>("")
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")
  const [category, setCategory] = useState("")
  const [campaign, setCampaign] = useState("default")
  const [platforms, setPlatforms] = useState<string[]>(["instagram-square"])
  const [slides, setSlides] = useState(3)
  const [ratio, setRatio] = useState<"square" | "portrait" | "auto">("square")
  const [sequenceAudit, setSequenceAudit] = useState(false)
  const [templateId, setTemplateId] = useState<string>("")
  const [media, setMedia] = useState<Record<string, MediaEntry>>({})
  const [submitting, setSubmitting] = useState(false)

  const activeSystems = useMemo(
    () => (systems ?? []).filter((s) => s.is_active),
    [systems]
  )
  const ds: DesignSystem | undefined = activeSystems.find((s) => s.id === dsId)
  const { data: templates, isLoading: tplLoading } = useTemplates(dsId || null)

  // Auto-select the only (or default) design system.
  useEffect(() => {
    if (!dsId && activeSystems.length > 0) {
      const preferred = activeSystems.find((s) => s.id === "default") ?? activeSystems[0]
      setDsId(preferred.id)
    }
  }, [activeSystems, dsId])

  const families = useMemo(
    () => [...new Set(platforms.map((p) => familyOfPlatform(p)).filter(Boolean))],
    [platforms]
  )
  const gallery = useMemo(
    () => (templates ?? []).filter((t) => families.includes(t.family)),
    [templates, families]
  )
  const selected = useMemo(
    () => (templates ?? []).find((t) => t.id === templateId),
    [templates, templateId]
  )

  function togglePlatform(p: string, checked: boolean) {
    setPlatforms((prev) => (checked ? [...prev, p] : prev.filter((x) => x !== p)))
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
      const images = Object.entries(media)
        .filter(([, v]) => v.data || v.url)
        .map(([key, v]) => ({
          data: v.data || undefined,
          mime: v.mime,
          url: v.url || undefined,
          alt: v.alt || `Image ${key}`,
          description: "",
          placement: "auto",
        }))
      const hasCarousel = platforms.some(isCarouselPlatform)
      const res = await apiRequest<GenerateResponse>("/generate", {
        method: "POST",
        body: JSON.stringify({
          content,
          title,
          category: category || undefined,
          campaign,
          platforms,
          slides: hasCarousel ? slides : undefined,
          ratio,
          sequence_audit: sequenceAudit,
          design_system_id: dsId,
          template_id: templateId,
          images,
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

  async function handleMediaUpload(slotKey: string, file: File) {
    try {
      const res = await uploadMedia(file)
      setMedia((prev) => ({ ...prev, [slotKey]: { data: res.data, mime: res.mime, alt: "" } }))
      toast.success("Image uploaded")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed")
    }
  }

  const hasMediaStep = Boolean(selected?.image_slots?.length)

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
            <ArrowLeft className="size-4" />
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
              {i < step || (i === 3 && !hasMediaStep && step === 3) ? <Check className="size-3" /> : i + 1}
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
                onClick={() => setDsId(s.id)}
                className={`flex items-center justify-between rounded-md border p-4 text-left transition-colors ${
                  dsId === s.id ? "border-primary bg-muted/50" : "hover:bg-muted/30"
                }`}
              >
                <div>
                  <p className="font-medium">{s.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {s.description || s.id} · {s.template_count ?? "?"} templates
                  </p>
                </div>
                {dsId === s.id ? <Check className="size-4 text-primary" /> : null}
              </button>
            ))}
            <div className="flex justify-end">
              <Button onClick={() => setStep(1)} disabled={!dsId}>
                Continue <ArrowRight className="size-4" />
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
              <Textarea id="nt-content" className="min-h-40" value={content} onChange={(e) => setContent(e.target.value)} placeholder="Paste the full article / blog post..." />
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
                      {p.name || p.id}
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
                    <Label htmlFor="nt-ratio" className="shrink-0">
                      Ratio
                    </Label>
                    <Select value={ratio} onValueChange={(v) => setRatio(v as typeof ratio)}>
                      <SelectTrigger id="nt-ratio" className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="square">square 1:1</SelectItem>
                        <SelectItem value="portrait">portrait 4:5</SelectItem>
                        <SelectItem value="auto">auto</SelectItem>
                      </SelectContent>
                    </Select>
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
            </div>
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => setStep(0)}>
                Back
              </Button>
              <Button onClick={() => setStep(2)} disabled={platforms.length === 0}>
                Choose Template <ArrowRight className="size-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {step === 2 ? (
        <div className="grid gap-4">
          <p className="text-sm text-muted-foreground">
            Templates for <Badge variant="outline">{ds?.name}</Badge> matching{" "}
            {families.join(", ")}. "Auto" lets the pipeline pick.
          </p>
          {tplLoading ? (
            <div className="flex flex-wrap justify-center gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-64 w-[280px]" />
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap justify-center gap-4">
              <div
                role="button"
                tabIndex={0}
                onClick={() => setTemplateId("")}
                onKeyDown={(e) => e.key === "Enter" && setTemplateId("")}
                className={`flex w-[280px] cursor-pointer flex-col items-center justify-center gap-2 rounded-md border p-4 text-center transition-colors ${
                  templateId === "" ? "border-primary bg-muted/50" : "hover:bg-muted/30"
                }`}
              >
                <Wand2 className="size-6 text-muted-foreground" />
                <span className="text-sm font-medium">Auto</span>
                <span className="text-xs text-muted-foreground">Pipeline picks the best match</span>
              </div>
              {gallery.map((t) => (
                <div
                  key={t.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setTemplateId(t.id)}
                  onKeyDown={(e) => e.key === "Enter" && setTemplateId(t.id)}
                  className={`flex w-[280px] cursor-pointer flex-col gap-2 rounded-md border p-2 transition-colors ${
                    templateId === t.id ? "border-primary" : "hover:border-muted-foreground/40"
                  }`}
                >
                  <TemplatePreviewCard t={t} />
                  <div className="flex items-center justify-between px-1">
                    <span className="truncate text-xs font-medium">{t.id}</span>
                    <Badge variant="outline" className="text-[10px]">
                      {t.family}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(1)}>
              Back
            </Button>
            <Button onClick={() => setStep(hasMediaStep ? 3 : 4)} disabled={!templateId && gallery.length === 0}>
              {hasMediaStep ? "Add Media" : "Generate"}
              <ArrowRight className="size-4" />
            </Button>
          </div>
        </div>
      ) : null}

      {step === 3 ? (
        <Card>
          <CardContent className="grid gap-4 p-6">
            <div className="flex items-center gap-2">
              <ImagePlus className="size-4" />
              <Label>Media slots</Label>
            </div>
            <p className="text-sm text-muted-foreground">
              This template declares {selected?.image_slots.length} image slot(s) — upload or paste a URL for each.
            </p>
            {(selected?.image_slots ?? []).map((slot, i) => {
              const entry = media[slot.key]
              return (
                <div key={slot.key} className="grid gap-2 rounded-md border p-4">
                  <Label className="text-xs uppercase tracking-wide text-muted-foreground">
                    Slot {slot.key} · {slot.hint}
                  </Label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed p-3 text-sm text-muted-foreground hover:bg-muted/30">
                      <ImagePlus className="size-4" />
                      {entry?.data ? "Replace image" : "Upload image"}
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp,image/gif"
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0]
                          if (f) void handleMediaUpload(slot.key, f)
                        }}
                      />
                    </label>
                    <div className="flex items-center gap-2">
                      <Link2 className="size-4 shrink-0 text-muted-foreground" />
                      <Input
                        placeholder="https://… image URL"
                        value={entry?.url ?? ""}
                        onChange={(e) =>
                          setMedia((prev) => ({ ...prev, [slot.key]: { ...prev[slot.key], url: e.target.value } }))
                        }
                      />
                    </div>
                  </div>
                  <Input
                    placeholder={`Alt text for slot ${slot.key}${i === 0 ? " (optional)" : ""}`}
                    value={entry?.alt ?? ""}
                    onChange={(e) =>
                      setMedia((prev) => ({ ...prev, [slot.key]: { ...prev[slot.key], alt: e.target.value } }))
                    }
                  />
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
                    <Loader2 className="size-4 animate-spin" /> Queuing…
                  </>
                ) : (
                  <>
                    Generate <ArrowRight className="size-4" />
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
                    <Loader2 className="size-4 animate-spin" /> Queuing…
                  </>
                ) : (
                  <>
                    Generate <ArrowRight className="size-4" />
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
  return (
    <TemplatePreviewInner t={t} />
  )
}

function TemplatePreviewInner({ t }: { t: Template }) {
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
      <Loader2 className="size-4 animate-spin text-muted-foreground" />
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
