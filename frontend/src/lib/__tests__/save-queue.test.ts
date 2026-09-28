import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SaveQueue, type SaveSnapshot } from "@/lib/save-queue"

/** A tiny "document" whose latest value is what prepare() snapshots. */
function harness(over: { idleMs?: number; maxWaitMs?: number } = {}) {
  let doc = 0
  let saved = 0
  const sends: Array<{ payload: number; resolve: (r: string) => void; reject: (e: unknown) => void; keepalive: boolean }> = []
  const snaps: SaveSnapshot[] = []
  const q = new SaveQueue<number, string>({
    prepare: () => (doc === saved ? null : { payload: doc, token: doc }),
    send: (payload, ctx) =>
      new Promise<string>((resolve, reject) => sends.push({ payload, resolve, reject, keepalive: ctx.keepalive })),
    onSaved: (token) => {
      saved = token as number
    },
    onChange: (s) => snaps.push(s),
    idleMs: over.idleMs ?? 700,
    maxWaitMs: over.maxWaitMs,
    backoff: { baseMs: 1000, maxMs: 8000 },
  })
  return {
    q,
    sends,
    snaps,
    edit: (v: number) => {
      doc = v
      q.touch()
    },
    get saved() {
      return saved
    },
    phases: () => snaps.map((s) => s.phase),
  }
}

const tick = async () => {
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
}

beforeEach(() => {
  vi.useFakeTimers()
})
afterEach(() => {
  vi.useRealTimers()
})

describe("SaveQueue coalescing", () => {
  it("a burst of 30 edits produces exactly one persist, with the latest state", async () => {
    const h = harness()
    for (let i = 1; i <= 30; i++) {
      h.edit(i)
      vi.advanceTimersByTime(40) // typing, well under the idle window
    }
    expect(h.sends).toHaveLength(0)
    vi.advanceTimersByTime(700)
    expect(h.sends).toHaveLength(1)
    expect(h.sends[0].payload).toBe(30)
    h.sends[0].resolve("ok")
    await tick()
    expect(h.saved).toBe(30)
    expect(h.q.snapshot.phase).toBe("saved")
    expect(h.sends).toHaveLength(1)
  })

  it("only ever has ONE request in flight; later edits ride the next save", async () => {
    const h = harness()
    h.edit(1)
    vi.advanceTimersByTime(700)
    expect(h.sends).toHaveLength(1)
    h.edit(2)
    vi.advanceTimersByTime(5000)
    expect(h.sends).toHaveLength(1) // still waiting on the first
    h.edit(3)
    h.sends[0].resolve("ok")
    await tick()
    expect(h.q.snapshot.phase).toBe("dirty")
    vi.advanceTimersByTime(700)
    expect(h.sends).toHaveLength(2)
    expect(h.sends[1].payload).toBe(3) // skipped the stale intermediate value
    h.sends[1].resolve("ok")
    await tick()
    expect(h.q.snapshot.phase).toBe("saved")
  })

  it("maxWait persists during endless typing", async () => {
    const h = harness({ maxWaitMs: 3000 })
    for (let i = 1; i <= 100; i++) {
      h.edit(i)
      vi.advanceTimersByTime(100)
    }
    expect(h.sends.length).toBeGreaterThanOrEqual(1)
  })

  it("does nothing when the state is already saved", async () => {
    const h = harness()
    h.q.touch()
    vi.advanceTimersByTime(700)
    await tick()
    expect(h.sends).toHaveLength(0)
    expect(h.q.snapshot.phase).toBe("saved")
  })
})

