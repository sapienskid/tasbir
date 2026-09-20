import { memo, useEffect, useImperativeHandle, useRef, useState } from "react"
import { AlertTriangle, Maximize2, Minus, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { detectOverflow } from "./slot-utils"

export interface SlotPreviewHandle {
  zoomBy: (factor: number) => void
  fit: () => void
}

/**
 * True-WYSIWYG preview: the exact final document in a scaled iframe, with
 * [data-slot] elements directly editable in place. Click a slot to type in
 * the real layout with real fonts — Enter commits, Escape reverts, paste is
 * forced to plain text so rich markup can never pollute a slot.
 *
 * Unlike a parallel canvas editor, there is no reinterpretation step: this
 * is the same HTML the PNG renderer screenshots.
 */
export const SlotPreview = memo(function SlotPreview({
  html,
  width,
  height,
  editable = true,
  onSlotCommit,
  ref,
}: {
  html: string
  width: number
  height: number
  /** False for designer-LLM posts (no template → no refill endpoint): preview only. */
  editable?: boolean
  /** Called with (slot, text) when an inline edit commits. */
  onSlotCommit: (slot: string, text: string) => void
  ref?: React.Ref<SlotPreviewHandle>
}) {
  const areaRef = useRef<HTMLDivElement>(null)
  const frameRef = useRef<HTMLIFrameElement>(null)
  const [box, setBox] = useState({ w: 0, h: 0 })
  const [zoomMul, setZoomMul] = useState(1)
  const [overflow, setOverflow] = useState<string[]>([])
  const editingRef = useRef<{ el: HTMLElement; slot: string; original: string } | null>(null)
  const commitRef = useRef(onSlotCommit)
  commitRef.current = onSlotCommit

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
    Math.max(1, box.w - 16) / width,
    Math.max(1, box.h - 16) / height
  )
  const scale = fitScale * zoomMul
  const boxWidth = Math.max(1, Math.round(width * scale))
  const boxHeight = Math.max(1, Math.round(height * scale))

  useImperativeHandle(
    ref,
    () => ({
      zoomBy: (factor: number) => setZoomMul((z) => Math.min(20, Math.max(0.08, z * factor))),
      fit: () => setZoomMul(1),
    }),
    []
  )

  // Attach click-to-edit + overflow check inside the frame after each load.
  useEffect(() => {
    const iframe = frameRef.current
    if (!iframe) return
    let alive = true
    const timers: number[] = []

    const finishEditing = (commit: boolean) => {
      const cur = editingRef.current
      if (!cur) return
      editingRef.current = null
      cur.el.contentEditable = "false"
      cur.el.removeAttribute("data-slot-editing")
      if (commit) {
        const text = (cur.el.innerText ?? "").trim()
        if (text !== cur.original) commitRef.current(cur.slot, text)
        else cur.el.innerText = cur.original
      } else {
        cur.el.innerText = cur.original
      }
    }

    const onLoad = () => {
      if (!alive) return
      const doc = iframe.contentDocument
      if (!doc?.body) return
      // If the document reloaded mid-edit (draft changed elsewhere), commit
      // the in-flight text instead of losing it.
      finishEditing(true)

      const style = doc.createElement("style")
      style.setAttribute("data-tasbir-slots", "")
      style.textContent = [
        "[data-slot]{cursor:text;border-radius:2px;transition:outline-color .15s;outline:2px dashed transparent;outline-offset:3px}",
        "[data-slot]:hover{outline-color:rgba(100,116,139,.55)}",
        "[data-slot][data-slot-editing]{outline:2px solid rgb(37,99,235);outline-offset:3px;cursor:text}",
      ].join("\n")
      doc.head.appendChild(style)

      const check = () => {
        if (!alive) return
        setOverflow(detectOverflow(doc, width, height))
      }

      doc.querySelectorAll<HTMLElement>("[data-slot]").forEach((el) => {
        if (!editable) return
        const slot = el.getAttribute("data-slot")
        if (!slot) return
        el.addEventListener("click", (e) => {
          e.preventDefault()
          e.stopPropagation()
          if (editingRef.current?.el === el) return
          finishEditing(true)
          editingRef.current = { el, slot, original: (el.innerText ?? "").trim() }
          el.setAttribute("data-slot-editing", "")
          el.contentEditable = "true"
          el.focus()
          // Select all so typing replaces; a click into a selection still
          // allows caret placement afterwards.
          try {
            const range = doc.createRange()
            range.selectNodeContents(el)
            const sel = doc.getSelection()
            sel?.removeAllRanges()
            sel?.addRange(range)
          } catch {
            /* selection is best-effort */
          }
        })
        el.addEventListener("keydown", (e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            ;(e.target as HTMLElement).blur()
          } else if (e.key === "Escape") {
            e.preventDefault()
            finishEditing(false)
            ;(e.target as HTMLElement).blur()
          }
        })
        el.addEventListener("paste", (e) => {
          e.preventDefault()
          const text = e.clipboardData?.getData("text/plain") ?? ""
          try {
            doc.execCommand("insertText", false, text)
          } catch {
            /* older engines */
          }
        })
        el.addEventListener("blur", () => {
          if (editingRef.current?.el === el) finishEditing(true)
        })
      })

      check()
      void doc?.fonts?.ready.then(check).catch(() => {})
      timers.push(window.setTimeout(check, 800))
    }

    iframe.addEventListener("load", onLoad)
    timers.push(window.setTimeout(() => setOverflow([]), 0))
    return () => {
      alive = false
      iframe.removeEventListener("load", onLoad)
      timers.forEach((t) => clearTimeout(t))
    }
  }, [html, width, height, editable])

  return (
    <div className="flex h-full w-full flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b bg-muted/20 px-2 py-1">
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Zoom out"
            onClick={() => setZoomMul((z) => Math.max(0.08, z / 1.25))}
            className="h-7 w-7"
          >
            <Minus className="size-3.5" />
          </Button>
          <span className="w-12 text-center text-xs tabular-nums">{Math.round(scale * 100)}%</span>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Zoom in"
            onClick={() => setZoomMul((z) => Math.min(20, z * 1.25))}
            className="h-7 w-7"
          >
            <Plus className="size-3.5" />
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <span role="status" aria-live="polite" className="contents">
            {overflow.map((slot) => (
              <span
                key={slot}
                className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-700 dark:text-amber-400"
              >
                <AlertTriangle aria-hidden="true" className="size-3" />
                {slot === "canvas" ? "Overflows canvas" : `Overflow: ${slot}`}
              </span>
            ))}
          </span>
          <Button variant="ghost" size="sm" onClick={() => setZoomMul(1)} className="h-7 px-2 text-xs">
            <Maximize2 className="size-3.5" />
            Fit
          </Button>
        </div>
      </div>
      <div ref={areaRef} className="min-h-0 flex-1 overflow-auto bg-neutral-100 dark:bg-neutral-900">
        <div
          className="overflow-hidden rounded-md border bg-white"
          style={{ width: boxWidth, height: boxHeight, margin: "8px auto" }}
        >
          <iframe
            ref={frameRef}
            srcDoc={html}
            title="editable preview"
            scrolling="no"
            sandbox="allow-same-origin allow-scripts"
            style={{ width, height, border: 0, transform: `scale(${scale})`, transformOrigin: "0 0" }}
          />
        </div>
      </div>
      <div className="shrink-0 border-t bg-muted/20 px-2 py-1 text-[11px] text-muted-foreground">
        {editable
          ? "Click any text to edit it in place — Enter saves, Escape cancels."
          : "Preview only — this post wasn't built from a template."}
      </div>
    </div>
  )
})
