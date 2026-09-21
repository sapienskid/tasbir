// Typed error classification for the structured editor. Pure — no React, no
// network — so the save queue / preview sequencer / UI all agree on what is
// worth retrying, what is the user's problem, and what to say about it.

export type EditorErrorKind =
  | "aborted" // request cancelled by us (latest-wins) — never surfaced
  | "auth" // 401 — missing / invalid API key
  | "notfound" // 404 — task / format / files gone (expired?)
  | "conflict" // 409 — task still processing
  | "invalid" // 400 / 413 / 422 — the request itself is wrong
  | "ratelimit" // 429 — slow down, retry later
  | "server" // 5xx
  | "network" // fetch failed (offline, dropped connection, CORS…)
  | "unknown"

export interface EditorError {
  kind: EditorErrorKind
  status: number
  /** Human message, safe to toast (the server's `detail` when there is one). */
  message: string
  /** Worth retrying automatically with backoff. */
  retryable: boolean
  /** Server-suggested wait, when it sent Retry-After. */
  retryAfterMs?: number
}

interface ErrorLike {
  name?: unknown
  message?: unknown
  status?: unknown
  retryAfterMs?: unknown
}

export function classifyError(err: unknown): EditorError {
  const e = (typeof err === "object" && err !== null ? err : {}) as ErrorLike
  const name = typeof e.name === "string" ? e.name : ""
  const raw = typeof e.message === "string" ? e.message : ""
  if (name === "AbortError") {
    return { kind: "aborted", status: 0, message: "Cancelled", retryable: false }
  }
  const status = typeof e.status === "number" ? e.status : 0
  if (status === 0) {
    // fetch() rejects with a TypeError for network-level failures.
    if (name === "TypeError" || /failed to fetch|network|load failed|fetch/i.test(raw)) {
      return {
        kind: "network",
        status: 0,
        message: "Can't reach the server — check your connection",
        retryable: true,
      }
    }
    return { kind: "unknown", status: 0, message: raw || "Unexpected error", retryable: false }
  }
  const retryAfterMs = typeof e.retryAfterMs === "number" ? e.retryAfterMs : undefined
  const message = raw || `Request failed (${status})`
  if (status === 401) return { kind: "auth", status, message, retryable: false }
  if (status === 404) return { kind: "notfound", status, message, retryable: false }
  if (status === 409) return { kind: "conflict", status, message, retryable: false }
  if (status === 429) {
    return {
      kind: "ratelimit",
      status,
      message: "Too many requests — slowing down",
      retryable: true,
      retryAfterMs,
    }
  }
  if (status >= 500) {
    return { kind: "server", status, message, retryable: true, retryAfterMs }
  }
  if (status >= 400) return { kind: "invalid", status, message, retryable: false }
  return { kind: "unknown", status, message, retryable: false }
}

/** True for errors that come from our own cancellation, never shown to users. */
export function isAbort(err: unknown): boolean {
  return classifyError(err).kind === "aborted"
}

/** Exponential backoff (ms) for attempt n (0-based), capped, honoring Retry-After. */
export function backoffMs(
  attempt: number,
  opts: { baseMs?: number; maxMs?: number; retryAfterMs?: number } = {}
): number {
  const base = opts.baseMs ?? 1000
  const max = opts.maxMs ?? 30_000
  const exp = Math.min(max, base * 2 ** Math.max(0, attempt))
  return Math.max(exp, opts.retryAfterMs ?? 0)
}
