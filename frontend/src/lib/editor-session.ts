// One editing session per (task, format): the shared EditorStore, the
// latest-wins preview sequencer and the coalesced save queue, wired together.
// React-free; talks to the server through an injected `EditorApi`.
//
// Data flow
//   text edit   → store → (sync) iframe DOM patch          · no network
//                       → save queue (idle 700 ms → refill)
//   structural  → store (optimistic UI) → sequencer → refill/preview → swap
//                       → save queue (same body, persisting)
//   failure     → preview 4xx: revert visible structure + notify
//                 save fails: pill shows it, retry with backoff / manually

import type {
  EditorState,
  RefillPreviewResponse,
  RefillRequest,
  RefillResponse,
} from "@/lib/api"
import { classifyError, isAbort } from "@/lib/editor-errors"
import {
  EditorStore,
  buildRefillBody,
  docKey,
  editorDocFromState,
  sameStructure,
  structureOf,
  type EditorDoc,
  type HiddenDefaults,
  type Structure,
} from "@/lib/editor-store"
import { PreviewSequencer } from "@/lib/preview-sequencer"
import { SaveQueue, type SaveSnapshot } from "@/lib/save-queue"

export interface EditorApi {
  getEditor(taskId: string, fmt: string): Promise<EditorState>
  preview(
    taskId: string,
    fmt: string,
    body: RefillRequest,
    signal: AbortSignal
  ): Promise<RefillPreviewResponse>
  refill(
    taskId: string,
    fmt: string,
    body: RefillRequest,
    opts: { keepalive?: boolean }
  ): Promise<RefillResponse>
}

export interface SessionQc {
  score: number
  issues: string[]
  critique: string
  pass: boolean
}

export interface SessionSnapshot {
  phase: "loading" | "ready" | "readonly" | "error"
  info: EditorState | null
  /** Base document shown in the preview (text edits are patched on top). */
  html: string
  htmlVersion: number
  updating: boolean
  save: SaveSnapshot
  qc: SessionQc | null
  error: string | null
  canUndo: boolean
  canRedo: boolean
}

export interface SessionCallbacks {
  onPersisted?: (r: { html: string; pngB64: string; res: RefillResponse }) => void
  onNotify?: (n: { level: "error" | "info"; message: string }) => void
}

interface PreviewReq {
  key: string
  body: RefillRequest
}

// Persists for one task run one at a time: two formats' refills would
// otherwise read-modify-write the same task row concurrently.
const taskChains = new Map<string, Promise<unknown>>()
function serial<T>(taskId: string, fn: () => Promise<T>): Promise<T> {
  const prev = taskChains.get(taskId) ?? Promise.resolve()
  const next = prev.catch(() => {}).then(fn)
  taskChains.set(taskId, next)
  void next.then(
    () => {
      if (taskChains.get(taskId) === next) taskChains.delete(taskId)
    },
    () => {
      if (taskChains.get(taskId) === next) taskChains.delete(taskId)
    }
  )
  return next
}

const EMPTY_DOC: EditorDoc = {
  templateId: "",
  slots: {},
  hidden: null,
  mediaPosition: "auto",
  media: null,
  designSystemId: "default",
  ground: "white",
  styleLanguage: "",
  category: "",
}

export class EditorSession {
  readonly store = new EditorStore(EMPTY_DOC)
  callbacks: SessionCallbacks = {}
  attached = 0
  defaultHidden: HiddenDefaults | undefined

  private info: EditorState | null = null
  private phase: SessionSnapshot["phase"] = "loading"
  private html = ""
  private htmlVersion = 0
  private baseHtml = ""
  private updating = false
  private qc: SessionQc | null = null
  private error: string | null = null
  private revision = 0
  private liveSlots: ReadonlySet<string> | null = null
  private lastGood: Structure = structureOf(EMPTY_DOC)
  private wanted: Structure = structureOf(EMPTY_DOC)
  private saveSnap: SaveSnapshot = {
    phase: "saved",
    lastSavedAt: null,
    error: null,
    retryInMs: null,
    attempts: 0,
  }
  private snap: SessionSnapshot
  private listeners = new Set<() => void>()
  private loadToken = 0
  private readonly sequencer: PreviewSequencer<PreviewReq, RefillPreviewResponse>
  private readonly queue: SaveQueue<RefillRequest, RefillResponse>

