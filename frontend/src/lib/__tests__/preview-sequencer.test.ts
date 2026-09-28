import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { PreviewSequencer } from "@/lib/preview-sequencer"

interface Req {
  k: string
}
interface Deferred {
  req: Req
  signal: AbortSignal
  resolve: (v: string) => void
  reject: (e: unknown) => void
}

function harness(opts: { shouldRetry?: (e: unknown) => boolean; maxRetries?: number } = {}) {
  const calls: Deferred[] = []
  const results: Array<{ res: string; fromCache: boolean }> = []
  const errors: unknown[] = []
  const busy: boolean[] = []
  const seq = new PreviewSequencer<Req, string>({
    fetch: (req, signal) =>
      new Promise<string>((resolve, reject) => {
        calls.push({ req, signal, resolve, reject })
        signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })))
      }),
    keyOf: (r) => r.k,
    onResult: (res, m) => results.push({ res, fromCache: m.fromCache }),
    onError: (e) => errors.push(e),
    onBusy: (b) => busy.push(b),
    shouldRetry: opts.shouldRetry,
    maxRetries: opts.maxRetries,
  })
  return { seq, calls, results, errors, busy }
}

const flush = () => Promise.resolve().then(() => Promise.resolve())

beforeEach(() => {
  vi.useFakeTimers()
})
afterEach(() => {
  vi.useRealTimers()
})

describe("PreviewSequencer latest-wins", () => {
  it("fires immediately for delay 0 and delivers the result", async () => {
    const h = harness()
    h.seq.request({ k: "a" })
    expect(h.calls).toHaveLength(1)
    h.calls[0].resolve("HTML-A")
    await flush()
    expect(h.results).toEqual([{ res: "HTML-A", fromCache: false }])
    expect(h.busy).toEqual([true, false])
  })

  it("debounces continuous input: only the last request fetches", async () => {
    const h = harness()
    h.seq.request({ k: "1" }, { delayMs: 120 })
    h.seq.request({ k: "2" }, { delayMs: 120 })
    h.seq.request({ k: "3" }, { delayMs: 120 })
    expect(h.calls).toHaveLength(0)
    vi.advanceTimersByTime(119)
    expect(h.calls).toHaveLength(0)
    vi.advanceTimersByTime(2)
    expect(h.calls.map((c) => c.req.k)).toEqual(["3"])
  })

  it("aborts the superseded in-flight fetch and never delivers it", async () => {
    const h = harness()
    h.seq.request({ k: "a" })
    h.seq.request({ k: "b" })
    expect(h.calls[0].signal.aborted).toBe(true)
    h.calls[1].resolve("B")
    await flush()
    expect(h.results.map((r) => r.res)).toEqual(["B"])
    expect(h.errors).toEqual([])
  })

  it("drops a LATE answer to an older request that could not be aborted", async () => {
    // A fetch that ignores its abort signal (e.g. a proxy) answers late.
    const results: string[] = []
    const resolvers: Array<(v: string) => void> = []
    const seq = new PreviewSequencer<Req, string>({
      fetch: () => new Promise<string>((res) => resolvers.push(res)),
      keyOf: (r) => r.k,
      onResult: (r) => results.push(r),
      onError: () => {},
    })
    seq.request({ k: "first" })
    seq.request({ k: "second" })
    resolvers[1]("SECOND") // newest answers first
    await flush()
    resolvers[0]("FIRST") // stale answer arrives afterwards
    await flush()
    expect(results).toEqual(["SECOND"])
    // …but it was cached, so going back is instant and synchronous.
    seq.request({ k: "first" })
    expect(results).toEqual(["SECOND", "FIRST"])
  })

  it("serves repeat states from the cache synchronously, without fetching", async () => {
    const h = harness()
    h.seq.request({ k: "a" })
    h.calls[0].resolve("A")
    await flush()
    h.seq.request({ k: "b" })
    h.calls[1].resolve("B")
    await flush()
    h.seq.request({ k: "a" })
    expect(h.calls).toHaveLength(2)
    expect(h.results.at(-1)).toEqual({ res: "A", fromCache: true })
  })

  it("re-requesting the in-flight key lets it land instead of refetching", async () => {
    const h = harness()
    h.seq.request({ k: "a" })
    h.seq.request({ k: "a" })
    expect(h.calls).toHaveLength(1)
    expect(h.calls[0].signal.aborted).toBe(false)
    h.calls[0].resolve("A")
    await flush()
    expect(h.results).toHaveLength(1)
  })

  it("seeded entries are cache hits", () => {
    const h = harness()
    h.seq.seed("s", "SEED")
    h.seq.request({ k: "s" })
    expect(h.results).toEqual([{ res: "SEED", fromCache: true }])
    expect(h.calls).toHaveLength(0)
  })

  it("evicts least-recently-used entries", async () => {
    const results: string[] = []
    const seq = new PreviewSequencer<Req, string>({
      fetch: async (r) => `H-${r.k}`,
      keyOf: (r) => r.k,
      onResult: (r, m) => results.push(`${r}${m.fromCache ? "*" : ""}`),
      onError: () => {},
      cacheSize: 2,
    })
    for (const k of ["a", "b", "c"]) {
      seq.request({ k })
      await flush()
    }
    seq.request({ k: "c" }) // cached
    seq.request({ k: "a" }) // evicted → fetch
    await flush()
    expect(results).toEqual(["H-a", "H-b", "H-c", "H-c*", "H-a"])
  })
})

