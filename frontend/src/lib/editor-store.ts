// Structured-editor state: ONE store shared by the Text form, inline editing
// in the preview, the template picker, element toggles and the media picker.
// Framework-free (no React, no DOM) so it is unit-testable; React binds to it
// through useSyncExternalStore and the preview iframe subscribes imperatively
// so a keystroke reaches the DOM in the same tick.

import type { ComposeMedia, EditorState, RefillRequest } from "@/lib/api"

/** A media selection that is complete enough to send to the server. */
export type MediaChoice = Exclude<ComposeMedia, { kind: "none" }>
export type MediaKindTag = "none" | "upload" | "photo" | "illustration"

export interface EditorDoc {
  templateId: string
  /** Text of every content slot (kicker/headline/…/extra.cta). */
  slots: Readonly<Record<string, string>>
  /** Element toggles; null = the template's own default. */
  hidden: readonly string[] | null
  mediaPosition: string
  /** A media change requested this session; null = keep what is baked in. */
  media: MediaChoice | null
  /** Effective design system (per-format override or the task's). */
  designSystemId: string
  /** Per-format recipe overrides (see services/format_recipe). "" language =
   *  the design system's own. */
  ground: "white" | "black"
  styleLanguage: string
  category: string
}

export type Structure = Pick<
  EditorDoc,
  | "templateId"
  | "hidden"
  | "mediaPosition"
  | "media"
  | "designSystemId"
  | "ground"
  | "styleLanguage"
  | "category"
>

export type ChangeSource = "form" | "inline" | "undo" | "redo" | "system" | "revert"

export interface StoreChange {
  source: ChangeSource
  /** Slot names whose text changed. */
  slots: string[]
  /** Template / toggles / media position / media changed. */
  structural: boolean
  /** Rapid-fire input (alt text, shuffle) — debounce the preview a little. */
  continuous: boolean
  /** The whole document was replaced (load / discard). */
  reset: boolean
}

export interface UndoResult {
  ok: boolean
  /** Undo stopped at media that was already saved — the original can't return. */
  mediaKept?: boolean
}

// ─── Pure helpers ──────────────────────────────────────────────────────────

function sameList(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false
  const set = new Set(a)
  return b.every((x) => set.has(x))
}

/** Cheap identity for media: kind + a fingerprint of large payloads. */
export function mediaFingerprint(m: MediaChoice | null): string {
  if (!m) return "none"
  if (m.kind === "upload") {
    const d = m.data
    return `upload:${m.mime}:${m.alt}:${d.length}:${d.slice(0, 24)}:${d.slice(-24)}`
  }
  if (m.kind === "photo") return `photo:${m.url}`
  return `illustration:${m.style}:${m.seed}`
}

export function mediaEqual(a: MediaChoice | null, b: MediaChoice | null): boolean {
  if (a === b) return true
  return mediaFingerprint(a) === mediaFingerprint(b)
}

export function slotsEqual(
  a: Readonly<Record<string, string>>,
  b: Readonly<Record<string, string>>
): boolean {
  const ka = Object.keys(a)
  if (ka.length !== Object.keys(b).length) return false
  return ka.every((k) => a[k] === b[k])
}

export function structureOf(doc: EditorDoc): Structure {
  return {
    templateId: doc.templateId,
    hidden: doc.hidden,
    mediaPosition: doc.mediaPosition,
    media: doc.media,
    designSystemId: doc.designSystemId,
    ground: doc.ground,
    styleLanguage: doc.styleLanguage,
    category: doc.category,
  }
}

export function sameStructure(a: Structure, b: Structure): boolean {
  if (a.templateId !== b.templateId || a.mediaPosition !== b.mediaPosition) return false
  if (a.designSystemId !== b.designSystemId) return false
  // Recipe overrides each force a full template re-fill server-side.
  if (a.ground !== b.ground) return false
  if (a.styleLanguage !== b.styleLanguage) return false
  if (a.category !== b.category) return false
  if (!mediaEqual(a.media, b.media)) return false
  if (a.hidden === null || b.hidden === null) return a.hidden === b.hidden
  return sameList(a.hidden, b.hidden)
}

export function docEquals(a: EditorDoc, b: EditorDoc): boolean {
  return a === b || (sameStructure(a, b) && slotsEqual(a.slots, b.slots))
}

