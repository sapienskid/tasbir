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
  const fitBoxRef = useRef<HTMLDivElement>(null)
  const editorRef = useRef<Editor | null>(null)
  const originalRef = useRef<Document | null>(null)
  const [ready, setReady] = useState(false)
  const [zoomPct, setZoomPct] = useState(100)

  useEffect(() => {
    let cancelled = false
    let editor: Editor | null = null
    let fitPct = 100
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

      const fitBox = fitBoxRef.current
      if (fitBox) {
        const cw = fitBox.clientWidth || container.clientWidth
        const ch = fitBox.clientHeight || container.clientHeight
        fitPct = Math.min((cw - 16) / width, (ch - 16) / height) * 100
        fitPct = Math.max(20, fitPct)
      }

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
      ed.setStyle(styleTags.map((s) => s.textContent ?? "").join("\n"))

      ed.setDevice("canvas")
      ed.Canvas.setZoom(fitPct)

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

  const setZoom = useCallback((pct: number) => {
    const editor = editorRef.current
    if (!editor) return
    editor.Canvas.setZoom(pct)
    setZoomPct(editor.Canvas.getZoom())
  }, [])

  const fit = useCallback(() => {
    const box = fitBoxRef.current
    const editor = editorRef.current
    if (!box || !editor) return
    const cw = box.clientWidth
    const ch = box.clientHeight
    const pct = Math.max(20, Math.min((cw - 16) / width, (ch - 16) / height) * 100)
    setZoom(pct)
  }, [height, setZoom, width])

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
    <div className="flex h-full w-full flex-col overflow-hidden rounded-md border">
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
      <div ref={fitBoxRef} className="min-h-0 flex-1 overflow-hidden bg-neutral-100 dark:bg-neutral-900">
        <div ref={containerRef} className="h-full w-full" />
      </div>
      <div className="flex shrink-0 items-center gap-2 border-t bg-muted/20 px-2 py-1 text-[11px] text-muted-foreground">
        <RotateCcw className="size-3" />
        Select elements to edit text / restyle. No manual additions — new elements come from the agent chat.
      </div>
    </div>
  )
}
