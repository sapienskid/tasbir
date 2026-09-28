import { describe, expect, it, vi } from "vitest"
import {
  EditorStore,
  buildRefillBody,
  docKey,
  editorDocFromState,
  effectiveHidden,
  mediaFingerprint,
  type EditorDoc,
  type StoreChange,
} from "@/lib/editor-store"
import type { EditorState } from "@/lib/api"

function baseDoc(over: Partial<EditorDoc> = {}): EditorDoc {
  return {
    templateId: "square-editorial-stack",
    slots: { headline: "Hello", subhead: "World", body: "" },
    hidden: null,
    mediaPosition: "auto",
    media: null,
    designSystemId: "default",
    ...over,
  }
}

function clock() {
  let t = 1000
  return { now: () => t, advance: (ms: number) => (t += ms) }
}

const UPLOAD = { kind: "upload" as const, data: "AAAA".repeat(50), mime: "image/png", alt: "a" }
const ILLUSTRATION = { kind: "illustration" as const, style: "procedural", seed: "abc" }

describe("EditorStore text", () => {
  it("notifies synchronously with the changed slot and no structural flag", () => {
    const s = new EditorStore(baseDoc())
    const seen: StoreChange[] = []
    s.subscribe((c) => seen.push(c))
    expect(s.setSlot("headline", "Hello!")).toBe(true)
    expect(seen).toHaveLength(1)
    expect(seen[0]).toMatchObject({ slots: ["headline"], structural: false, source: "form" })
    expect(s.doc.slots.headline).toBe("Hello!")
  })

  it("is a no-op when the text is unchanged", () => {
    const s = new EditorStore(baseDoc())
    const l = vi.fn()
    s.subscribe(l)
    expect(s.setSlot("headline", "Hello")).toBe(false)
    expect(s.setSlot("tagline", "")).toBe(false) // absent + empty
    expect(l).not.toHaveBeenCalled()
    expect(s.canUndo).toBe(false)
  })

  it("form and inline edits share one document", () => {
    const s = new EditorStore(baseDoc())
    s.setSlot("headline", "from form", "form")
    s.setSlot("headline", "from inline", "inline")
    expect(s.doc.slots.headline).toBe("from inline")
    expect(s.isDirty()).toBe(true)
  })

  it("a throwing subscriber never breaks editing", () => {
    const s = new EditorStore(baseDoc())
    const err = vi.spyOn(console, "error").mockImplementation(() => {})
    const good = vi.fn()
    s.subscribe(() => {
      throw new Error("boom")
    })
    s.subscribe(good)
    expect(() => s.setSlot("headline", "x")).not.toThrow()
    expect(good).toHaveBeenCalledTimes(1)
    err.mockRestore()
  })
})