/** Names whose text differs between two slot maps (missing counts as ""). */
export function changedSlotNames(
  a: Readonly<Record<string, string>>,
  b: Readonly<Record<string, string>>
): string[] {
  const names = new Set([...Object.keys(a), ...Object.keys(b)])
  return [...names].filter((n) => (a[n] ?? "") !== (b[n] ?? ""))
}

export type HiddenDefaults = (templateId: string) => readonly string[] | undefined

/** The toggles actually in force: explicit list, else the template default. */
export function effectiveHidden(doc: EditorDoc, defaults?: HiddenDefaults): readonly string[] {
  return doc.hidden ?? defaults?.(doc.templateId) ?? []
}

export function mediaToBody(m: MediaChoice): Record<string, string> {
  if (m.kind === "upload") return { kind: "upload", data: m.data, mime: m.mime, alt: m.alt }
  if (m.kind === "photo") {
    return {
      kind: "photo",
      url: m.url,
      credit: m.credit,
      provider: m.provider,
      photographer: m.photographer,
      license: m.license,
    }
  }
  return { kind: "illustration", style: m.style, seed: m.seed }
}

/** Server editor-state → the store's document. */
export function editorDocFromState(s: EditorState): EditorDoc {
  return {
    templateId: s.template_id,
    slots: { ...s.slots },
    hidden: Array.isArray(s.hidden) ? [...s.hidden] : null,
    mediaPosition: s.media_position || "auto",
    media: null,
    designSystemId: s.design_system_id || "default",
    ground: s.ground === "black" ? "black" : "white",
    styleLanguage: s.style_language || "",
    category: s.category || "",
  }
}

export interface BodyContext {
  defaultHidden?: HiddenDefaults
  /**
   * Slot names that exist as `[data-slot]` in the document being shown. A text
   * edit to a field with no live slot can't be patched in place — it needs a
   * full template re-fill (structural). null = unknown, assume all live.
   */
  liveSlots?: ReadonlySet<string> | null
}

export interface BuiltBody {
  body: RefillRequest
  /** Needs a template re-fill on the server (vs a cheap in-place text swap). */
  structural: boolean
  changedSlots: string[]
}

/**
 * The request body that turns the server's persisted state (`saved`) into the
 * editor's current state (`doc`), or null when they are identical.
 *
 * Used verbatim for both `refill/preview` and the persisting `refill`, so what
 * the user saw is exactly what gets saved. Text-only diffs send only the
 * changed slots (cheap text swap, merges with concurrent edits); anything
 * structural sends the full structural state and always an explicit `hidden`
 * list, which is what forces the server down its deterministic re-fill path.
 */
export function buildRefillBody(
  doc: EditorDoc,
  saved: EditorDoc,
  ctx: BodyContext = {}
): BuiltBody | null {
  const changedSlots = changedSlotNames(doc.slots, saved.slots).filter((n) => n in doc.slots)
  const tplChanged = doc.templateId !== saved.templateId
  const dsChanged = doc.designSystemId !== saved.designSystemId
  const groundChanged = doc.ground !== saved.ground
  const languageChanged = doc.styleLanguage !== saved.styleLanguage
  const categoryChanged = doc.category !== saved.category
  const hiddenChanged = !sameList(
    effectiveHidden(doc, ctx.defaultHidden),
    effectiveHidden(saved, ctx.defaultHidden)
  )
  const posChanged = doc.mediaPosition !== saved.mediaPosition
  const mediaChanged = !mediaEqual(doc.media, saved.media)
  const live = ctx.liveSlots
  const slotStructural = !!live && changedSlots.some((n) => !live.has(n))
  const structural =
    tplChanged ||
    dsChanged ||
    groundChanged ||
    languageChanged ||
    categoryChanged ||
    hiddenChanged ||
    posChanged ||
    mediaChanged ||
    slotStructural
  if (!structural && changedSlots.length === 0) return null

  const body: RefillRequest = {}
  if (changedSlots.length > 0) {
    body.slots = Object.fromEntries(changedSlots.map((n) => [n, doc.slots[n]]))
  }
  if (dsChanged) body.design_system_id = doc.designSystemId
  if (groundChanged) body.ground = doc.ground
  if (languageChanged) body.style_language = doc.styleLanguage
  if (categoryChanged) body.category = doc.category
  if (structural) {
    body.template_id = doc.templateId
    body.hidden = [...effectiveHidden(doc, ctx.defaultHidden)]
    body.media_position = doc.mediaPosition
    if (mediaChanged && doc.media) body.media = mediaToBody(doc.media)
  }
  return { body, structural, changedSlots }
}

