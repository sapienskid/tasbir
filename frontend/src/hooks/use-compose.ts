import { useEffect, useRef, useState } from "react"
import useSWR from "swr"
import {
  composePreview,
  getComposeBatch,
  getComposeIllustration,
  type ComposeBatch,
  type ComposeGround,
  type ComposePreviewRequest,
  type ComposePreviewResponse,
} from "@/lib/api"
import { specKey } from "@/components/compose/model"

// ─── Slide preview (debounced POST /compose/preview + session cache) ──────

// Small LRU keyed by the compact spec key, shared by the main preview and the
// rail thumbnails so switching slides back and forth never re-renders.
const PREVIEW_CACHE_MAX = 80
const previewCache = new Map<string, ComposePreviewResponse>()

function cacheGet(key: string): ComposePreviewResponse | undefined {
  const hit = previewCache.get(key)
  if (hit) {
    previewCache.delete(key)
    previewCache.set(key, hit)
  }
  return hit
}

function cacheSet(key: string, value: ComposePreviewResponse): void {
  previewCache.set(key, value)
  while (previewCache.size > PREVIEW_CACHE_MAX) {
    const oldest = previewCache.keys().next().value
    if (oldest === undefined) break
    previewCache.delete(oldest)
  }
}

// In-flight requests by key, so the main canvas and a rail thumbnail asking
// for the same slide share one POST.
const inflight = new Map<string, Promise<ComposePreviewResponse>>()

function fetchPreview(key: string, body: ComposePreviewRequest): Promise<ComposePreviewResponse> {
  const cached = cacheGet(key)
  if (cached) return Promise.resolve(cached)
  let p = inflight.get(key)
  if (!p) {
    p = composePreview(body)
      .then((res) => {
        cacheSet(key, res)
        return res
      })
      .finally(() => inflight.delete(key))
    inflight.set(key, p)
  }
  return p
}

export interface SlidePreviewState {
  data: ComposePreviewResponse | null
  error: string | null
  loading: boolean
}

/**
 * Debounced live preview of one slide. `req` null (or `enabled` false)
 * pauses fetching; the last good render stays visible while a newer one loads.
 */
export function useSlidePreview(
  req: ComposePreviewRequest | null,
  { delay = 350, enabled = true }: { delay?: number; enabled?: boolean } = {}
): SlidePreviewState {
  const key = req && req.slide.template_id ? specKey(req) : null
  const reqRef = useRef(req)
  reqRef.current = req
  const [state, setState] = useState<SlidePreviewState>(() => ({
    data: key ? (cacheGet(key) ?? null) : null,
    error: null,
    loading: false,
  }))

  useEffect(() => {
    if (!key || !enabled) return
    const cached = cacheGet(key)
    if (cached) {
      setState({ data: cached, error: null, loading: false })
      return
    }
    let alive = true
    setState((s) => ({ ...s, loading: true, error: null }))
    const t = setTimeout(() => {
      const body = reqRef.current
      if (!body) return
      fetchPreview(key, body)
        .then((res) => {
          if (alive) setState({ data: res, error: null, loading: false })
        })
        .catch((err: unknown) => {
          if (!alive) return
          setState((s) => ({
            ...s,
            loading: false,
            error: err instanceof Error ? err.message : "Preview failed",
          }))
        })
    }, delay)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [key, enabled, delay])

  if (!key) return { data: null, error: null, loading: false }
  return state
}

// ─── Illustration thumbnail ────────────────────────────────────────────────

export function useIllustration(style: string, seed: string, ground: ComposeGround) {
  return useSWR(
    style && seed ? `/compose/illustration?${style}&${seed}&${ground}` : null,
    () => getComposeIllustration(style, seed, ground),
    { dedupingInterval: Infinity, revalidateOnFocus: false, shouldRetryOnError: false }
  )
}

// ─── Batch status ──────────────────────────────────────────────────────────

export function isSettledStatus(status: string): boolean {
  return status === "done" || status === "completed" || status === "failed"
}

/** GET /compose/batches/{id}, polled every 2s until every task settles. */
export function useComposeBatch(batchId: string | null) {
  return useSWR<ComposeBatch>(
    batchId ? `/compose/batches/${batchId}` : null,
    () => getComposeBatch(batchId as string),
    {
      refreshInterval: (latest) =>
        latest && latest.tasks.every((t) => isSettledStatus(t.status)) ? 0 : 2000,
      revalidateOnFocus: false,
    }
  )
}

// ─── Unsaved-changes guard + draft autosave ────────────────────────────────

export function useBeforeUnload(dirty: boolean): void {
  useEffect(() => {
    if (!dirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ""
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [dirty])
}

const DRAFT_PREFIX = "tasbir:compose-draft:v1"

export function draftStorageKey(batchId?: string): string {
  return batchId ? `${DRAFT_PREFIX}:${batchId}` : DRAFT_PREFIX
}

export function readDraft<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

export function clearDraft(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    /* storage unavailable */
  }
}

/**
 * Debounced localStorage autosave (per-viewer convenience only). Large
 * uploads can blow the quota — the fallback drops upload payloads.
 */
export function useDraftAutosave<T>(
  key: string,
  value: T,
  enabled: boolean,
  stripHeavy: (v: T) => T
): void {
  useEffect(() => {
    if (!enabled) return
    const t = setTimeout(() => {
      try {
        localStorage.setItem(key, JSON.stringify(value))
      } catch {
        try {
          localStorage.setItem(key, JSON.stringify(stripHeavy(value)))
        } catch {
          /* storage unavailable — skip */
        }
      }
    }, 800)
    return () => clearTimeout(t)
  }, [key, value, enabled, stripHeavy])
}
