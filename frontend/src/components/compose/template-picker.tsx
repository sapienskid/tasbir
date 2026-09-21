import { memo, useMemo } from "react"
import useSWR from "swr"
import { Check, Loader2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ScaledFrame } from "@/components/tasks/preview-frame"
import { useTemplatePreview } from "@/hooks/use-library"
import { getTemplate, type ComposeGround, type ComposeMediaPosition, type Template } from "@/lib/api"
import { FAMILY_DIMS } from "@/lib/platforms"
import { detectTemplateElements } from "@/lib/template-elements"
import { templateHasMedia } from "./model"

const CARD_W = 148
const CARD_H = 190

/** Gallery card: the template's cached sample render (same as New Task). */
const TemplateCard = memo(function TemplateCard({
  t,
  selected,
  ground,
  onPick,
}: {
  t: Template
  selected: boolean
  ground: ComposeGround
  onPick: () => void
}) {
  const { data, failed, retry } = useTemplatePreview(t.id)
  const dims = FAMILY_DIMS[t.family] ?? FAMILY_DIMS.square
  const scale = Math.min(CARD_W / dims.width, CARD_H / dims.height)
  const box = { width: Math.round(dims.width * scale), height: Math.round(dims.height * scale) }
  const offGround = (t.grounds?.length ?? 0) > 0 && !t.grounds.includes(ground)
  return (
    <div
      role="radio"
      aria-checked={selected}
      tabIndex={0}
      onClick={onPick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onPick()
        }
      }}
      className={`relative flex cursor-pointer flex-col gap-1.5 rounded-md border p-1.5 transition-colors ${
        selected ? "border-primary ring-1 ring-primary" : "hover:border-muted-foreground/40"
      }`}
    >
      {data ? (
        <ScaledFrame html={data.html} width={dims.width} height={dims.height} maxWidth={CARD_W} maxHeight={CARD_H} />
      ) : failed ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            retry()
          }}
          className="mx-auto flex items-center justify-center rounded-md border bg-muted/20 text-[10px] text-muted-foreground hover:underline"
          style={box}
        >
          Preview failed — retry
        </button>
      ) : (
        <div className="mx-auto flex items-center justify-center rounded-md border bg-muted/20" style={box}>
          <Loader2 aria-hidden="true" className="size-4 animate-spin text-muted-foreground" />
        </div>
      )}
      <div className="flex items-center justify-between gap-1 px-0.5">
        <span className="truncate text-[11px] font-medium" title={t.name || t.id}>
          {t.name || t.id}
        </span>
        {selected ? <Check aria-hidden="true" className="size-3.5 shrink-0 text-primary" /> : null}
      </div>
      <div className="flex flex-wrap gap-1 px-0.5">
        {templateHasMedia(t) ? (
          <Badge variant="secondary" className="px-1 text-[9px]">
            media
          </Badge>
        ) : null}
        {offGround ? (
          <Badge variant="outline" className="px-1 text-[9px]">
            {t.grounds.join("/")} only
          </Badge>
        ) : null}
      </div>
    </div>
  )
})

/**
 * Template tab: gallery of the design system's templates for the post's
 * platform family, then element toggles + media position for the selection.
 */
export function TemplatePicker({
  family,
  templates,
  loading,
  selected,
  ground,
  hidden,
  mediaPosition,
  multiSlide,
  onPick,
  onHidden,
  onMediaPosition,
  onApplyAll,
  showApplyAll = true,
}: {
  family: string
  templates: Template[]
  loading: boolean
  selected: Template | undefined
  ground: ComposeGround
  hidden: string[] | null
  mediaPosition: ComposeMediaPosition
  multiSlide: boolean
  onPick: (id: string) => void
  onHidden: (hidden: string[] | null) => void
  onMediaPosition: (p: ComposeMediaPosition) => void
  onApplyAll: (scope: "post" | "all") => void
  /** Hide the bulk-apply buttons (single-post editors apply directly). */
  showApplyAll?: boolean
}) {
  // The list payload has no HTML — fetch the selected template for toggles.
  const { data: full } = useSWR(
    selected ? `/templates/${selected.id}` : null,
    () => getTemplate(selected!.id),
    { revalidateOnFocus: false, dedupingInterval: 60_000 }
  )
  const elements = useMemo(() => detectTemplateElements(full?.html ?? ""), [full?.html])
  const effectiveHidden = hidden ?? selected?.hidden_elements ?? []

  return (
    <div className="grid gap-4">
      <div className="grid gap-2">
        <div className="flex items-center justify-between gap-2">
          <span id="tpl-gallery-label" className="text-xs text-muted-foreground">
            {family} templates · {templates.length}
          </span>
          {selected && showApplyAll ? (
            <div className="flex gap-1">
              {multiSlide ? (
                <Button size="xs" variant="outline" onClick={() => onApplyAll("post")}>
                  Apply to all slides
                </Button>
              ) : null}
              <Button size="xs" variant="outline" onClick={() => onApplyAll("all")}>
                Apply to all posts
              </Button>
            </div>
          ) : null}
        </div>
        {loading ? (
          <p className="text-xs text-muted-foreground">Loading templates…</p>
        ) : templates.length === 0 ? (
          <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
            This design system has no {family} templates. Pick another platform or design system.
          </p>
        ) : (
          <div
            role="radiogroup"
            aria-labelledby="tpl-gallery-label"
            className="grid max-h-[26rem] grid-cols-2 gap-2 overflow-y-auto pr-1"
          >
            {templates.map((t) => (
              <TemplateCard
                key={t.id}
                t={t}
                ground={ground}
                selected={selected?.id === t.id}
                onPick={() => onPick(t.id)}
              />
            ))}
          </div>
        )}
      </div>

      {selected ? (
        <div className="grid gap-3 rounded-md border p-3">
          <div className="flex items-center justify-between">
            <Label className="text-xs text-muted-foreground">Show / hide elements</Label>
            {hidden !== null ? (
              <Button size="xs" variant="ghost" onClick={() => onHidden(null)}>
                Template default
              </Button>
            ) : null}
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
                const id = `el-${el.name}`
                return (
                  <label key={el.name} htmlFor={id} className="flex items-center gap-2 text-xs">
                    <input
                      id={id}
                      type="checkbox"
                      checked={!effectiveHidden.includes(el.name)}
                      onChange={(e) =>
                        onHidden(
                          e.target.checked
                            ? effectiveHidden.filter((n) => n !== el.name)
                            : [...effectiveHidden, el.name]
                        )
                      }
                    />
                    {el.label}
                  </label>
                )
              })}
            </div>
          )}
          {templateHasMedia(selected) ? (
            <div className="grid gap-1.5">
              <Label htmlFor="tpl-media-pos" className="text-xs text-muted-foreground">
                Media position
              </Label>
              <Select value={mediaPosition} onValueChange={(v) => onMediaPosition(v as ComposeMediaPosition)}>
                <SelectTrigger id="tpl-media-pos" className="w-40">
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
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