/** Stable cache key for a document state + the server revision it sits on. */
export function docKey(doc: EditorDoc, revision: number, defaults?: HiddenDefaults): string {
  const slotEntries = Object.keys(doc.slots)
    .sort()
    .map((k) => [k, doc.slots[k]])
  return JSON.stringify([
    revision,
    doc.templateId,
    doc.designSystemId,
    doc.ground,
    doc.styleLanguage,
    doc.category,
    [...effectiveHidden(doc, defaults)].sort(),
    doc.mediaPosition,
    mediaFingerprint(doc.media),
    slotEntries,
  ])
}

// ─── The store ─────────────────────────────────────────────────────────────

interface HistoryEntry {
  doc: EditorDoc
}

export interface StoreOptions {
  /** Consecutive edits of the same field within this window form one undo step. */
  coalesceMs?: number
  maxHistory?: number
  now?: () => number
}

export class EditorStore {
  private _doc: EditorDoc
  private _saved: EditorDoc
  private undoStack: HistoryEntry[] = []
  private redoStack: HistoryEntry[] = []
  private listeners = new Set<(c: StoreChange) => void>()
  private lastKey: string | null = null
  private lastAt = 0
  private readonly coalesceMs: number
  private readonly maxHistory: number
  private readonly now: () => number
  /** Bumps on every document change — the React snapshot. */
  version = 0

  constructor(initial: EditorDoc, opts: StoreOptions = {}) {
    this._doc = initial
    this._saved = initial
    this.coalesceMs = opts.coalesceMs ?? 900
    this.maxHistory = opts.maxHistory ?? 200
    this.now = opts.now ?? (() => Date.now())
  }

  get doc(): EditorDoc {
    return this._doc
  }
  get saved(): EditorDoc {
    return this._saved
  }
  get canUndo(): boolean {
    return this.undoStack.length > 0
  }
  get canRedo(): boolean {
    return this.redoStack.length > 0
  }
  isDirty(): boolean {
    return !docEquals(this._doc, this._saved)
  }

