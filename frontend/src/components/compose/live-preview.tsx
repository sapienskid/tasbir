import { useEffect, useRef, useState } from "react"
import { AlertTriangle, Loader2 } from "lucide-react"
import { ZoomableFrame } from "@/components/tasks/preview-frame"
import { useSlidePreview } from "@/hooks/use-compose"
import type { ComposePreviewRequest } from "@/lib/api"
import { formatDims } from "@/lib/platforms"

/**
 * Slot names whose content overflows its box, plus "canvas" when the whole
 * document spills past the platform dimensions.
 */
const CLIPPING = new Set(["hidden", "clip", "scroll", "auto"])

function detectOverflow(doc: Document, width: number, height: number): string[] {
  const hits = new Set<string>()
  const win = doc.defaultView
  doc.querySelectorAll<HTMLElement>("[data-slot]").forEach((el) => {
    // Empty slots can't overflow.
    if (!el.textContent?.trim()) return
    // scrollHeight > clientHeight alone is NOT overflow: with overflow:visible
    // it just means glyphs extend past a tight line box (display type at
    // line-height 1). Only flag text that is actually clipped by its own box,
    // or that leaves the canvas — the same rule the server-side check uses.
    const cs = win?.getComputedStyle(el)
    const clips = !!cs && (CLIPPING.has(cs.overflowX) || CLIPPING.has(cs.overflowY))
    const clipped =
      clips && (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1)
    const r = el.getBoundingClientRect()
    const outside = r.right > width + 1 || r.bottom > height + 1 || r.left < -1 || r.top < -1
    if (clipped || outside) hits.add(el.dataset.slot || "slot")
  })
  const root = doc.documentElement
  const body = doc.body
  if (body) {
    const h = Math.max(root.scrollHeight, body.scrollHeight)
    const w = Math.max(root.scrollWidth, body.scrollWidth)
    if (h > height + 1 || w > width + 1) hits.add("canvas")
  }
  return [...hits]
}

/**
 * Main canvas: debounced POST /compose/preview of the selected slide in the
 * zoomable scaled iframe at true platform dims, with an overflow check run
 * inside the (same-origin) iframe after each load and once fonts settle.
 */
export function LivePreview({ req }: { req: ComposePreviewRequest | null }) {
  const { data, error, loading } = useSlidePreview(req, { delay: 350 })
  const wrapRef = useRef<HTMLDivElement>(null)
  const [overflow, setOverflow] = useState<string[]>([])
  const dims = data ?? formatDims(req?.platform ?? "")

  useEffect(() => {
    setOverflow([])
    if (!data) return
    const iframe = wrapRef.current?.querySelector("iframe")
    if (!iframe) return
    let alive = true
    const timers: number[] = []
    const check = () => {
      if (!alive) return
      const doc = iframe.contentDocument
      if (!doc?.body) return
      setOverflow(detectOverflow(doc, data.width, data.height))
    }
    const onLoad = () => {
      check()
      // Web fonts swap in after load and can push text over — re-check.
      const doc = iframe.contentDocument
      void doc?.fonts?.ready.then(check).catch(() => {})
      timers.push(window.setTimeout(check, 800))
    }
    iframe.addEventListener("load", onLoad)
    // Safety net in case the srcdoc finished loading before the listener.
    timers.push(window.setTimeout(check, 1500))
    return () => {
      alive = false
      iframe.removeEventListener("load", onLoad)
      timers.forEach((t) => clearTimeout(t))
    }
  }, [data])

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex min-h-6 flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground tabular-nums">
          {dims.width}×{dims.height}
        </span>
        {loading ? (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <Loader2 aria-hidden="true" className="size-3 animate-spin" /> Rendering…
          </span>
        ) : null}
        <span role="status" aria-live="polite" className="contents">
          {overflow.map((slot) => (
            <span
              key={slot}
              className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-amber-700 dark:text-amber-400"
            >
              <AlertTriangle aria-hidden="true" className="size-3" />
              {slot === "canvas" ? "Content overflows the canvas" : `Overflow: ${slot}`}
            </span>
          ))}
        </span>
      </div>
      <div ref={wrapRef} className="min-h-[360px] flex-1 overflow-hidden rounded-md border bg-muted/10">
        {!req?.slide.template_id ? (
          <p className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
            Choose a template to see the preview.
          </p>
        ) : error && !data ? (
          <p className="flex h-full items-center justify-center p-6 text-center text-sm text-destructive">
            {error}
          </p>
        ) : data ? (
          <ZoomableFrame html={data.html} width={data.width} height={data.height} />
        ) : (
          <div className="flex h-full items-center justify-center">
            <Loader2 aria-hidden="true" className="size-5 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>
      {error && data ? <p className="text-xs text-destructive">Latest change failed to render: {error}</p> : null}
    </div>
  )
}
