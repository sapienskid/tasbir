import { useEffect, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { ScaledFrame } from "@/components/tasks/preview-frame"
import { formatDims } from "@/lib/platforms"
import type { TaskDetail } from "@/lib/api"
import { Download } from "lucide-react"
import { formatLabel, groupFormats, StepDot } from "@/components/tasks/format-utils"

const THUMB_MAX_W = 280
const THUMB_MAX_H = 230

/**
 * Contact-sheet view of every artifact in the task. Each format is a
 * thumbnail card (PNG render, or live HTML frame when no PNG exists); clicking
 * one opens the full editor for that format. All artifacts flow through a
 * single CSS masonry so mixed aspect ratios fill the width edge-to-edge.
 */
export function GalleryView({
  task,
  formats,
  pngUrlFor,
  htmlFor,
  prefetch,
  onOpenFormat,
  onDownloadZip,
}: {
  task: TaskDetail
  formats: string[]
  pngUrlFor: (fmt: string) => string | undefined
  htmlFor: (fmt: string) => string | undefined
  prefetch: (fmt: string) => Promise<unknown>
  onOpenFormat: (fmt: string) => void
  onDownloadZip: () => void
}) {
  // Warm every format's cache (PNG + HTML) so thumbnails render and the
  // editor opens instantly.
  useEffect(() => {
    if (formats.length > 0) void Promise.all(formats.map((fmt) => prefetch(fmt)))
  }, [formats, prefetch])

  // Flatten the groups (Posts, Carousel·square, Carousel·portrait) so all
  // artifacts share one masonry column flow while keeping their natural order.
  const ordered = useMemo(() => groupFormats(formats).flatMap((g) => g.items), [formats])
  const missing = formats.length - Object.keys(task?.result?.platforms ?? {}).length

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {formats.length} artifacts{missing > 0 ? ` · ${missing} without a render yet` : ""}
        </p>
        <Button variant="outline" size="sm" onClick={onDownloadZip} disabled={formats.length === 0}>
          <Download className="size-4" />
          Download ZIP
        </Button>
      </div>

      <div className="columns-1 gap-5 sm:columns-2 md:columns-3 xl:columns-4">
        {ordered.map((fmt) => {
          const p = task?.result?.platforms?.[fmt]
          return (
            <div key={fmt} className="mb-5 break-inside-avoid">
              <ArtifactCard
                fmt={fmt}
                pngUrl={pngUrlFor(fmt)}
                html={htmlFor(fmt)}
                status={p?.status}
                score={p?.quality_score}
                onOpen={() => onOpenFormat(fmt)}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ArtifactCard({
  fmt,
  pngUrl,
  html,
  status,
  score,
  onOpen,
}: {
  fmt: string
  pngUrl?: string
  html?: string
  status?: string
  score?: number
  onOpen: () => void
}) {
  const dims = formatDims(fmt)

  return (
    <button
      type="button"
      onClick={onOpen}
      className="group w-full overflow-hidden rounded-lg border bg-card text-left transition-colors hover:border-primary/50 hover:bg-primary/5"
    >
      <div
        className="flex items-center justify-center overflow-hidden border-b bg-muted/40"
        style={{ aspectRatio: `${dims.width} / ${dims.height}` }}
      >
        {pngUrl ? (
          <img
            src={pngUrl}
            alt={formatLabel(fmt)}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
          />
        ) : html ? (
          <ScaledFrame
            html={html}
            width={dims.width}
            height={dims.height}
            maxWidth={THUMB_MAX_W}
            maxHeight={THUMB_MAX_H}
          />
        ) : (
          <span className="px-3 text-center text-xs text-muted-foreground">
            {formatLabel(fmt)} — no render yet
          </span>
        )}
      </div>
      <div className="flex items-center gap-2 px-3 py-2.5">
        <StepDot status={status ?? "pending"} />
        <span className="flex-1 truncate text-sm font-medium">{formatLabel(fmt)}</span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {dims.width}×{dims.height}
        </span>
        {typeof score === "number" ? (
          <span className="text-xs tabular-nums text-muted-foreground">{score}</span>
        ) : null}
      </div>
    </button>
  )
}
