import { memo, useEffect, useImperativeHandle, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Maximize2, Minus, Plus } from "lucide-react"

export const FAMILY_DIMS: Record<string, { width: number; height: number }> = {
  square: { width: 1080, height: 1080 },
  portrait: { width: 1080, height: 1350 },
  story: { width: 1080, height: 1920 },
  landscape: { width: 1200, height: 627 },
}

/** Pixel dimensions per platform format (mirrors platforms.yaml). */
export const FORMAT_DIMS: Record<string, { width: number; height: number }> = {
  "instagram-square": { width: 1080, height: 1080 },
  "instagram-portrait": { width: 1080, height: 1350 },
  "instagram-story": { width: 1080, height: 1920 },
  "linkedin-post": { width: 1200, height: 627 },
  "twitter-card": { width: 1200, height: 675 },
  "facebook-post": { width: 1200, height: 630 },
  "pinterest-pin": { width: 1000, height: 1500 },
}

export function formatDims(format: string): { width: number; height: number } {
  return FORMAT_DIMS[format] ?? FAMILY_DIMS.square
}

const CARD_WIDTH = 264
const MAX_CARD_HEIGHT = 340

/**
 * Live HTML preview of a full-pixel document, scaled to fit a box. The iframe
 * gets the native-size document via srcdoc so Google Fonts + tokens render
 * exactly as the pipeline would; a CSS transform scales it into the box.
 */
export const ScaledFrame = memo(function ScaledFrame({
  html,
  width,
  height,
  maxWidth = CARD_WIDTH,
  maxHeight = MAX_CARD_HEIGHT,
}: {
  html: string
  width: number
  height: number
  maxWidth?: number
  maxHeight?: number
}) {
  const scale = Math.min(maxWidth / width, maxHeight / height)
  const boxWidth = Math.round(width * scale)
  const boxHeight = Math.round(height * scale)
  return (
    <div
      className="overflow-hidden rounded-md border bg-white"
      style={{ width: boxWidth, height: boxHeight, margin: "0 auto" }}
    >
      <iframe
        srcDoc={html}
        title="preview"
        scrolling="no"
        sandbox="allow-same-origin allow-scripts"
        style={{
          width,
          height,
          border: 0,
          transform: `scale(${scale})`,
          transformOrigin: "0 0",
          pointerEvents: "none",
        }}
      />
    </div>
  )
})

/**
 * Live preview that fills its parent container — measures it with a
 * ResizeObserver and scales the document to fit, so it never overflows the
 * pane regardless of viewport/dialog size.
 */
export const FitScaledFrame = memo(function FitScaledFrame({
  html,
  width,
  height,
  gap = 8,
}: {
  html: string
  width: number
  height: number
  gap?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [box, setBox] = useState({ w: 0, h: 0 })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect
      if (r) setBox({ w: r.width, h: r.height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const availW = Math.max(1, box.w - gap * 2)
  const availH = Math.max(1, box.h - gap * 2)
  const scale = Math.min(availW / width, availH / height)
  const boxWidth = Math.max(1, Math.round(width * scale))
  const boxHeight = Math.max(1, Math.round(height * scale))

  return (
    <div ref={ref} className="flex h-full w-full items-center justify-center">
      <div
        className="overflow-hidden rounded-md border bg-white"
        style={{ width: boxWidth, height: boxHeight }}
      >
        <iframe
          srcDoc={html}
          title="preview"
          scrolling="no"
          sandbox="allow-same-origin allow-scripts"
          style={{
            width,
            height,
            border: 0,
            transform: `scale(${scale})`,
            transformOrigin: "0 0",
            pointerEvents: "none",
          }}
        />
      </div>
    </div>
  )
})

/** Family-aware preview used in galleries. */
export const PreviewFrame = memo(function PreviewFrame({
  html,
  family,
}: {
  html: string
  family: string
}) {
  const dims = FAMILY_DIMS[family] ?? FAMILY_DIMS.square
  return <ScaledFrame html={html} width={dims.width} height={dims.height} />
})

export interface PreviewZoomHandle {
  zoomBy: (factor: number) => void
  fit: () => void
}

/**
 * Interactive live preview with zoom controls. Defaults to "fit" (auto-scales
 * to the pane); ± zooms around fit, "Fit" resets, "100%" shows natural pixels
 * (scrollable) so overflow is easy to inspect.
 */
export const ZoomableFrame = memo(function ZoomableFrame({
  html,
  width,
  height,
  gap = 8,
  ref,
}: {
  html: string
  width: number
  height: number
  gap?: number
  ref?: React.Ref<PreviewZoomHandle>
}) {
  const areaRef = useRef<HTMLDivElement>(null)
  const [box, setBox] = useState({ w: 0, h: 0 })
  const [zoomMul, setZoomMul] = useState(1)

  useEffect(() => {
    const el = areaRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect
      if (r) setBox({ w: r.width, h: r.height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const fitScale = Math.min(
    Math.max(1, box.w - gap * 2) / width,
    Math.max(1, box.h - gap * 2) / height
  )
  const scale = fitScale * zoomMul
  const boxWidth = Math.max(1, Math.round(width * scale))
  const boxHeight = Math.max(1, Math.round(height * scale))
  const pct = Math.round(scale * 100)

  function zoomOut() {
    setZoomMul((z) => Math.max(0.08, z / 1.25))
  }
  function zoomIn() {
    setZoomMul((z) => Math.min(20, z * 1.25))
  }
  function fit() {
    setZoomMul(1)
  }
  function oneToOne() {
    if (fitScale > 0) setZoomMul(1 / fitScale)
  }

  useImperativeHandle(
    ref,
    () => ({
      zoomBy: (factor: number) => setZoomMul((z) => Math.min(20, Math.max(0.08, z * factor))),
      fit: () => setZoomMul(1),
    }),
    []
  )

  return (
    <div className="flex h-full w-full flex-col">
      <div className="flex shrink-0 items-center justify-between border-b bg-muted/20 px-2 py-1">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Zoom out" onClick={zoomOut} className="h-7 w-7">
            <Minus className="size-3.5" />
          </Button>
          <span className="w-12 text-center text-xs tabular-nums">{pct}%</span>
          <Button variant="ghost" size="icon" aria-label="Zoom in" onClick={zoomIn} className="h-7 w-7">
            <Plus className="size-3.5" />
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={fit} className="h-7 px-2 text-xs">
            <Maximize2 className="size-3.5" />
            Fit
          </Button>
          <Button variant="ghost" size="sm" onClick={oneToOne} className="h-7 px-2 text-xs">
            100%
          </Button>
        </div>
      </div>
      <div ref={areaRef} className="min-h-0 flex-1 overflow-auto">
        <div
          className="overflow-hidden rounded-md border bg-white"
          style={{ width: boxWidth, height: boxHeight, margin: "0 auto" }}
        >
          <iframe
            srcDoc={html}
            title="preview"
            scrolling="no"
            sandbox="allow-same-origin allow-scripts"
            style={{
              width,
              height,
              border: 0,
              transform: `scale(${scale})`,
              transformOrigin: "0 0",
              pointerEvents: "none",
            }}
          />
        </div>
      </div>
    </div>
  )
})
