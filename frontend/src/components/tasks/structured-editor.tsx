import { memo, useEffect, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { Check, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TextFields } from "@/components/compose/text-fields"
import { MediaPicker } from "@/components/compose/media-picker"
import {
  ALL_FIELDS,
  FALLBACK_FIELDS,
  getField,
  isFieldKey,
  templateFields,
  templateHasMedia,
  templateMediaKinds,
  type FieldKey,
} from "@/components/compose/model"
import { ScaledFrame } from "@/components/tasks/preview-frame"
import { useTemplatePreview, useTemplates } from "@/hooks/use-library"
import { detectTemplateElements } from "@/lib/template-elements"
import {
  getTemplate,
  type ComposeCopy,
  type ComposeExtraKey,
  type ComposeGround,
  type ComposeMedia,
  type ComposeMediaPosition,
  type RefillRequest,
  type Template,
} from "@/lib/api"
import { FAMILY_DIMS } from "@/lib/platforms"

function emptyCopy(): ComposeCopy {
  return {
    kicker: "",
    headline: "",
    subhead: "",
    body: "",
    tagline: "",
    extra: { price: "", cta: "", date: "", location: "", stat: "", source: "" },
  }
}

/** Rendered slots → form copy (extra.* keys map into copy.extra). */
function copyFromSlots(slots: Record<string, string>): ComposeCopy {
  const copy = emptyCopy()
  for (const [k, v] of Object.entries(slots)) {
    if (k.startsWith("extra.")) {
      const key = k.slice(6) as ComposeExtraKey
      if (key in copy.extra) copy.extra[key] = v
    } else if (k in copy) {
      (copy as unknown as Record<string, string>)[k] = v
    }
  }
  return copy
}

const TemplateOption = memo(function TemplateOption({
  t,
  selected,
  onPick,
  disabled,
}: {
  t: Template
  selected: boolean
  onPick: () => void
  disabled: boolean
}) {
  const { data, failed, retry } = useTemplatePreview(t.id)
  const dims = FAMILY_DIMS[t.family] ?? FAMILY_DIMS.square
  return (
    <div
      role="radio"
      aria-checked={selected}
      aria-disabled={disabled}
      tabIndex={disabled ? -1 : 0}
      onClick={() => {
        if (!disabled) onPick()
      }}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled) {
          e.preventDefault()
          onPick()
        }
      }}
      className={`relative flex cursor-pointer flex-col gap-1.5 rounded-md border p-1.5 transition-colors ${
        selected
          ? "border-primary ring-1 ring-primary"
          : "hover:border-muted-foreground/40"
      } ${disabled ? "pointer-events-none opacity-50" : ""}`}
    >
      {data ? (
        <ScaledFrame html={data.html} width={dims.width} height={dims.height} maxWidth={148} maxHeight={188} />
      ) : failed ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            retry()
          }}
          className="mx-auto flex min-h-24 w-full items-center justify-center rounded-md border bg-muted/20 text-[10px] text-muted-foreground hover:underline"
        >
          Preview failed — retry
        </button>
      ) : (
        <div className="mx-auto flex min-h-24 w-full items-center justify-center rounded-md border bg-muted/20">
          <Loader2 aria-hidden="true" className="size-4 animate-spin text-muted-foreground" />
        </div>
      )}
      <div className="flex items-center justify-between gap-1 px-0.5">
        <span className="truncate text-[11px] font-medium" title={t.name || t.id}>
          {t.name || t.id}
        </span>
        {selected ? <Check aria-hidden="true" className="size-3.5 shrink-0 text-primary" /> : null}
      </div>
    </div>
  )
})

/**
 * Compose-style structured panel for a template-built agent post: Template
 * gallery + element toggles on one tab, slot text fields (with the same
 * character caps as Manual Compose) on the other. Every change goes through
 * the refill endpoint — raw HTML is never touched here.
 */
