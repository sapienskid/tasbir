// Background, coalesced persistence.
//
// Every edit marks the queue dirty. After `idleMs` without further edits it
// persists — ONE request in flight at a time, always built from the LATEST
// state at send time (`prepare()`), so nothing ever queues up behind a slow
// save and stale snapshots are never sent. Edits made while a save is in
// flight simply trigger the next one when it lands.
//
// Failures: retryable ones (network / 5xx / 429) back off exponentially and
// keep the state dirty; hard ones (404 / 409 / 422) stop and surface the
// message, and are retried on the next edit or a manual `retryNow()`.
//
// Pure: no React, no fetch; timers injected for tests.

import { backoffMs, classifyError, type EditorError } from "@/lib/editor-errors"

export type SavePhase = "saved" | "dirty" | "saving" | "error"

export interface SaveSnapshot {
  phase: SavePhase
  /** Epoch ms of the last successful persist. */
  lastSavedAt: number | null
  error: EditorError | null
  /** Auto-retry scheduled in ms (null when not waiting on a retry). */
  retryInMs: number | null
  attempts: number
}

export interface SaveQueueOptions<P, R> {
  /** Build the payload from the latest state; null = nothing to save. */
  prepare: () => { payload: P; token: unknown } | null
  send: (payload: P, ctx: { keepalive: boolean; render: boolean }) => Promise<R>
  onSaved: (token: unknown, result: R) => void
  onChange?: (snap: SaveSnapshot) => void
  idleMs?: number
  /** Persist even during continuous typing after this long. */
  maxWaitMs?: number
  now?: () => number
  setTimer?: (fn: () => void, ms: number) => unknown
  clearTimer?: (h: unknown) => void
  backoff?: { baseMs?: number; maxMs?: number }
}

export class SaveQueue<P, R> {
  private phase: SavePhase = "saved"
  private lastSavedAt: number | null = null
  private error: EditorError | null = null
  private retryInMs: number | null = null
  private attempts = 0
  private idleTimer: unknown = null
  private retryTimer: unknown = null
  private dirtySince: number | null = null
  private loop: Promise<void> | null = null
  private wantFlush = false
  /** Set by flush({render:true}); consumed by the next send(). */
  private renderRequested = false
  private disposed = false
  private readonly idleMs: number
  private readonly maxWaitMs: number
  private readonly now: () => number
  private readonly setTimer: (fn: () => void, ms: number) => unknown
  private readonly clearTimer: (h: unknown) => void

  constructor(private readonly opts: SaveQueueOptions<P, R>) {
    this.idleMs = opts.idleMs ?? 700
    this.maxWaitMs = opts.maxWaitMs ?? 8000
    this.now = opts.now ?? (() => Date.now())
    this.setTimer = opts.setTimer ?? ((fn, ms) => setTimeout(fn, ms))
    this.clearTimer = opts.clearTimer ?? ((h) => clearTimeout(h as ReturnType<typeof setTimeout>))
  }

  get snapshot(): SaveSnapshot {
    return {
      phase: this.phase,
      lastSavedAt: this.lastSavedAt,
      error: this.error,
      retryInMs: this.retryInMs,
      attempts: this.attempts,
    }
  }

  /** True while there is anything unsaved or a save in flight. */
  get pending(): boolean {
    return this.phase !== "saved"
  }

  private emit(): void {
    this.opts.onChange?.(this.snapshot)
  }

  private setPhase(p: SavePhase): void {
    this.phase = p
    this.emit()
  }

  /** An edit happened. Restarts the idle timer (bounded by `maxWaitMs`). */
  touch(): void {
    if (this.disposed) return
    const t = this.now()
    if (this.dirtySince === null) this.dirtySince = t
    // A fresh edit after a hard failure is a fresh chance — clear the error.
    if (this.phase === "error" && this.error && !this.error.retryable) {
      this.error = null
      this.attempts = 0
    }
    if (this.phase !== "saving") this.setPhase("dirty")
    // While a retry backoff is pending, keep waiting on it — the retry will
    // pick up the latest state anyway.
    if (this.retryTimer !== null) return
    this.scheduleIdle()
  }