  constructor(
    readonly taskId: string,
    readonly fmt: string,
    private readonly api: EditorApi
  ) {
    this.sequencer = new PreviewSequencer<PreviewReq, RefillPreviewResponse>({
      fetch: (req, signal) => this.api.preview(this.taskId, this.fmt, req.body, signal),
      keyOf: (r) => r.key,
      onResult: (res) => this.onPreview(res),
      onError: (err) => this.onPreviewError(err),
      onBusy: (b) => {
        this.updating = b
        this.emit()
      },
      shouldRetry: (e) => classifyError(e).retryable,
      retryDelay: (e, n) => classifyError(e).retryAfterMs ?? 400 * 2 ** n,
    })
    this.queue = new SaveQueue<RefillRequest, RefillResponse>({
      prepare: () => this.prepareSave(),
      send: (body, ctx) => {
        const size = JSON.stringify(body).length
        // keepalive requests are capped at 64 KB by browsers.
        const keepalive = ctx.keepalive && size < 60_000
        // Autosave persists recipe + HTML only. Rendering needs headless
        // Chromium (~3.3s) and used to ship a 128 KB base64 PNG back on every
        // keystroke-batch; recipe -> HTML is Jinja-only, so the visible editor
        // never needed it. The PNG is produced on demand via renderNow().
        const payload = ctx.render ? { ...body, render: true } : { ...body, render: false }
        return serial(this.taskId, () =>
          this.api.refill(this.taskId, this.fmt, payload, { keepalive })
        )
      },
      onSaved: (token, res) => this.onSaved(token as EditorDoc, res),
      onChange: (s) => {
        this.saveSnap = s
        this.emit()
      },
    })
    this.snap = this.buildSnapshot()
    this.store.subscribe((c) => {
      if (c.reset || c.source === "system") return
      this.queue.touch()
      if (c.source === "revert") return
      const live = this.liveSlots
      const slotStructural = !!live && c.slots.some((n) => !live.has(n))
      if (c.structural || slotStructural) this.refreshPreview(c.continuous || slotStructural)
      this.emit() // undo/redo availability
    })
  }

  // ── React binding ────────────────────────────────────────────────────────

  subscribe = (l: () => void): (() => void) => {
    this.listeners.add(l)
    return () => this.listeners.delete(l)
  }

  getSnapshot = (): SessionSnapshot => this.snap

  private buildSnapshot(): SessionSnapshot {
    return {
      phase: this.phase,
      info: this.info,
      html: this.html,
      htmlVersion: this.htmlVersion,
      updating: this.updating,
      save: this.saveSnap,
      qc: this.qc,
      error: this.error,
      canUndo: this.store.canUndo,
      canRedo: this.store.canRedo,
    }
  }

  private emit(): void {
    this.snap = this.buildSnapshot()
    for (const l of [...this.listeners]) l()
  }

  // ── Loading ──────────────────────────────────────────────────────────────

  /** Fetch editor state + the current document. Safe to call again to reload. */
  async load(loadHtml: () => Promise<string>): Promise<void> {
    const token = ++this.loadToken
    this.phase = "loading"
    this.error = null
    this.emit()
    try {
      const [info, html] = await Promise.all([
        this.api.getEditor(this.taskId, this.fmt),
        loadHtml().catch(() => ""),
      ])
      if (token !== this.loadToken) return
      this.info = info
      this.revision = info.revision ?? 0
      this.html = html
      this.baseHtml = html
      this.htmlVersion++
      if (!info.editable) {
        this.phase = "readonly"
        this.emit()
        return
      }
      const doc = editorDocFromState(info)
      this.liveSlots = new Set(Object.keys(info.slots))
      this.lastGood = structureOf(doc)
      this.wanted = structureOf(doc)
      this.sequencer.clearCache()
      this.store.replace(doc)
      this.phase = "ready"
      this.emit()
    } catch (err) {
      if (token !== this.loadToken) return
      const e = classifyError(err)
      this.phase = "error"
      this.error =
        e.kind === "notfound"
          ? "This post's files are no longer available (expired or deleted)."
          : e.message
      this.emit()
    }
  }

