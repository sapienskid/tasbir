import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Check, Maximize2, Minus, Plus, RotateCcw } from "lucide-react"
import type { Editor } from "grapesjs"

interface VisualEditorProps {
  /** Full HTML document (token-injected). */
  html: string
  /** Native canvas size in px (format dimensions). */
  width: number
  height: number
  /** Called with a rebuilt full document when the user applies edits. */
  onExport: (html: string) => void
}

/** Rebuild a full document from the original head (fonts/KaTeX/meta) + new CSS + body. */
function rebuildDocument(original: Document, bodyHtml: string, css: string): string {
  const headExtras = Array.from(original.head.children)
    .filter(
      (el) =>
        el.tagName !== "STYLE" &&
        !(el.tagName === "META" && el.getAttribute("charset"))
    )
    .map((el) => el.outerHTML)
    .join("\n")
  const lang = original.documentElement.getAttribute("lang") ?? "en"
  return [
    "<!DOCTYPE html>",
    `<html lang="${lang}">`,
    "<head>",
    '<meta charset="UTF-8">',
    headExtras,
    `<style>\n${css}\n</style>`,
    "</head>",
    `<body>\n${bodyHtml}\n</body>`,
    "</html>",
  ].join("\n")
}

/**
 * Locked-down GrapesJS canvas. The block manager stays empty (no manual
 * element addition — items come from the agent). The user selects existing
 * elements, edits text, restyles via the style manager, and repositions them.
 * "Apply to editor" exports the canvas back into the code editor, where
 * Re-render re-injects tokens/fonts/KaTeX/images and re-runs QC.
 */