  private scheduleIdle(): void {
    if (this.idleTimer !== null) this.clearTimer(this.idleTimer)
    const waited = this.dirtySince === null ? 0 : this.now() - this.dirtySince
    const wait = Math.max(0, Math.min(this.idleMs, this.maxWaitMs - waited))
    this.idleTimer = this.setTimer(() => {
      this.idleTimer = null
      void this.drain()
    }, wait)
  }

  private clearTimers(): void {
    if (this.idleTimer !== null) this.clearTimer(this.idleTimer)
    if (this.retryTimer !== null) this.clearTimer(this.retryTimer)
    this.idleTimer = null
    this.retryTimer = null
    this.retryInMs = null
  }

  /**
   * Persist everything now. Resolves true once nothing is left unsaved,
   * false if the queue ended in an error state.
   *
   * `render: true` asks the server to also render the PNG and run QC — used by
   * the explicit "render now" action, since autosave deliberately skips both.
   */
  async flush(opts: { keepalive?: boolean; render?: boolean } = {}): Promise<boolean> {
    if (this.disposed) return true
    this.wantFlush = true
    this.renderRequested = opts.render ?? false
    this.clearTimers()
    try {
      await this.drain(opts.keepalive ?? false)
    } finally {
      this.wantFlush = false
      this.renderRequested = false
    }
    return this.phase === "saved"
  }

  /** Manual retry after a failure. */
  retryNow(): Promise<boolean> {
    this.error = null
    this.attempts = 0
    return this.flush()
  }

  /** Run saves until the latest state is persisted or an error stops us. */
  private drain(keepalive = false): Promise<void> {
    // One loop at a time; a flush that arrives mid-loop just flips wantFlush,
    // which the running loop checks after every save.
    if (this.loop) return this.loop
    this.loop = this.runLoop(keepalive).finally(() => {
      this.loop = null
    })
    return this.loop
  }

  private async runLoop(keepalive: boolean): Promise<void> {
    this.clearTimers()
    while (!this.disposed) {
      const job = this.opts.prepare()
      if (!job) {
        this.dirtySince = null
        this.error = null
        this.attempts = 0
        if (this.phase !== "saved") this.setPhase("saved")
        return
      }
      this.setPhase("saving")
      const ok = await this.runOne(job, keepalive).then(
        () => true,
        () => false
      )
      if (!ok) return // error handling scheduled a retry (or stopped)
      if (!this.wantFlush) {
        // Edits landed during the save: wait for idle instead of hammering.
        if (this.opts.prepare()) {
          this.setPhase("dirty")
          this.dirtySince = this.now()
          this.scheduleIdle()
          return
        }
      }
    }
  }

  private async runOne(
    job: { payload: P; token: unknown },
    keepalive: boolean
  ): Promise<void> {
    try {
      // A requested render applies to this save only.
      const render = this.renderRequested
      this.renderRequested = false
      const result = await this.opts.send(job.payload, { keepalive, render })
      this.lastSavedAt = this.now()
      this.error = null
      this.attempts = 0
      this.opts.onSaved(job.token, result)
    } catch (err) {
      const e = classifyError(err)
      this.error = e
      this.attempts += 1
      if (e.kind === "aborted") {
        // Cancelled (unload / dispose): stay dirty, no retry storm.
        this.setPhase("dirty")
      } else if (e.retryable) {
        const wait = backoffMs(this.attempts - 1, {
          baseMs: this.opts.backoff?.baseMs,
          maxMs: this.opts.backoff?.maxMs,
          retryAfterMs: e.retryAfterMs,
        })
        this.retryInMs = wait
        this.setPhase("error")
        if (this.retryTimer !== null) this.clearTimer(this.retryTimer)
        this.retryTimer = this.setTimer(() => {
          this.retryTimer = null
          this.retryInMs = null
          void this.drain()
        }, wait)
      } else {
        this.retryInMs = null
        this.setPhase("error")
      }
      throw err
    }
  }

  /** Give up on timers (route change). Unsaved state stays with the owner. */
  dispose(): void {
    this.disposed = true
    this.clearTimers()
  }
}
