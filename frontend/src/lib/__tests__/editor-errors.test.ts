import { describe, expect, it } from "vitest"
import { backoffMs, classifyError, isAbort } from "@/lib/editor-errors"

const api = (status: number, message = "msg", retryAfterMs?: number) =>
  Object.assign(new Error(message), { name: "ApiError", status, retryAfterMs })

describe("classifyError", () => {
  it.each([
    [401, "auth", false],
    [404, "notfound", false],
    [409, "conflict", false],
    [422, "invalid", false],
    [413, "invalid", false],
    [429, "ratelimit", true],
    [500, "server", true],
    [503, "server", true],
  ])("status %i → %s (retryable=%s)", (status, kind, retryable) => {
    const e = classifyError(api(status))
    expect(e.kind).toBe(kind)
    expect(e.retryable).toBe(retryable)
  })

  it("keeps the server detail for user-facing kinds", () => {
    expect(classifyError(api(422, "Template 'x' not found")).message).toBe("Template 'x' not found")
    expect(classifyError(api(409, "Task is still processing")).message).toBe("Task is still processing")
  })

  it("recognises aborts and network failures", () => {
    expect(isAbort(new DOMException("x", "AbortError"))).toBe(true)
    expect(classifyError(new TypeError("Failed to fetch"))).toMatchObject({ kind: "network", retryable: true })
    expect(classifyError("weird")).toMatchObject({ kind: "unknown", retryable: false })
    expect(classifyError(null).kind).toBe("unknown")
  })

  it("carries Retry-After", () => {
    expect(classifyError(api(429, "x", 4000)).retryAfterMs).toBe(4000)
  })
})

describe("backoffMs", () => {
  it("grows exponentially, caps, and honors Retry-After", () => {
    expect(backoffMs(0)).toBe(1000)
    expect(backoffMs(1)).toBe(2000)
    expect(backoffMs(3)).toBe(8000)
    expect(backoffMs(20)).toBe(30_000)
    expect(backoffMs(0, { retryAfterMs: 9000 })).toBe(9000)
  })
})
