// Latest-wins fetching of server previews.
//
// The editor asks for a preview on every structural change (template click,
// toggle, media, …). Requests can overlap and answers can arrive out of
// order; the user must only ever see the answer to the LAST thing they asked
// for. This class owns that rule:
//
//  * `request()` records the wanted key and supersedes whatever was pending
//    or in flight (the in-flight fetch is aborted unless it's the same key).
//  * A result is delivered only if its key is still the wanted one. Stale
//    results are still cached, so toggling back and forth is instant.
//  * An LRU cache serves repeat states synchronously.
//  * Retryable failures (network / 5xx / 429) retry with backoff while the
//    request is still wanted; the rest surface once via `onError`.
//
// Pure: timers and fetch are injected, so it is tested with fake timers.

export interface SequencerOptions<Req, Res> {
  fetch: (req: Req, signal: AbortSignal) => Promise<Res>
  keyOf: (req: Req) => string
  /** Only the latest wanted request's result / error is ever delivered. */
  onResult: (res: Res, meta: { key: string; fromCache: boolean }) => void
  onError: (err: unknown, meta: { key: string }) => void
  onBusy?: (busy: boolean) => void
  /** Decide whether a failure is worth another attempt. */
  shouldRetry?: (err: unknown) => boolean
  /** Server-suggested delay for a failed attempt, if any. */
  retryDelay?: (err: unknown, attempt: number) => number
  maxRetries?: number
  cacheSize?: number
  setTimer?: (fn: () => void, ms: number) => unknown
  clearTimer?: (h: unknown) => void
}

export class PreviewSequencer<Req, Res> {
  private wantedKey: string | null = null
  private timer: unknown = null
  private inflight: { key: string; controller: AbortController } | null = null
  private cache = new Map<string, Res>()
  private busy = false
  private readonly cacheSize: number
  private readonly maxRetries: number
  private readonly setTimer: (fn: () => void, ms: number) => unknown
  private readonly clearTimer: (h: unknown) => void
  private disposed = false

  constructor(private readonly opts: SequencerOptions<Req, Res>) {
    this.cacheSize = opts.cacheSize ?? 40
    this.maxRetries = opts.maxRetries ?? 2
    this.setTimer = opts.setTimer ?? ((fn, ms) => setTimeout(fn, ms))
    this.clearTimer = opts.clearTimer ?? ((h) => clearTimeout(h as ReturnType<typeof setTimeout>))
  }

  get isBusy(): boolean {
    return this.busy
  }

  private setBusy(b: boolean): void {
    if (this.busy === b) return
    this.busy = b
    this.opts.onBusy?.(b)
  }

  private cacheGet(key: string): Res | undefined {
    const hit = this.cache.get(key)
    if (hit !== undefined) {
      this.cache.delete(key)
      this.cache.set(key, hit)
    }
    return hit
  }

  private cacheSet(key: string, res: Res): void {
    this.cache.set(key, res)
    while (this.cache.size > this.cacheSize) {
      const oldest = this.cache.keys().next().value
      if (oldest === undefined) break
      this.cache.delete(oldest)
    }
  }

  /** Seed the cache (e.g. with the document the editor opened on). */
  seed(key: string, res: Res): void {
    this.cacheSet(key, res)
  }

  clearCache(): void {
    this.cache.clear()
  }

  /**
   * Ask for a preview. `delayMs` 0 fires immediately (clicks); a small delay
   * debounces continuous input. Cache hits are delivered synchronously.
   */
  request(req: Req, opts: { delayMs?: number } = {}): void {
    if (this.disposed) return
    const key = this.opts.keyOf(req)
    this.wantedKey = key
    if (this.timer !== null) {
      this.clearTimer(this.timer)
      this.timer = null
    }

    const cached = this.cacheGet(key)
    if (cached !== undefined) {
      this.abortInflight()
      this.setBusy(false)
      this.opts.onResult(cached, { key, fromCache: true })
      return
    }

    // Already fetching exactly this — let it land.
    if (this.inflight && this.inflight.key === key) {
      this.setBusy(true)
      return
    }
    this.abortInflight()
    this.setBusy(true)

    const delay = opts.delayMs ?? 0
    if (delay <= 0) {
      void this.run(req, key, 0)
    } else {
      this.timer = this.setTimer(() => {
        this.timer = null
        void this.run(req, key, 0)
      }, delay)
    }
  }

  private abortInflight(): void {
    if (this.inflight) {
      this.inflight.controller.abort()
      this.inflight = null
    }
  }

  private async run(req: Req, key: string, attempt: number): Promise<void> {
    if (this.disposed || this.wantedKey !== key) return
    const controller = new AbortController()
    this.inflight = { key, controller }
    try {
      const res = await this.opts.fetch(req, controller.signal)
      this.cacheSet(key, res)
      if (this.disposed || this.wantedKey !== key) return // stale — cached only
      this.inflight = null
      this.setBusy(false)
      this.opts.onResult(res, { key, fromCache: false })
    } catch (err) {
      if (controller.signal.aborted || this.disposed) return
      if (this.wantedKey !== key) return
      this.inflight = null
      const retry = this.opts.shouldRetry?.(err) ?? false
      if (retry && attempt < this.maxRetries) {
        const wait = this.opts.retryDelay?.(err, attempt) ?? 400 * 2 ** attempt
        this.timer = this.setTimer(() => {
          this.timer = null
          void this.run(req, key, attempt + 1)
        }, wait)
        return
      }
      this.setBusy(false)
      this.opts.onError(err, { key })
    }
  }

  /** Stop everything pending; nothing more is delivered for the old wants. */
  cancel(): void {
    this.wantedKey = null
    if (this.timer !== null) {
      this.clearTimer(this.timer)
      this.timer = null
    }
    this.abortInflight()
    this.setBusy(false)
  }

  dispose(): void {
    this.cancel()
    this.disposed = true
    this.cache.clear()
  }
}