describe("EditorStore undo / redo", () => {
  it("coalesces typing in one field into a single step", () => {
    const c = clock()
    const s = new EditorStore(baseDoc(), { now: c.now, coalesceMs: 900 })
    for (const ch of ["H", "He", "Hel", "Hell", "Hello!"]) {
      s.setSlot("headline", ch)
      c.advance(100)
    }
    expect(s.undo().ok).toBe(true)
    expect(s.doc.slots.headline).toBe("Hello") // back to the original in ONE undo
    expect(s.canUndo).toBe(false)
  })

  it("starts a new step after a pause or a different field", () => {
    const c = clock()
    const s = new EditorStore(baseDoc(), { now: c.now, coalesceMs: 900 })
    s.setSlot("headline", "A")
    c.advance(2000)
    s.setSlot("headline", "AB") // pause → new step
    s.setSlot("subhead", "Sub") // other field → new step
    s.undo()
    expect(s.doc.slots.subhead).toBe("World")
    expect(s.doc.slots.headline).toBe("AB")
    s.undo()
    expect(s.doc.slots.headline).toBe("A")
    s.undo()
    expect(s.doc.slots.headline).toBe("Hello")
  })

  it("redo restores and a new edit clears the redo stack", () => {
    const c = clock()
    const s = new EditorStore(baseDoc(), { now: c.now })
    s.setSlot("headline", "One")
    c.advance(5000)
    s.setSlot("headline", "Two")
    s.undo()
    expect(s.doc.slots.headline).toBe("One")
    expect(s.canRedo).toBe(true)
    s.redo()
    expect(s.doc.slots.headline).toBe("Two")
    s.undo()
    c.advance(5000)
    s.setSlot("subhead", "new branch")
    expect(s.canRedo).toBe(false)
  })

  it("undo after typing does not merge the next typing into the old step", () => {
    const c = clock()
    const s = new EditorStore(baseDoc(), { now: c.now })
    s.setSlot("headline", "A")
    s.undo()
    s.setSlot("headline", "B")
    s.undo()
    expect(s.doc.slots.headline).toBe("Hello")
  })

  it("undoes structural changes: template, toggles, position", () => {
    const s = new EditorStore(baseDoc())
    s.setTemplate("square-split")
    s.setHidden(["body"])
    s.setMediaPosition("left")
    expect(s.doc).toMatchObject({ templateId: "square-split", hidden: ["body"], mediaPosition: "left" })
    s.undo()
    expect(s.doc.mediaPosition).toBe("auto")
    s.undo()
    expect(s.doc.hidden).toBeNull()
    s.undo()
    expect(s.doc.templateId).toBe("square-editorial-stack")
    expect(s.undo().ok).toBe(false)
  })

  it("template switch resets toggles and position to the new template's defaults", () => {
    const s = new EditorStore(baseDoc({ hidden: ["body"], mediaPosition: "left" }))
    s.setTemplate("other")
    expect(s.doc.hidden).toBeNull()
    expect(s.doc.mediaPosition).toBe("auto")
  })

  it("flags structural undo so the preview is refreshed", () => {
    const s = new EditorStore(baseDoc())
    s.setTemplate("t2")
    const seen: StoreChange[] = []
    s.subscribe((c) => seen.push(c))
    s.undo()
    expect(seen[0]).toMatchObject({ source: "undo", structural: true })
  })

  it("does not drop already-saved media on undo (the original can't come back)", () => {
    const s = new EditorStore(baseDoc())
    s.setMedia(UPLOAD)
    s.markSaved(s.doc) // the server now has it
    const r = s.undo()
    // The only step is the media change → nothing visible to undo.
    expect(r.ok).toBe(false)
    expect(r.mediaKept).toBe(true)
    expect(s.doc.media).toEqual(UPLOAD)
  })

  it("undoes unsaved media normally", () => {
    const s = new EditorStore(baseDoc())
    s.setMedia(ILLUSTRATION)
    expect(s.undo().ok).toBe(true)
    expect(s.doc.media).toBeNull()
  })

  it("skips no-op history entries", () => {
    const s = new EditorStore(baseDoc())
    s.setMedia(UPLOAD)
    s.markSaved(s.doc)
    s.setSlot("headline", "changed")
    // step 1: text; step 2 (media) is a no-op once saved → skipped
    expect(s.undo().ok).toBe(true)
    expect(s.doc.slots.headline).toBe("Hello")
    expect(s.undo().ok).toBe(false)
  })
})

describe("EditorStore server sync", () => {
  it("adoptSlots adds unknown fields to doc AND baseline without going dirty", () => {
    const s = new EditorStore(baseDoc())
    const seen: StoreChange[] = []
    s.subscribe((c) => seen.push(c))
    s.adoptSlots({ kicker: "WRITING", headline: "SERVER" })
    expect(s.doc.slots.kicker).toBe("WRITING")
    expect(s.doc.slots.headline).toBe("Hello") // known field: local wins
    expect(s.isDirty()).toBe(false)
    expect(seen[0]).toMatchObject({ source: "system", slots: ["kicker"] })
    expect(s.canUndo).toBe(false)
  })

  it("revertStructure restores the last good structure and keeps typed text", () => {
    const s = new EditorStore(baseDoc())
    const good = { templateId: s.doc.templateId, hidden: s.doc.hidden, mediaPosition: "auto", media: null, designSystemId: s.doc.designSystemId }
    s.setTemplate("broken")
    s.setSlot("headline", "typed meanwhile")
    s.revertStructure(good)
    expect(s.doc.templateId).toBe("square-editorial-stack")
    expect(s.doc.slots.headline).toBe("typed meanwhile")
    expect(s.canRedo).toBe(false)
  })

  it("replace resets doc, baseline and history", () => {
    const s = new EditorStore(baseDoc())
    s.setSlot("headline", "x")
    s.replace(baseDoc({ templateId: "fresh" }))
    expect(s.doc.templateId).toBe("fresh")
    expect(s.isDirty()).toBe(false)
    expect(s.canUndo).toBe(false)
  })

  it("editorDocFromState maps the server contract", () => {
    const st = {
      template_id: "t",
      slots: { headline: "H" },
      hidden: ["body"],
      media_position: "",
    } as unknown as EditorState
    expect(editorDocFromState(st)).toEqual({
      templateId: "t",
      slots: { headline: "H" },
      hidden: ["body"],
      mediaPosition: "auto",
      media: null,
      designSystemId: "default",
    })
  })
})