describe("SaveQueue flush", () => {
  it("flush persists immediately and resolves true", async () => {
    const h = harness()
    h.edit(7)
    const p = h.q.flush()
    expect(h.sends).toHaveLength(1)
    h.sends[0].resolve("ok")
    await expect(p).resolves.toBe(true)
    expect(h.saved).toBe(7)
  })

  it("flush waits for the in-flight save and then saves the newer state", async () => {
    const h = harness()
    h.edit(1)
    vi.advanceTimersByTime(700)
    h.edit(2)
    const p = h.q.flush()
    h.sends[0].resolve("ok")
    await tick()
    expect(h.sends).toHaveLength(2)
    expect(h.sends[1].payload).toBe(2)
    h.sends[1].resolve("ok")
    await expect(p).resolves.toBe(true)
  })

  it("passes keepalive through for unload flushes", async () => {
    const h = harness()
    h.edit(1)
    void h.q.flush({ keepalive: true })
    expect(h.sends[0].keepalive).toBe(true)
  })

  it("flush resolves false when the save fails", async () => {
    const h = harness()
    h.edit(1)
    const p = h.q.flush()
    h.sends[0].reject(Object.assign(new Error("bad"), { status: 422 }))
    await expect(p).resolves.toBe(false)
    expect(h.q.snapshot.phase).toBe("error")
  })
})

describe("SaveQueue failures", () => {
  it("retries transient failures with exponential backoff and stays dirty", async () => {
    const h = harness()
    h.edit(1)
    vi.advanceTimersByTime(700)
    h.sends[0].reject(Object.assign(new Error("boom"), { status: 503 }))
    await tick()
    expect(h.q.snapshot).toMatchObject({ phase: "error", retryInMs: 1000 })
    vi.advanceTimersByTime(1000)
    expect(h.sends).toHaveLength(2)
    h.sends[1].reject(new TypeError("Failed to fetch"))
    await tick()
    expect(h.q.snapshot.retryInMs).toBe(2000)
    vi.advanceTimersByTime(2000)
    h.sends[2].resolve("ok")
    await tick()
    expect(h.q.snapshot.phase).toBe("saved")
    expect(h.saved).toBe(1)
  })

  it("honors Retry-After on 429", async () => {
    const h = harness()
    h.edit(1)
    vi.advanceTimersByTime(700)
    h.sends[0].reject(Object.assign(new Error("slow"), { status: 429, retryAfterMs: 6000 }))
    await tick()
    expect(h.q.snapshot.retryInMs).toBe(6000)
  })

  it("does not auto-retry validation / conflict errors, but a new edit does", async () => {
    const h = harness()
    h.edit(1)
    vi.advanceTimersByTime(700)
    h.sends[0].reject(Object.assign(new Error("Task is still processing"), { status: 409 }))
    await tick()
    expect(h.q.snapshot.phase).toBe("error")
    expect(h.q.snapshot.error?.kind).toBe("conflict")
    vi.advanceTimersByTime(60_000)
    expect(h.sends).toHaveLength(1) // no retry storm
    h.edit(2)
    vi.advanceTimersByTime(700)
    expect(h.sends).toHaveLength(2)
    expect(h.sends[1].payload).toBe(2)
  })

  it("retryNow retries a hard failure on demand", async () => {
    const h = harness()
    h.edit(1)
    vi.advanceTimersByTime(700)
    h.sends[0].reject(Object.assign(new Error("bad"), { status: 422 }))
    await tick()
    const p = h.q.retryNow()
    expect(h.sends).toHaveLength(2)
    h.sends[1].resolve("ok")
    await expect(p).resolves.toBe(true)
  })

  it("edits during a retry backoff are picked up by the retry (latest state wins)", async () => {
    const h = harness()
    h.edit(1)
    vi.advanceTimersByTime(700)
    h.sends[0].reject(Object.assign(new Error("boom"), { status: 500 }))
    await tick()
    h.edit(2)
    h.edit(3)
    vi.advanceTimersByTime(1000)
    expect(h.sends).toHaveLength(2)
    expect(h.sends[1].payload).toBe(3)
  })

  it("dispose stops timers", async () => {
    const h = harness()
    h.edit(1)
    h.q.dispose()
    vi.advanceTimersByTime(5000)
    expect(h.sends).toHaveLength(0)
  })
})
