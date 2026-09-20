/** Shared slot helpers for agent-post structured editing.
 *
 * `parseSlots` reads the current text of every [data-slot] element from a
 * rendered HTML document (mirrors backend `extract_slots`). `detectOverflow`
 * flags slots clipped by their own box or spilling past the canvas (same rule
 * as the compose LivePreview and the server-side check).
 */

export function parseSlots(html: string): Record<string, string> {
  const out: Record<string, string> = {}
  if (!html) return out
  try {
    const doc = new DOMParser().parseFromString(html, "text/html")
    doc.querySelectorAll("[data-slot]").forEach((el) => {
      const name = el.getAttribute("data-slot")
      if (name && !(name in out)) out[name] = (el.textContent ?? "").trim()
    })
  } catch {
    /* malformed HTML — no slots */
  }
  return out
}

const CLIPPING = new Set(["hidden", "clip", "scroll", "auto"])

export function detectOverflow(doc: Document, width: number, height: number): string[] {
  const hits = new Set<string>()
  const win = doc.defaultView
  doc.querySelectorAll<HTMLElement>("[data-slot]").forEach((el) => {
    if (!el.textContent?.trim()) return
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