describe("buildRefillBody", () => {
  const defaults = (id: string) => (id === "square-split" ? ["tagline"] : [])

  it("is null when nothing differs", () => {
    const d = baseDoc()
    expect(buildRefillBody(d, d)).toBeNull()
    expect(buildRefillBody({ ...d, slots: { ...d.slots } }, d)).toBeNull()
  })

  it("text-only edit sends only the changed slots (cheap path)", () => {
    const saved = baseDoc()
    const doc = baseDoc({ slots: { ...saved.slots, headline: "New" } })
    const r = buildRefillBody(doc, saved)
    expect(r).toEqual({ body: { slots: { headline: "New" } }, structural: false, changedSlots: ["headline"] })
  })

  it("a slot with no live element is a structural (re-fill) edit", () => {
    const saved = baseDoc()
    const doc = baseDoc({ slots: { ...saved.slots, tagline: "hi" } })
    const r = buildRefillBody(doc, saved, { liveSlots: new Set(["headline", "subhead", "body"]) })
    expect(r?.structural).toBe(true)
    expect(r?.body.hidden).toEqual([])
    expect(r?.body.slots).toEqual({ tagline: "hi" })
  })

  it("toggles send the explicit hidden list plus structural state", () => {
    const saved = baseDoc()
    const doc = baseDoc({ hidden: ["body"] })
    const r = buildRefillBody(doc, saved)
    expect(r?.structural).toBe(true)
    expect(r?.body).toEqual({
      template_id: "square-editorial-stack",
      hidden: ["body"],
      media_position: "auto",
    })
  })

  it("template switch resolves the new template's default hidden list", () => {
    const saved = baseDoc()
    const doc = baseDoc({ templateId: "square-split" })
    const r = buildRefillBody(doc, saved, { defaultHidden: defaults })
    expect(r?.body).toEqual({ template_id: "square-split", hidden: ["tagline"], media_position: "auto" })
  })

  it("'template default' equals an explicit copy of the default (no phantom change)", () => {
    const saved = baseDoc({ templateId: "square-split", hidden: null })
    const doc = baseDoc({ templateId: "square-split", hidden: ["tagline"] })
    expect(buildRefillBody(doc, saved, { defaultHidden: defaults })).toBeNull()
  })

  it("media is sent only until it is saved", () => {
    const saved = baseDoc()
    const doc = baseDoc({ media: UPLOAD })
    expect(buildRefillBody(doc, saved)?.body.media).toMatchObject({ kind: "upload", alt: "a" })
    const savedWith = baseDoc({ media: UPLOAD })
    const later = baseDoc({ media: UPLOAD, slots: { ...saved.slots, headline: "Z" } })
    const r = buildRefillBody(later, savedWith)
    expect(r?.structural).toBe(false)
    expect(r?.body.media).toBeUndefined()
  })

  it("combined text + structural edits ride in one body", () => {
    const saved = baseDoc()
    const doc = baseDoc({ mediaPosition: "left", slots: { ...saved.slots, headline: "Both" } })
    const r = buildRefillBody(doc, saved)
    expect(r?.body).toMatchObject({ slots: { headline: "Both" }, media_position: "left", hidden: [] })
  })

  it("design-system switch sends design_system_id and is structural", () => {
    const saved = baseDoc()
    const doc = baseDoc({ designSystemId: "theorem", templateId: "theorem-square-slide" })
    const r = buildRefillBody(doc, saved)
    expect(r?.structural).toBe(true)
    expect(r?.body.design_system_id).toBe("theorem")
    expect(r?.body.template_id).toBe("theorem-square-slide")
  })

  it("setDesignSystem is one undo step and resets toggles", () => {
    const s = new EditorStore(baseDoc({ hidden: ["body"], mediaPosition: "left" }))
    expect(s.setDesignSystem("default", "square-editorial-stack")).toBe(false)
    expect(s.setDesignSystem("theorem", "theorem-square-slide")).toBe(true)
    expect(s.doc).toMatchObject({
      designSystemId: "theorem",
      templateId: "theorem-square-slide",
      hidden: null,
      mediaPosition: "auto",
    })
    s.undo()
    expect(s.doc.designSystemId).toBe("default")
    expect(s.doc.templateId).toBe("square-editorial-stack")
  })
})

describe("cache keys", () => {
  it("differ on revision, text, structure and media; ignore hidden order", () => {
    const d = baseDoc({ hidden: ["a", "b"] })
    const same = baseDoc({ hidden: ["b", "a"] })
    expect(docKey(d, 1)).toBe(docKey(same, 1))
    expect(docKey(d, 1)).not.toBe(docKey(d, 2))
    expect(docKey(d, 1)).not.toBe(docKey({ ...d, slots: { ...d.slots, headline: "x" } }, 1))
    expect(docKey(d, 1)).not.toBe(docKey({ ...d, media: ILLUSTRATION }, 1))
  })

  it("fingerprints large uploads instead of embedding them", () => {
    const fp = mediaFingerprint({ ...UPLOAD, data: "Q".repeat(5_000_000) })
    expect(fp.length).toBeLessThan(200)
  })

  it("effectiveHidden falls back to the template default", () => {
    expect(effectiveHidden(baseDoc({ templateId: "x" }), () => ["k"])).toEqual(["k"])
    expect(effectiveHidden(baseDoc({ hidden: [] }), () => ["k"])).toEqual([])
  })
})
