import { memo, useEffect, useRef, useState } from "react"
import { AlertTriangle, Loader2 } from "lucide-react"
import { ScaledFrame } from "@/components/tasks/preview-frame"
import { useSlidePreview } from "@/hooks/use-compose"
import type { ComposePreviewRequest } from "@/lib/api"
import { formatDims } from "@/lib/platforms"

const THUMB_W = 60
const THUMB_H = 76

/**
 * Rail thumbnail of one slide. Renders lazily (only once scrolled into view)
 * through the same cached preview call as the main canvas.
 */
export const SlideThumb = memo(function SlideThumb({
  req,
  label,
  selected,
  onSelect,
}: {
  req: ComposePreviewRequest
  label: string
  selected: boolean
  onSelect: () => void
}) {
  const ref = useRef<HTMLButtonElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el || visible) return
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) setVisible(true)
      },
      { rootMargin: "120px" }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [visible])

  const { data, error, loading } = useSlidePreview(req, { delay: 900, enabled: visible })
  const dims = data ?? formatDims(req.platform)
  const scale = Math.min(THUMB_W / dims.width, THUMB_H / dims.height)
  const boxW = Math.round(dims.width * scale)
  const boxH = Math.round(dims.height * scale)

  return (
    <button
      ref={ref}
      type="button"
      onClick={onSelect}
      aria-label={label}
      aria-pressed={selected}
      title={label}
      className={`relative shrink-0 rounded-md p-0.5 outline-offset-2 transition-colors ${
        selected ? "ring-2 ring-primary" : "ring-1 ring-transparent hover:ring-border"
      }`}
    >
      {data ? (
        <ScaledFrame
          html={data.html}
          width={data.width}
          height={data.height}
          maxWidth={THUMB_W}
          maxHeight={THUMB_H}
        />
      ) : (
        <div
          className="flex items-center justify-center rounded-md border bg-muted/30 text-[10px] text-muted-foreground"
          style={{ width: boxW, height: boxH }}
        >
          {error ? (
            <AlertTriangle aria-hidden="true" className="size-3.5 text-destructive" />
          ) : loading ? (
            <Loader2 aria-hidden="true" className="size-3.5 animate-spin" />
          ) : !req.slide.template_id ? (
            "—"
          ) : null}
        </div>
      )}
      <span className="absolute bottom-1 left-1 rounded-sm bg-background/90 px-1 text-[9px] font-medium tabular-nums">
        {req.slide_index}
      </span>
    </button>
  )
})