  subscribe(listener: (c: StoreChange) => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private notify(change: StoreChange): void {
    this.version++
    for (const l of [...this.listeners]) {
      try {
        l(change)
      } catch (err) {
        // A misbehaving subscriber must never break editing.
        console.error("[editor-store] listener failed", err)
      }
    }
  }

  private apply(next: EditorDoc, source: ChangeSource, continuous = false): void {
    const prev = this._doc
    this._doc = next
    this.notify({
      source,
      slots: changedSlotNames(prev.slots, next.slots),
      structural: !sameStructure(prev, next),
      continuous,
      reset: false,
    })
  }

  private commit(
    next: EditorDoc,
    source: ChangeSource,
    key: string | null,
    continuous = false
  ): boolean {
    if (docEquals(next, this._doc)) return false
    const t = this.now()
    const coalesce = key !== null && key === this.lastKey && t - this.lastAt <= this.coalesceMs
    if (!coalesce) {
      this.undoStack.push({ doc: this._doc })
      if (this.undoStack.length > this.maxHistory) this.undoStack.shift()
    }
    this.redoStack = []
    this.lastKey = key
    this.lastAt = t
    this.apply(next, source, continuous)
    return true
  }

  // ── Edits ────────────────────────────────────────────────────────────────

  setSlot(name: string, text: string, source: ChangeSource = "form"): boolean {
    if ((this._doc.slots[name] ?? "") === text) return false
    return this.commit(
      { ...this._doc, slots: { ...this._doc.slots, [name]: text } },
      source,
      `slot:${name}`
    )
  }

  /** Several slots as one undo step (paste, template-driven fill). */
  setSlots(map: Record<string, string>, source: ChangeSource = "form"): boolean {
    const merged = { ...this._doc.slots, ...map }
    return this.commit({ ...this._doc, slots: merged }, source, null)
  }

  /** Switching template resets toggles + position to the new template's defaults. */
  setTemplate(templateId: string): boolean {
    if (templateId === this._doc.templateId) return false
    return this.commit(
      { ...this._doc, templateId, hidden: null, mediaPosition: "auto" },
      "form",
      null
    )
  }

  /**
   * Switching design system remaps the template (caller resolves the target
   * id, "" = let the server pick) and resets toggles + position — one commit,
   * one undo step, like Manual Compose's system switch.
   */
  setDesignSystem(designSystemId: string, templateId: string): boolean {
    if (designSystemId === this._doc.designSystemId && templateId === this._doc.templateId) {
      return false
    }
    return this.commit(
      { ...this._doc, designSystemId, templateId, hidden: null, mediaPosition: "auto" },
      "form",
      null
    )
  }

  setHidden(hidden: readonly string[] | null): boolean {
    return this.commit({ ...this._doc, hidden: hidden ? [...hidden] : null }, "form", null)
  }

  /** Switch the post's ground (white/black). A full re-fill, one undo step. */
  setGround(ground: "white" | "black"): boolean {
    if (ground === this._doc.ground) return false
    return this.commit({ ...this._doc, ground }, "form", null)
  }

  /** Switch the post's design language. "" = the design system's own. */
  setStyleLanguage(styleLanguage: string): boolean {
    if (styleLanguage === this._doc.styleLanguage) return false
    return this.commit({ ...this._doc, styleLanguage }, "form", null)
  }

  setCategory(category: string): boolean {
    if (category === this._doc.category) return false
    return this.commit({ ...this._doc, category }, "form", null)
  }

  setMediaPosition(pos: string): boolean {
    return this.commit({ ...this._doc, mediaPosition: pos }, "form", null)
  }

  setMedia(media: MediaChoice, continuous = false): boolean {
    // Alt-text typing coalesces into one step; everything else is its own.
    const key = continuous && media.kind === "upload" ? "media:alt" : null
    return this.commit({ ...this._doc, media }, "form", key, continuous)
  }

  // ── History ──────────────────────────────────────────────────────────────

  private step(from: HistoryEntry[], to: HistoryEntry[], source: ChangeSource): UndoResult {
    let mediaKept = false
    while (from.length > 0) {
      const entry = from.pop() as HistoryEntry
      let target = entry.doc
      // Media that already reached the server can't be un-baked: the original
      // bytes are gone. Keep it rather than pretend to restore it.
      if (target.media === null && this._saved.media !== null) {
        target = { ...target, media: this._saved.media }
        mediaKept = true
      }
      if (docEquals(target, this._doc)) continue // a no-op step — keep looking
      to.push({ doc: this._doc })
      this.lastKey = null
      this.apply(target, source)
      return { ok: true, mediaKept }
    }
    return { ok: false, mediaKept }
  }

  undo(): UndoResult {
    return this.step(this.undoStack, this.redoStack, "undo")
  }

  redo(): UndoResult {
    return this.step(this.redoStack, this.undoStack, "redo")
  }

  // ── Server sync ──────────────────────────────────────────────────────────

  /** The server persisted `doc` (a snapshot taken when the save was sent). */
  markSaved(doc: EditorDoc): void {
    this._saved = doc
  }

  /**
   * Fields the server rendered that the form didn't know about (e.g. a kicker
   * derived from the category). Adopted silently into doc AND baseline — they
   * are server truth, not a user edit, so they never make the store dirty.
   */
  adoptSlots(incoming: Record<string, string>): void {
    const add: Record<string, string> = {}
    for (const [k, v] of Object.entries(incoming)) if (!(k in this._doc.slots)) add[k] = v
    if (Object.keys(add).length === 0) return
    this._doc = { ...this._doc, slots: { ...this._doc.slots, ...add } }
    this._saved = { ...this._saved, slots: { ...this._saved.slots, ...add } }
    this.notify({
      source: "system",
      slots: Object.keys(add),
      structural: false,
      continuous: false,
      reset: false,
    })
  }

  /**
   * A structural change failed on the server — roll the visible structure
   * back to `good` (the last one that rendered) while keeping typed text. The
   * failed steps leave the undo stack too.
   */
  revertStructure(good: Structure): void {
    let i = this.undoStack.length - 1
    while (i >= 0 && !sameStructure(this.undoStack[i].doc, good)) i--
    if (i >= 0) this.undoStack.length = i
    this.redoStack = []
    this.lastKey = null
    this.apply({ ...this._doc, ...good }, "revert")
  }

  /** Replace everything (initial load, discard, reload after conversion). */
  replace(doc: EditorDoc): void {
    this._doc = doc
    this._saved = doc
    this.undoStack = []
    this.redoStack = []
    this.lastKey = null
    this.notify({
      source: "system",
      slots: Object.keys(doc.slots),
      structural: true,
      continuous: false,
      reset: true,
    })
  }
}
