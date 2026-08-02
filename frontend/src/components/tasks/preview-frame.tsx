import { memo } from "react"

export const FAMILY_DIMS: Record<string, { width: number; height: number }> = {
  square: { width: 1080, height: 1080 },
  portrait: { width: 1080, height: 1350 },
  story: { width: 1080, height: 1920 },
  landscape: { width: 1200, height: 627 },
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
