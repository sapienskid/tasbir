// Typed API client for Tasbir. API key lives in versioned localStorage and
// is cached in a module-level slot so we never read storage per render.

const API_KEY_STORAGE_KEY = "tasbir:apikey:v1"

let cachedApiKey: string | null = null

export function getApiKey(): string {
  if (cachedApiKey === null) {
    try {
      cachedApiKey = localStorage.getItem(API_KEY_STORAGE_KEY) ?? ""
    } catch {
      cachedApiKey = ""
    }
  }
  return cachedApiKey
}

export function setApiKey(key: string): void {
  cachedApiKey = key
  try {
    localStorage.setItem(API_KEY_STORAGE_KEY, key)
  } catch {
    /* storage unavailable — in-memory only */
  }
}

export function clearApiKey(): void {
  cachedApiKey = ""
  try {
    localStorage.removeItem(API_KEY_STORAGE_KEY)
  } catch {
    /* noop */
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function authHeaders(init: RequestInit): Promise<Headers> {
  const headers = new Headers(init.headers)
  headers.set("x-api-key", getApiKey() ?? "")
  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json")
  }
  return headers
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = await authHeaders(init)
  const res = await fetch(path, { ...init, headers })
  if (res.status === 401) {
    throw new ApiError(401, "Invalid or missing API key — set it in Settings.")
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const apiFetcher = (path: string): Promise<unknown> => apiRequest(path)

export async function fetchBlob(path: string): Promise<Blob> {
  const headers = await authHeaders({})
  const res = await fetch(path, { headers })
  if (res.status === 401) throw new ApiError(401, "Invalid or missing API key")
  if (!res.ok) throw new ApiError(res.status, res.statusText)
  return res.blob()
}

export async function fetchText(path: string): Promise<string> {
  const headers = await authHeaders({})
  const res = await fetch(path, { headers })
  if (res.status === 401) throw new ApiError(401, "Invalid or missing API key")
  if (!res.ok) throw new ApiError(res.status, res.statusText)
  return res.text()
}

// ─── Types ────────────────────────────────────────────────────────────────

export type TaskStatus = "pending" | "running" | "completed" | "failed"

export interface TaskSummary {
  id: string
  title: string
  status: TaskStatus
  created_at: string | null
}

export interface PlatformResult {
  status: string
  quality_score: number
  quality_issues: string[]
  html_path?: string
  template_id?: string | null
  error?: string | null
  rerendered_at?: string | null
}

export interface TaskResult {
  output_paths?: Record<string, Record<string, string>>
  strategic_brief?: Record<string, unknown>
  platforms?: Record<string, PlatformResult>
}

export interface TaskDetail {
  id: string
  status: TaskStatus
  source_data: Record<string, unknown>
  result: TaskResult | null
  error: string | null
  created_at: string | null
  updated_at: string | null
}

export interface OutputFile {
  format: string
  ext: string
  size: number
  filename: string
}

export interface RerenderResponse {
  format: string
  pass: boolean
  quality: {
    score: number
    issues: string[]
    critique: string
  }
  png_b64: string
}

export interface GenerateResponse {
  task_id: string
  status: string
}

export interface SaveTemplateResponse {
  template_id: string
  mode: "new" | "update"
  file: string
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