export function VisualEditor({ html, width, height, onExport }: VisualEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const editorRef = useRef<Editor | null>(null)
  const originalRef = useRef<Document | null>(null)
  const [ready, setReady] = useState(false)
  const [zoomPct, setZoomPct] = useState(100)

  /**
   * Size the frames container to the device canvas and anchor it so its
   * center sits at the canvas viewport's center. GrapesJS by default sizes
   * the frames wrapper to the *viewport* (622x544) — fine for web layouts
   * where the device is smaller, but our 1080px canvas overflows it and gets
   * clipped. By giving the frames wrapper the exact device size and scaling
   * about its center, the full canvas stays centered at any zoom.
   */
  const centerFrame = useCallback(
    (ed: Editor) => {
      const viewport = ed.Canvas.getElement()
      const framesEl = ed.Canvas.getFramesEl()
      const vw = viewport.clientWidth
      const vh = viewport.clientHeight
      if (vw <= 0 || vh <= 0) return
      framesEl.style.width = `${width}px`
      framesEl.style.height = `${height}px`
      framesEl.style.left = `${(vw - width) / 2}px`
      framesEl.style.top = `${(vh - height) / 2}px`
      framesEl.style.transformOrigin = "center"
      // Allow panning when zoomed beyond "fit".
      viewport.style.overflow = "auto"
    },
    [width, height]
  )

  const fitPctFor = useCallback(
    (ed: Editor) => {
      const viewport = ed.Canvas.getElement()
      const vw = viewport.clientWidth
      const vh = viewport.clientHeight
      if (vw <= 0 || vh <= 0) return 100
      return Math.max(10, Math.min((vw - 12) / width, (vh - 12) / height) * 100)
    },
    [width, height]
  )

  /**
   * GrapesJS inserts an internal wrapper div between <body> and the design
   * root; a CssComposer rule pins it to a definite height so `height:100%`
   * chains on the design root resolve (see init).
   */
  useEffect(() => {
    let cancelled = false
    let editor: Editor | null = null
    const container = containerRef.current
    if (!container) return

    const parser = new DOMParser()
    const doc = parser.parseFromString(html, "text/html")
    originalRef.current = doc

    async function init() {
      const grapes = (await import("grapesjs")).default
      await import("grapesjs/dist/css/grapes.min.css")
      const container = containerRef.current
      if (cancelled || !container) return

      const ed = grapes.init({
        container,
        height: "100%",
        fromElement: false,
        storageManager: false,
        avoidInlineStyle: true,
        deviceManager: {
          devices: [{ id: "canvas", name: `${width}×${height}`, width: String(width), height: String(height) }],
          default: "canvas",
        },
        // No blocks → nothing can be added manually.
        blockManager: { blocks: [] },
      })

      ed.setComponents(doc.body.innerHTML)
      const styleTags = Array.from(doc.querySelectorAll("style"))
      const designCss = styleTags.map((s) => s.textContent ?? "").join("\n")
      // GrapesJS gives its internal wrapper div `min-height: 100%` (auto
      // height). That makes the wrapper an indefinite containing block, so a
      // full-bleed design root's `height: 100%` collapses to its text height
      // and sits above the canvas center. Pin the wrapper to a definite
      // height via the CssComposer so body → wrapper → card percentages
      // resolve correctly. The rule is inert in the exported doc (no such
      // element exists there).
      ed.setStyle([designCss, '[data-gjs-type="wrapper"] { height: 100%; }'].join("\n"))

      ed.setDevice("canvas")
      centerFrame(ed)
      const fitPct = fitPctFor(ed)
      ed.Canvas.setZoom(fitPct)
      // setZoom may reset the origin — enforce center after it.
      ed.Canvas.getFramesEl().style.transformOrigin = "center"

      editor = ed
      editorRef.current = ed
      setZoomPct(fitPct)
      setReady(true)
    }

    void init()
    return () => {
      cancelled = true
      try {
        editor?.destroy()
      } catch {
        /* already destroyed */
      }
      editorRef.current = null
    }
    // Init once on mount — the canvas owns its state. Re-applying the exported
    // HTML just re-renders with the same prop; we must not reload the canvas.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const setZoom = useCallback(
    (pct: number) => {
      const editor = editorRef.current
      if (!editor) return
      centerFrame(editor)
      editor.Canvas.setZoom(pct)
      editor.Canvas.getFramesEl().style.transformOrigin = "center"
      setZoomPct(editor.Canvas.getZoom())
    },
    [centerFrame]
  )

  const fit = useCallback(() => {
    const editor = editorRef.current
    if (!editor) return
    centerFrame(editor)
    setZoom(fitPctFor(editor))
  }, [centerFrame, fitPctFor, setZoom])

  const zoomOut = useCallback(() => setZoom(zoomPct / 1.2), [setZoom, zoomPct])
  const zoomIn = useCallback(() => setZoom(zoomPct * 1.2), [setZoom, zoomPct])
  const oneToOne = useCallback(() => setZoom(100), [setZoom])

  const apply = useCallback(() => {
    const editor = editorRef.current
    const original = originalRef.current
    if (!editor || !original) return
    const css = editor.getCss() ?? ""
    const bodyHtml = editor.getHtml() ?? ""
    onExport(rebuildDocument(original, bodyHtml, css))
  }, [onExport])

  return (
    <div data-visual-editor className="flex h-full w-full flex-col overflow-hidden rounded-md border">
      <style>{`[data-visual-editor] { --gjs-left-width: max(260px, 38%); }`}</style>
      <div className="flex shrink-0 items-center justify-between gap-2 border-b bg-muted/20 px-2 py-1">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Zoom out" onClick={zoomOut} className="h-7 w-7">
            <Minus className="size-3.5" />
          </Button>
          <span className="w-12 text-center text-xs tabular-nums">{Math.round(zoomPct)}%</span>
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
          <Button
            variant="outline"
            size="sm"
            onClick={apply}
            className="h-7 px-2 text-xs"
            disabled={!ready}
          >
            <Check className="size-3.5" />
            Apply to editor
          </Button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden bg-neutral-100 dark:bg-neutral-900">
        <div ref={containerRef} className="h-full w-full" />
      </div>
      <div className="flex shrink-0 items-center gap-2 border-t bg-muted/20 px-2 py-1 text-[11px] text-muted-foreground">
        <RotateCcw className="size-3" />
        Select elements to edit text / restyle. No manual additions — new elements come from the agent chat.
      </div>
    </div>
  )
}