export function StructuredEditor({
  format,
  slots,
  templateId,
  designSystemId,
  ground,
  family,
  refilling,
  onRefill,
}: {
  format: string
  slots: Record<string, string>
  templateId: string
  designSystemId: string
  ground: ComposeGround
  family: string
  refilling: boolean
  onRefill: (body: RefillRequest) => Promise<void>
}) {
  const [tab, setTab] = useState<"template" | "text" | "media">("text")
  const { data: templates, isLoading: templatesLoading } = useTemplates(designSystemId, family)
  const { data: full } = useSWR(templateId ? `/templates/${templateId}` : null, () =>
    getTemplate(templateId)
  )

  const template = (templates ?? []).find((t) => t.id === templateId)
  const { fields, fieldsFallback } = useMemo<{ fields: FieldKey[]; fieldsFallback: boolean }>(() => {
    const fromTemplate = template ? templateFields(template) : []
    if (fromTemplate.length > 0) return { fields: fromTemplate, fieldsFallback: false }
    const fromSlots = Object.keys(slots).filter(isFieldKey)
    if (fromSlots.length > 0) return { fields: fromSlots, fieldsFallback: false }
    return { fields: [...FALLBACK_FIELDS], fieldsFallback: true }
  }, [template, slots])

  const [copy, setCopy] = useState<ComposeCopy>(() => copyFromSlots(slots))
  const copyRef = useRef(copy)
  copyRef.current = copy
  const [textDirty, setTextDirty] = useState(false)
  const [saveState, setSaveState] = useState<"clean" | "pending" | "saving" | "error">("clean")
  const [lastSaved, setLastSaved] = useState<string | null>(null)
  // Slots the form was built on + which fields the user touched since.
  // Only touched fields are ever sent, so form typing and inline preview
  // edits converge instead of clobbering each other.
  const baseRef = useRef<Record<string, string>>(slots)
  const touchedRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    if (!textDirty) {
      if (JSON.stringify(slots) !== JSON.stringify(baseRef.current)) {
        setCopy(copyFromSlots(slots))
        baseRef.current = slots
      }
    }
    // While dirty the base stays put — touched-field diffing stays valid.
  }, [slots, textDirty])

  function trackTouched(next: ComposeCopy) {
    const base = copyFromSlots(baseRef.current)
    const touched = touchedRef.current
    for (const f of ALL_FIELDS) {
      if (getField(next, f) !== getField(base, f)) touched.add(f)
      else touched.delete(f)
    }
    const dirty = touched.size > 0
    setTextDirty(dirty)
    if (dirty) setSaveState((s) => (s === "saving" ? s : "pending"))
    else setSaveState("clean")
  }

  function handleCopyChange(next: ComposeCopy) {
    setCopy(next)
    trackTouched(next)
  }

  /** Send touched fields. Throws nothing — status is shown inline. */
  async function fireText() {
    const keys = [...touchedRef.current]
    if (keys.length === 0 || saveState === "saving") return
    const cur = copyRef.current
    const body: Record<string, string> = {}
    for (const k of keys) body[k] = getField(cur, k as FieldKey)
    setSaveState("saving")
    try {
      await onRefill({ slots: body })
      baseRef.current = { ...baseRef.current, ...body }
      for (const k of keys) touchedRef.current.delete(k)
      const stillDirty = touchedRef.current.size > 0
      setTextDirty(stillDirty)
      if (!stillDirty) {
        setSaveState("clean")
        setLastSaved(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))
      } else {
        setSaveState("pending")
      }
    } catch {
      setSaveState("error")
    }
  }

  // Auto-save like Manual Compose's live preview: debounced after typing
  // stops, paused while a refill is in flight (it re-fires after).
  useEffect(() => {
    if (!textDirty || refilling) return
    const t = window.setTimeout(() => void fireText(), 1200)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copy, textDirty, refilling])

  function revertText() {
    setCopy(copyFromSlots(slots))
    baseRef.current = slots
    touchedRef.current.clear()
    setTextDirty(false)
    setSaveState("clean")
  }

  const elements = useMemo(() => detectTemplateElements(full?.html ?? ""), [full?.html])
  const [hidden, setHidden] = useState<string[] | null>(null)
  useEffect(() => {
    setHidden(null)
  }, [templateId])
  const effectiveHidden = hidden ?? full?.hidden_elements ?? template?.hidden_elements ?? []

  const [mediaPosition, setMediaPosition] = useState<ComposeMediaPosition>(
    (template?.media_position as ComposeMediaPosition) ?? "auto"
  )
  useEffect(() => {
    setMediaPosition((template?.media_position as ComposeMediaPosition) ?? "auto")
  }, [templateId, template?.media_position])

  const hasMedia = templateHasMedia(template)
  const mediaKinds = template ? templateMediaKinds(template) : []
  const orientation = family === "landscape" ? "landscape" : family === "square" ? "square" : "portrait"
  const [media, setMedia] = useState<ComposeMedia>({ kind: "none" })
  const mediaReady = media.kind !== "none"

  function applyMedia() {
    if (!mediaReady) return
    const body: Record<string, string> =
      media.kind === "upload"
        ? { kind: "upload", data: media.data, mime: media.mime, alt: media.alt }
        : media.kind === "photo"
          ? {
              kind: "photo",
              url: media.url,
              credit: media.credit,
              provider: media.provider,
              photographer: media.photographer,
              license: media.license,
            }
          : { kind: "illustration", style: media.style, seed: media.seed };
    (async () => {
      try {
        await onRefill({ media: body })
        setMedia({ kind: "none" })
        toast.success("Media updated — re-rendered")
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Refill failed")
      }
    })()
  }

  async function run(body: RefillRequest, okMsg: string) {
    try {
      await onRefill(body)
      toast.success(okMsg)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Refill failed")
    }
  }

  const hiddenCount = effectiveHidden.length

  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as "template" | "text" | "media")} className="gap-3">
      <TabsList className="w-full">
        <TabsTrigger value="template">Template</TabsTrigger>
        <TabsTrigger value="text">Text</TabsTrigger>
        <TabsTrigger value="media" disabled={!hasMedia} title={hasMedia ? undefined : "This template has no media slot"}>
          Media
        </TabsTrigger>
      </TabsList>

      <TabsContent value="template" className="grid gap-3">
        {templatesLoading ? (
          <p className="text-xs text-muted-foreground">Loading templates…</p>
        ) : (templates ?? []).length === 0 ? (
          <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
            No {family} templates in this design system.
          </p>
        ) : (
          <div
            role="radiogroup"
            aria-label="Templates"
            className="grid max-h-72 grid-cols-2 gap-2 overflow-y-auto pr-1"
          >
            {(templates ?? []).map((t) => (
              <TemplateOption
                key={t.id}
                t={t}
                selected={t.id === templateId}
                disabled={refilling}
                onPick={() => {
                  if (t.id !== templateId) void run({ template_id: t.id }, `Switched to ${t.name || t.id}`)
                }}
              />
            ))}
          </div>
        )}

        <div className="grid gap-3 rounded-md border p-3">
          <div className="flex items-center justify-between">
            <Label className="text-xs text-muted-foreground">
              Show / hide elements{hiddenCount > 0 ? ` (${hiddenCount} hidden)` : ""}
            </Label>
            <span className="text-[10px] text-muted-foreground">applies instantly</span>
          </div>
          {!full ? (
            <p className="text-xs text-muted-foreground">Loading elements…</p>
          ) : elements.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No optional elements — this template renders everything it receives.
            </p>
          ) : (
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              {elements.map((el) => {
                const id = `ag-el-${format}-${el.name}`
                return (
                  <label key={el.name} htmlFor={id} className="flex items-center gap-2 text-xs">
                    <input
                      id={id}
                      type="checkbox"
                      disabled={refilling}
                      checked={!effectiveHidden.includes(el.name)}
                      onChange={(e) => {
                        const next = e.target.checked
                          ? effectiveHidden.filter((n) => n !== el.name)
                          : [...effectiveHidden, el.name]
                        setHidden(next)
                        void run({ hidden: next }, "Elements updated")
                      }}
                    />
                    {el.label}
                  </label>
                )
              })}
            </div>
          )}
          {hasMedia ? (
            <div className="grid gap-1.5">
              <Label htmlFor={`ag-media-pos-${format}`} className="text-xs text-muted-foreground">
                Media position
              </Label>
              <Select
                value={mediaPosition}
                disabled={refilling}
                onValueChange={(v) => {
                  const pos = v as ComposeMediaPosition
                  setMediaPosition(pos)
                  void run({ media_position: pos }, "Media position updated")
                }}
              >
                <SelectTrigger id={`ag-media-pos-${format}`} className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto</SelectItem>
                  <SelectItem value="left">Left</SelectItem>
                  <SelectItem value="right">Right</SelectItem>
                  <SelectItem value="top">Top</SelectItem>
                  <SelectItem value="bottom">Bottom</SelectItem>
                </SelectContent>
              </Select>
            </div>
          ) : (
            <p className="text-[11px] text-muted-foreground">
              Photos and illustrations are baked in and preserved on every edit.
            </p>
          )}
        </div>
      </TabsContent>

      <TabsContent value="text" className="grid gap-3">
        <TextFields
          fields={fields}
          copy={copy}
          hidden={effectiveHidden}
          fallback={fieldsFallback}
          onChange={handleCopyChange}
        />
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] text-muted-foreground" role="status">
            {saveState === "saving" || refilling
              ? "Saving…"
              : saveState === "error"
                ? "Save failed — will retry on next keystroke"
                : lastSaved
                  ? `Saved ${lastSaved}`
                  : "Edits save automatically"}
          </span>
          {saveState === "saving" || refilling ? (
            <Loader2 aria-hidden="true" className="size-4 animate-spin text-muted-foreground" />
          ) : saveState === "error" ? (
            <Button size="xs" variant="outline" onClick={() => void fireText()}>
              Retry now
            </Button>
          ) : textDirty ? (
            <Button size="xs" variant="ghost" onClick={revertText}>
              Revert
            </Button>
          ) : null}
        </div>
      </TabsContent>

      <TabsContent value="media" className="grid gap-3">
        <p className="text-[11px] text-muted-foreground">
          Baked media stays until you pick a replacement below and apply it.
        </p>
        <MediaPicker
          media={media}
          mediaKinds={mediaKinds}
          ground={ground}
          orientation={orientation}
          multiSlide={false}
          onChange={setMedia}
          onApplyAll={() => {}}
          hideApply
        />
        <div className="flex justify-end">
          <Button size="sm" disabled={refilling || !mediaReady} onClick={applyMedia}>
            {refilling ? <Loader2 aria-hidden="true" className="size-4 animate-spin" /> : null}
            Apply media
          </Button>
        </div>
      </TabsContent>
    </Tabs>
  )
}