  // ── Preview ──────────────────────────────────────────────────────────────

  private ctx() {
    return { defaultHidden: this.defaultHidden, liveSlots: this.liveSlots }
  }

  private refreshPreview(continuous: boolean): void {
    const { doc, saved } = this.store
    const built = buildRefillBody(doc, saved, this.ctx())
    if (!built || !built.structural) {
      // Text-only (already patched into the DOM) or back to the saved state:
      // make sure the shown base matches the saved structure.
      this.sequencer.cancel()
      if (sameStructure(structureOf(doc), structureOf(saved)) && this.html !== this.baseHtml) {
        this.html = this.baseHtml
        this.htmlVersion++
        this.lastGood = structureOf(saved)
        this.emit()
      }
      return
    }
    this.wanted = structureOf(doc)
    this.sequencer.request(
      { key: docKey(doc, this.revision, this.defaultHidden), body: built.body },
      { delayMs: continuous ? 120 : 0 }
    )
  }

  private onPreview(res: RefillPreviewResponse): void {
    this.lastGood = this.wanted
    this.html = res.html
    this.htmlVersion++
    this.liveSlots = new Set(Object.keys(res.slots ?? {}))
    this.store.adoptSlots(res.slots ?? {})
    this.emit()
  }

  private onPreviewError(err: unknown): void {
    if (isAbort(err)) return
    const e = classifyError(err)
    this.store.revertStructure(this.lastGood)
    this.callbacks.onNotify?.({
      level: "error",
      message: `Couldn't update the preview — ${e.message}`,
    })
    this.emit()
  }

  // ── Saving ───────────────────────────────────────────────────────────────

  private prepareSave(): { payload: RefillRequest; token: unknown } | null {
    const { doc, saved } = this.store
    const built = buildRefillBody(doc, saved, this.ctx())
    return built ? { payload: built.body, token: doc } : null
  }

  private onSaved(sent: EditorDoc, res: RefillResponse): void {
    this.store.markSaved(sent)
    this.revision = res.revision ?? this.revision + 1
    if (res.html) {
      this.baseHtml = res.html
      // The sequencer's cache is keyed by revision, so nothing stale can hit.
    }
    // A save that skipped rendering reports no verdict — keep the previous QC
    // rather than overwriting it with "not checked".
    if (res.pass !== null && res.pass !== undefined) {
      this.qc = {
        score: res.quality.score,
        issues: res.quality.issues,
        critique: res.quality.critique,
        pass: res.pass,
      }
    }
    if (this.info) {
      this.info = {
        ...this.info,
        revision: this.revision,
        // Only a rendered save brings the PNG up to date.
        render_stale: res.rendered ? false : true,
        ground: (res.ground as EditorState["ground"]) ?? this.info.ground,
        style_language: res.style_language ?? this.info.style_language,
        category: res.category ?? this.info.category,
      }
    }
    this.callbacks.onPersisted?.({ html: res.html ?? "", pngB64: res.png_b64, res })
    // The DOM the user sees already matches what was persisted — no swap.
    this.emit()
  }

  // ── Actions ──────────────────────────────────────────────────────────────

  flush(opts: { keepalive?: boolean } = {}): Promise<boolean> {
    return this.queue.flush(opts)
  }

  /**
   * Persist and render: produces the PNG artifact and runs the hard checks.
   *
   * Autosave deliberately skips both (recipe -> HTML is Jinja-only), which
   * leaves the saved HTML ahead of the PNG on disk. This is the explicit action
   * that catches the PNG up — and it is what the "render" affordance in the
   * editor calls.
   */
  renderNow(): Promise<boolean> {
    return this.queue.flush({ render: true })
  }

  retrySave(): Promise<boolean> {
    return this.queue.retryNow()
  }

  get pending(): boolean {
    return this.queue.pending
  }

  undo(): void {
    const r = this.store.undo()
    if (r.mediaKept) {
      this.callbacks.onNotify?.({
        level: "info",
        message: "Saved media can't be un-replaced — pick another image to change it.",
      })
    }
  }

  redo(): void {
    this.store.redo()
  }

  dispose(): void {
    this.loadToken++
    this.sequencer.dispose()
    this.queue.dispose()
    this.listeners.clear()
  }
}
