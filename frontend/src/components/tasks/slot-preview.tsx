import { memo, useEffect, useImperativeHandle, useRef, useState } from "react"
import { AlertTriangle, Loader2, Maximize2, Minus, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { EditorStore } from "@/lib/editor-store"
import { applySlotsToDocument, detectOverflow } from "./slot-utils"

export interface SlotPreviewHandle {
  zoomBy: (factor: number) => void
  fit: () => void
}

/** Keys forwarded out of the iframe so Ctrl+Z / Ctrl+S work while editing inline. */
export interface FrameKey {
  key: string
  ctrl: boolean
  shift: boolean
  alt: boolean
  preventDefault: () => void
  /** True when the key was pressed while typing in a slot. */
  editing: boolean
}

/**
 * True-WYSIWYG preview: the exact final document in a scaled iframe.
 *
 *  - Two stacked iframes: a new document loads in the hidden one and swaps in
 *    once ready, so structural updates never flash blank.
 *  - Text is patched into the live DOM synchronously from the shared store
 *    (no network, no reload); inline edits write back into the same store.
 *  - Slot texts held by the store are re-applied after every swap, so edits
 *    typed while a preview was in flight are never lost.
 */
export const SlotPreview = memo(function SlotPreview({
  html,
  htmlVersion,
  width,
  height,
  store,
  editable = true,
  updating = false,
  onHotkey,
  ref,
}: {
  html: string
  /** Bump to force a reload even when `html` is byte-identical. */
  htmlVersion: number
  width: number
  height: number
  /** Shared editor store; null = a plain static preview. */
  store: EditorStore | null
  editable?: boolean
  updating?: boolean
  onHotkey?: (e: FrameKey) => void
  ref?: React.Ref<SlotPreviewHandle>
}) {
  const areaRef = useRef<HTMLDivElement>(null)
  const frameA = useRef<HTMLIFrameElement>(null)
  const frameB = useRef<HTMLIFrameElement>(null)
  const activeRef = useRef(-1)
  const [active, setActive] = useState(-1)
  const [box, setBox] = useState({ w: 0, h: 0 })
  const [zoomMul, setZoomMul] = useState(1)
  const [overflow, setOverflow] = useState<string[]>([])
  const editingRef = useRef<{ el: HTMLElement; slot: string; original: string } | null>(null)
  const storeRef = useRef(store)
  storeRef.current = store
  const editableRef = useRef(editable)
  editableRef.current = editable
  const hotkeyRef = useRef(onHotkey)
  hotkeyRef.current = onHotkey
  const dimsRef = useRef({ width, height })
  dimsRef.current = { width, height }
  const rafRef = useRef(0)

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

  const fitScale = Math.min(Math.max(1, box.w - 16) / width, Math.max(1, box.h - 16) / height)
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

  const activeDoc = (): Document | null => {
    const f = activeRef.current === 0 ? frameA.current : activeRef.current === 1 ? frameB.current : null
    return f?.contentDocument ?? null
  }

  // Overflow chips: recomputed at most once per frame after any change.
  const scheduleOverflow = () => {
    if (rafRef.current) return
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0
      const doc = activeDoc()
      if (!doc?.body) return
      const next = detectOverflow(doc, dimsRef.current.width, dimsRef.current.height)
      setOverflow((prev) =>
        prev.length === next.length && prev.every((v, i) => v === next[i]) ? prev : next
      )
    })
  }

  // Load each new document into the hidden frame, then swap.
  useEffect(() => {
    const target = activeRef.current === 0 ? 1 : 0
    const frame = (target === 0 ? frameA : frameB).current
    if (!frame) return
    let alive = true

    const finishEditing = (commit: boolean) => {
      const cur = editingRef.current
      if (!cur) return
      editingRef.current = null
      cur.el.contentEditable = "false"
      cur.el.removeAttribute("data-slot-editing")
      if (!commit) {
        cur.el.textContent = cur.original
        storeRef.current?.setSlot(cur.slot, cur.original, "form")
      }
    }

    const prepare = (doc: Document) => {
      const style = doc.createElement("style")
      style.setAttribute("data-tasbir-slots", "")
      style.textContent = [
        "[data-slot]{cursor:text;border-radius:2px;transition:outline-color .15s;outline:2px dashed transparent;outline-offset:3px}",
        "[data-slot]:hover{outline-color:rgba(100,116,139,.55)}",
        "[data-slot][data-slot-editing]{outline:2px solid rgb(37,99,235);outline-offset:3px;cursor:text}",
      ].join("\n")
      doc.head.appendChild(style)

      doc.addEventListener(
        "keydown",
        (e) => {
          const mod = e.ctrlKey || e.metaKey
          const k = e.key
          const isHot = mod && ["z", "y", "s", "Z", "Y", "S"].includes(k)
          const isNav = !mod && !e.altKey && (k === "[" || k === "]") && !editingRef.current
          if (!isHot && !isNav) return
          hotkeyRef.current?.({
            key: k.toLowerCase(),
            ctrl: mod,
            shift: e.shiftKey,
            alt: e.altKey,
            preventDefault: () => e.preventDefault(),
            editing: !!editingRef.current,
          })
        },
        true
      )

      if (!editableRef.current) return
      doc.querySelectorAll<HTMLElement>("[data-slot]").forEach((el) => {
        const slot = el.getAttribute("data-slot")
        if (!slot || slot === "counter") return
        el.addEventListener("click", (e) => {
          e.preventDefault()
          e.stopPropagation()
          if (editingRef.current?.el === el) return
          finishEditing(true)
          editingRef.current = { el, slot, original: el.textContent ?? "" }
          el.setAttribute("data-slot-editing", "")
          el.contentEditable = "true"
          el.focus()
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
        // Live: every keystroke lands in the shared store (form mirrors it).
        el.addEventListener("input", () => {
          const text = (el.innerText ?? el.textContent ?? "").replace(/\n+$/, "")
          storeRef.current?.setSlot(slot, text, "inline")
          scheduleOverflow()
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
    }

    const onLoad = () => {
      frame.removeEventListener("load", onLoad)
      if (!alive) return
      const doc = frame.contentDocument
      if (!doc?.body) return
      finishEditing(true)
      prepare(doc)
      const st = storeRef.current
      if (st) applySlotsToDocument(doc, st.doc.slots)
      activeRef.current = target
      setActive(target)
      scheduleOverflow()
      void doc.fonts?.ready.then(scheduleOverflow).catch(() => {})
    }
    frame.addEventListener("load", onLoad)
    frame.srcdoc = html
    return () => {
      alive = false
      frame.removeEventListener("load", onLoad)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [html, htmlVersion])

  // Text edits → the visible document, synchronously.
  useEffect(() => {
    if (!store) return
    return store.subscribe((c) => {
      const doc = activeDoc()
      if (!doc || c.slots.length === 0) return
      const skip = c.source === "inline" ? editingRef.current?.el : null
      applySlotsToDocument(doc, store.doc.slots, c.slots, skip)
      scheduleOverflow()
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store])

  const frameStyle = (i: number): React.CSSProperties => ({
    position: "absolute",
    top: 0,
    left: 0,
    width,
    height,
    border: 0,
    transform: `scale(${scale})`,
    transformOrigin: "0 0",
    visibility: active === i ? "visible" : "hidden",
    pointerEvents: active === i ? "auto" : "none",
  })

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
          {updating ? (
            <span
              role="status"
              className="inline-flex items-center gap-1 text-[11px] text-muted-foreground"
              data-testid="preview-updating"
            >
              <Loader2 aria-hidden="true" className="size-3 animate-spin" /> Updating…
            </span>
          ) : null}
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
          className="relative overflow-hidden rounded-md border bg-white"
          style={{ width: boxWidth, height: boxHeight, margin: "8px auto" }}
        >
          <iframe
            ref={frameA}
            title="editable preview"
            data-active={active === 0 ? "true" : "false"}
            scrolling="no"
            sandbox="allow-same-origin allow-scripts"
            style={frameStyle(0)}
          />
          <iframe
            ref={frameB}
            title="editable preview (buffer)"
            data-active={active === 1 ? "true" : "false"}
            scrolling="no"
            sandbox="allow-same-origin allow-scripts"
            style={frameStyle(1)}
          />
        </div>
      </div>
      <div className="shrink-0 border-t bg-muted/20 px-2 py-1 text-[11px] text-muted-foreground">
        {editable
          ? "Click any text to edit it in place — Enter to finish, Escape cancels."
          : "Preview only."}
      </div>
    </div>
  )
})