describe("PreviewSequencer errors", () => {
  it("reports a non-retryable error once, for the latest request only", async () => {
    const h = harness()
    h.seq.request({ k: "a" })
    h.calls[0].reject(Object.assign(new Error("nope"), { status: 422 }))
    await flush()
    expect(h.errors).toHaveLength(1)
    expect(h.busy.at(-1)).toBe(false)
  })

  it("never reports the error of a superseded request", async () => {
    const h = harness()
    h.seq.request({ k: "a" })
    h.seq.request({ k: "b" })
    h.calls[0].reject(new Error("late failure"))
    await flush()
    expect(h.errors).toEqual([])
  })

  it("retries transient failures with backoff, then succeeds", async () => {
    const h = harness({ shouldRetry: () => true })
    h.seq.request({ k: "a" })
    h.calls[0].reject(new Error("503"))
    await flush()
    expect(h.calls).toHaveLength(1)
    vi.advanceTimersByTime(400)
    expect(h.calls).toHaveLength(2)
    h.calls[1].resolve("OK")
    await flush()
    expect(h.results.map((r) => r.res)).toEqual(["OK"])
    expect(h.errors).toEqual([])
  })

  it("gives up after maxRetries and surfaces the error", async () => {
    const h = harness({ shouldRetry: () => true, maxRetries: 1 })
    h.seq.request({ k: "a" })
    h.calls[0].reject(new Error("x"))
    await flush()
    vi.advanceTimersByTime(400)
    h.calls[1].reject(new Error("x"))
    await flush()
    expect(h.errors).toHaveLength(1)
    expect(h.calls).toHaveLength(2)
  })

  it("a new request cancels a pending retry", async () => {
    const h = harness({ shouldRetry: () => true })
    h.seq.request({ k: "a" })
    h.calls[0].reject(new Error("x"))
    await flush()
    h.seq.request({ k: "b" })
    vi.advanceTimersByTime(5000)
    expect(h.calls.map((c) => c.req.k)).toEqual(["a", "b"])
  })

  it("dispose stops delivery", async () => {
    const h = harness()
    h.seq.request({ k: "a" })
    h.seq.dispose()
    expect(h.calls[0].signal.aborted).toBe(true)
    h.seq.request({ k: "b" })
    expect(h.calls).toHaveLength(1)
  })
})
