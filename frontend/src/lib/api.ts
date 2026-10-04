// Typed API client for Tasbir. API key lives in versioned localStorage and
// is cached in a module-level slot so we never read storage per render.

const API_KEY_STORAGE_KEY = "tasbir:apikey:v1"
// All JSON API routes live under /api so the SPA routes (/, /templates, ...)
// never collide with them. The vite dev proxy forwards /api → :8000.
const API_BASE = "/api"

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
  /** Server-suggested wait (from a `Retry-After` header), in milliseconds. */
  retryAfterMs?: number
  constructor(status: number, message: string, retryAfterMs?: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.retryAfterMs = retryAfterMs
  }
}

function retryAfterOf(res: Response): number | undefined {
  const raw = res.headers.get("retry-after")
  if (!raw) return undefined
  const secs = Number(raw)
  return Number.isFinite(secs) && secs >= 0 ? Math.min(secs, 120) * 1000 : undefined
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
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
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
    throw new ApiError(res.status, detail, retryAfterOf(res))
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const apiFetcher = (path: string): Promise<unknown> => apiRequest(path)

export async function apiForm<T>(path: string, form: FormData): Promise<T> {
  const headers = await authHeaders({})
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", headers, body: form })
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
  return (await res.json()) as T
}

export async function fetchBlob(path: string): Promise<Blob> {
  const headers = await authHeaders({})
  const res = await fetch(`${API_BASE}${path}`, { headers })
  if (res.status === 401) throw new ApiError(401, "Invalid or missing API key")
  if (!res.ok) throw new ApiError(res.status, res.statusText)
  return res.blob()
}

export async function fetchText(path: string): Promise<string> {
  const headers = await authHeaders({})
  const res = await fetch(`${API_BASE}${path}`, { headers })
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
  /** Stored copy JSON (headline/subhead/body/…) for template-built formats. */
  copy?: string
  error?: string | null
  rerendered_at?: string | null
}

export interface TaskResult {
  output_paths?: Record<string, Record<string, string>>
  strategic_brief?: Record<string, unknown>
  post_plan?: Record<string, unknown>
  sequence_check?: Record<string, unknown>
  platforms?: Record<string, PlatformResult>
}

export interface TaskDetail {
  id: string
  status: TaskStatus
  source_data: Record<string, unknown>
  result: TaskResult | null
  edited_html: Record<string, string> | null
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

export interface RetryResponse {
  format: string
  pass: boolean
  score: number
  issues: string[]
  critique: string
  html_path: string
  png_path: string | null
  template_id: string | null
}

export interface RefillRequest {
  slots?: Record<string, string>
  hidden?: string[] | null
  media_position?: string
  template_id?: string
  media?: Record<string, string>
  /** Re-fill under another design system (template is remapped server-side). */
  design_system_id?: string
}

/** Persisted editor metadata the server keeps per (task, format). */
export interface EditorMeta {
  hidden?: string[] | null
  media_position?: string
  media_kind?: string
  revision?: number
}

export interface RefillResponse {
  format: string
  pass: boolean
  quality: {
    score: number
    issues: string[]
    critique: string
  }
  png_b64: string
  template_id: string
  /** Finalized document as persisted — the client never has to refetch it. */
  html?: string
  /** +1 per successful persist per (task, format). */
  revision?: number
  saved_at?: string
  editor?: EditorMeta
  /** True when a designer-LLM post was converted to a template post. */
  converted?: boolean
  /** Effective design system after the refill (override or task default). */
  design_system_id?: string
  /** Template remap applied by a design-system switch, if any. */
  remapped?: { from: string; to: string } | null
}

export interface RefillPreviewResponse {
  html: string
  width: number
  height: number
  template_id: string
  slots: Record<string, string>
  converted: boolean
  design_system_id?: string
  remapped?: { from: string; to: string } | null
}

export interface RequestOpts {
  signal?: AbortSignal
  /** Let the request outlive the page (route change / unload flush). */
  keepalive?: boolean
}

/** Structured slot edit (template-built formats) — no raw HTML involved. */
export function refillFormat(
  taskId: string,
  format: string,
  body: RefillRequest,
  opts: RequestOpts = {}
): Promise<RefillResponse> {
  return apiRequest(`/tasks/${taskId}/formats/${format}/refill`, {
    method: "POST",
    body: JSON.stringify(body),
    signal: opts.signal,
    keepalive: opts.keepalive,
  })
}

/** Fast preview of a refill — no PNG, no hard checks, no writes. */
export function refillPreview(
  taskId: string,
  format: string,
  body: RefillRequest,
  opts: RequestOpts = {}
): Promise<RefillPreviewResponse> {
  return apiRequest(`/tasks/${taskId}/formats/${format}/refill/preview`, {
    method: "POST",
    body: JSON.stringify(body),
    signal: opts.signal,
  })
}

/** Media as reported by the editor-state endpoint (never carries base64). */
export interface EditorMedia {
  kind: "none" | "upload" | "photo" | "illustration"
  [key: string]: unknown
}

export interface EditorState {
  editable: boolean
  convertible: boolean
  reason: string | null
  template_id: string
  family: string
  ground: "white" | "black"
  width: number
  height: number
  slots: Record<string, string>
  hidden: string[] | null
  media_position: string
  media: EditorMedia
  media_kinds: Array<"image" | "illustration">
  revision: number
  design_system_id: string
  style_language: string
}

export function getEditorState(
  taskId: string,
  format: string,
  opts: RequestOpts = {}
): Promise<EditorState> {
  return apiRequest(`/tasks/${taskId}/formats/${format}/editor`, { signal: opts.signal })
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

// ─── Agent chat ────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  html: string | null
  created_at: string | null
}

export interface ChatThread {
  thread_id: string
  format: string
  messages: ChatMessage[]
}

export interface ChatReply {
  reply: string
  html: string | null
  qc: { ok: boolean; issues: string[] } | null
  thread_id: string
}

export function getChat(taskId: string, format: string): Promise<ChatThread> {
  return apiRequest(`/tasks/${taskId}/chat?format=${encodeURIComponent(format)}`)
}

export function sendChat(
  taskId: string,
  format: string,
  message: string,
  html?: string
): Promise<ChatReply> {
  return apiRequest(`/tasks/${taskId}/chat`, {
    method: "POST",
    body: JSON.stringify({ format, message, html }),
  })
}

export function getTaskAudit(taskId: string): Promise<AuditEntry[]> {
  return apiRequest(`/tasks/${taskId}/audit`)
}

export interface AuditEntry {
  id: number
  agent_name: string
  decision: Record<string, unknown>
  critique: string | null
  created_at: string | null
}

// ─── Live pipeline progress ────────────────────────────────────────────────

export interface TaskProgressFormat {
  step?: string
  status: string
}

export interface TaskProgress {
  pct: number
  node: string
  per_format: Record<string, TaskProgressFormat>
  done: number
  total: number
}

export function getTaskProgress(taskId: string): Promise<TaskProgress> {
  return apiRequest(`/tasks/${taskId}/progress`)
}

export function listTasks(limit = 1): Promise<TaskSummary[]> {
  return apiRequest(`/tasks?limit=${limit}`)
}

// ─── Design systems ───────────────────────────────────────────────────────

export interface DesignSystem {
  id: string
  name: string
  description: string
  brand: {
    name?: string
    tagline?: string
    mission?: string
    story?: string
    url?: string
    social?: Record<string, string>
  }
  footer: { left: string; right: string }
  categories: Array<{ name: string; description?: string; ground?: string }>
  overrides: Record<string, string>
  tokens: Record<string, string>
  token_roles: Record<string, string>
  campaigns: Record<string, { label: string; tone: string; ground: string; language: string }>
  design_instruction: Record<string, unknown>
  logo: { mime?: string; data?: string; filename?: string } | null
  has_logo: boolean
  source: string
  is_active: boolean
  template_count?: number
  created_at: string | null
  updated_at: string | null
}

// ─── Templates ─────────────────────────────────────────────────────────────

export interface Template {
  id: string
  name: string
  design_system_id: string
  family: "square" | "portrait" | "story" | "landscape"
  grounds: string[]
  categories: string[]
  hint_tags: string[]
  weight: number
  description: string
  image_slots: Array<{ key: string; role: string; hint: string }>
  has_logo_slot: boolean
  hidden_elements?: string[]
  media_position?: string
  supports_text?: boolean
  has_illustration_slot?: boolean
  /** Content vars the template renders (kicker/headline/…/extra.cta). */
  fields?: string[]
  /** True when the template has an image slot or an illustration. */
  has_media?: boolean
  /** Media the template can host: "image" (upload/photo), "illustration". */
  media_kinds?: Array<"image" | "illustration">
  source: string
  is_active: boolean
  html?: string
  created_at: string | null
  updated_at: string | null
}

export interface TemplateCreate {
  id?: string
  name: string
  design_system_id: string
  family: Template["family"]
  grounds: string[]
  categories?: string[]
  hint_tags?: string[]
  weight?: number
  description?: string
  html: string
}

export interface GoogleFont {
  family: string
  category: string
  variants: string[]
}

export function searchGoogleFonts(q: string): Promise<GoogleFont[]> {
  return apiRequest<{ fonts: GoogleFont[] }>(
    `/fonts/search?q=${encodeURIComponent(q)}`
  ).then((r) => r.fonts)
}

export function listDefaultFonts(): Promise<GoogleFont[]> {
  return apiRequest<{ fonts: GoogleFont[] }>("/fonts/default").then((r) => r.fonts)
}

export interface AgentJob {
  id: string
  kind: "template" | "design_system"
  status: "pending" | "running" | "completed" | "failed"
  result: Record<string, unknown> | null
  error: string | null
  created_at: string | null
  updated_at: string | null
  title: string
}

// ─── Agents (DB-backed agent configs) ──────────────────────────────────────

export interface AgentConfig {
  name: string
  persona: string
  role: string
  system_prompt: string
  model: string
  fallback_models: string[]
  temperature: number
  max_tokens: number
  source: "seed" | "manual"
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

export interface ModelInfo {
  id: string
  name: string
  category: string
  vision: boolean
  rpm: number
  tpm: number
  rpd: number
}

export function listModels(): Promise<{ models: ModelInfo[] }> {
  return apiRequest("/models")
}

export interface AgentGraphNode {
  id: string
  label: string
  kind: "start" | "agent" | "group" | "end" | "pipeline"
  agent?: string
  persona?: string
  model?: string
  is_active?: boolean
}

export interface AgentGraphEdge {
  id: string
  source: string
  target: string
  label?: string
}

export interface AgentGraphAuxAgent {
  name: string
  persona: string
  model: string
  is_active: boolean
}

export interface AgentGraphLane {
  id: string
  label: string
  agents: AgentGraphAuxAgent[]
}

export interface AgentGraphSpec {
  nodes: AgentGraphNode[]
  edges: AgentGraphEdge[]
  aux_lanes: AgentGraphLane[]
}

export function listAgents(includeInactive = false): Promise<AgentConfig[]> {
  return apiRequest(`/agents${includeInactive ? "?include_inactive=true" : ""}`)
}

export function getAgent(name: string): Promise<AgentConfig> {
  return apiRequest(`/agents/${name}`)
}

export function updateAgent(
  name: string,
  // Model routing is code-owned — persona/prompts/knobs only. The GET
  // response still carries model info read-only.
  patch: Partial<Pick<
    AgentConfig,
    "persona" | "role" | "system_prompt" | "temperature" | "max_tokens" | "is_active"
  >>
): Promise<AgentConfig> {
  return apiRequest(`/agents/${name}`, { method: "PUT", body: JSON.stringify(patch) })
}

export function resetAgent(name: string): Promise<AgentConfig> {
  return apiRequest(`/agents/${name}/reset`, { method: "POST" })
}

export interface PromptPreview {
  agent: string
  system_prompt: string
  user_prompt: string
}

export function promptPreview(name: string, designSystemId = "default"): Promise<PromptPreview> {
  return apiRequest(`/agents/${name}/prompt-preview`, {
    method: "POST",
    body: JSON.stringify({ design_system_id: designSystemId }),
  })
}

export function getAgentGraph(): Promise<AgentGraphSpec> {
  return apiRequest("/agents/graph")
}

// ─── Platforms (DB-backed) ─────────────────────────────────────────────────

export interface PlatformInfo {
  id: string
  name: string
  width: number
  height: number
  family: "square" | "portrait" | "story" | "landscape"
  is_active: boolean
  sort_order: number
  created_at?: string | null
  updated_at?: string | null
}

export type PlatformCreate = Omit<PlatformInfo, "created_at" | "updated_at">
export type PlatformUpdate = Partial<Omit<PlatformInfo, "id" | "created_at" | "updated_at">>

export function listPlatforms(includeInactive = false): Promise<PlatformInfo[]> {
  return apiRequest(`/platforms${includeInactive ? "?include_inactive=true" : ""}`)
}

export function createPlatform(body: PlatformCreate): Promise<PlatformInfo> {
  return apiRequest("/platforms", { method: "POST", body: JSON.stringify(body) })
}

export function updatePlatform(id: string, patch: PlatformUpdate): Promise<PlatformInfo> {
  return apiRequest(`/platforms/${id}`, { method: "PUT", body: JSON.stringify(patch) })
}

export function deletePlatform(id: string): Promise<void> {
  return apiRequest(`/platforms/${id}`, { method: "DELETE" })
}

// ─── Curated font pool (DB-backed) ─────────────────────────────────────────

export interface PoolFont {
  family: string
  role: string
  weights: number[]
  style: string
  is_active: boolean
  sort_order: number
  created_at?: string | null
  updated_at?: string | null
}

export type PoolFontCreate = Omit<PoolFont, "created_at" | "updated_at">
export type PoolFontUpdate = Partial<Omit<PoolFont, "family" | "created_at" | "updated_at">>

export function listFontPool(includeInactive = false): Promise<PoolFont[]> {
  return apiRequest(`/fonts/pool${includeInactive ? "?include_inactive=true" : ""}`)
}

export function createPoolFont(body: PoolFontCreate): Promise<PoolFont> {
  return apiRequest("/fonts/pool", { method: "POST", body: JSON.stringify(body) })
}

export function updatePoolFont(family: string, patch: PoolFontUpdate): Promise<PoolFont> {
  return apiRequest(`/fonts/pool/${encodeURIComponent(family)}`, {
    method: "PUT",
    body: JSON.stringify(patch),
  })
}

export function deletePoolFont(family: string): Promise<void> {
  return apiRequest(`/fonts/pool/${encodeURIComponent(family)}`, { method: "DELETE" })
}

// ─── Runtime settings (DB-backed knobs) ────────────────────────────────────

export interface RuntimeSettingsResponse {
  defaults: Record<string, { value: unknown; description: string }>
  values: Record<string, unknown>
}

export function getRuntimeSettings(): Promise<RuntimeSettingsResponse> {
  return apiRequest("/settings")
}

export function updateRuntimeSettings(values: Record<string, unknown>): Promise<RuntimeSettingsResponse> {
  return apiRequest("/settings", { method: "PUT", body: JSON.stringify({ values }) })
}

export function resetRuntimeSettings(): Promise<RuntimeSettingsResponse> {
  return apiRequest("/settings/reset", { method: "POST" })
}

// ─── System export / import (config backup & restore) ─────────────────────

export interface SystemSnapshot {
  schema_version: number
  exported_at?: string
  design_systems: Record<string, unknown>[]
  templates: Record<string, unknown>[]
  platforms: Record<string, unknown>[]
  fonts: Record<string, unknown>[]
  agents: Record<string, unknown>[]
  app_settings: Record<string, unknown>[]
}

export function exportSystem(): Promise<SystemSnapshot> {
  return apiRequest("/system/export")
}

export function importSystem(snapshot: SystemSnapshot): Promise<{ applied: Record<string, number> }> {
  return apiRequest("/system/import", {
    method: "POST",
    body: JSON.stringify({ payload: snapshot }),
  })
}

// ─── Design system API helpers ─────────────────────────────────────────────

export function listDesignSystems(includeInactive = false): Promise<DesignSystem[]> {
  return apiRequest(`/design-systems${includeInactive ? "?include_inactive=true" : ""}`)
}

export function createDesignSystem(name: string, description = ""): Promise<DesignSystem> {
  return apiRequest("/design-systems", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  })
}

export function getDesignSystem(id: string): Promise<DesignSystem> {
  return apiRequest(`/design-systems/${id}`)
}

export function updateDesignSystem(id: string, patch: Partial<DesignSystem>): Promise<DesignSystem> {
  return apiRequest(`/design-systems/${id}`, {
    method: "PUT",
    body: JSON.stringify(patch),
  })
}

export function deleteDesignSystem(id: string): Promise<void> {
  return apiRequest(`/design-systems/${id}`, { method: "DELETE" })
}

export interface StyleLanguage {
  id: string
  label: string
  description: string
  emoji: boolean
  accent: boolean
  grayscale: boolean
  media_policy: string
  accent_tokens: Record<string, string>
  palette_tokens: Record<string, string>
}

export function listStyleLanguages(): Promise<StyleLanguage[]> {
  return apiRequest("/design-systems/styles")
}

export function applyStyleLanguage(
  id: string,
  styleLanguage: string
): Promise<DesignSystem & { seeded_templates: string[] }> {
  return apiRequest(`/design-systems/${id}/style`, {
    method: "POST",
    body: JSON.stringify({ style_language: styleLanguage }),
  })
}

export interface DesignLanguage {
  id: string
  name: string
  description: string
  emoji: boolean
  grayscale: boolean
  accent: boolean
  media_policy: string
  accent_tokens: Record<string, string>
  palette_tokens: Record<string, string>
}

export function listDesignLanguages(): Promise<DesignLanguage[]> {
  return apiRequest("/design-languages")
}

export function createDesignLanguage(
  name: string,
  base: string,
  description = ""
): Promise<DesignLanguage> {
  return apiRequest("/design-languages", {
    method: "POST",
    body: JSON.stringify({ name, base, description }),
  })
}

export function deleteDesignLanguage(id: string): Promise<void> {
  return apiRequest(`/design-languages/${id}`, { method: "DELETE" })
}

export async function uploadLogo(id: string, file: File): Promise<{ has_logo: boolean }> {
  const form = new FormData()
  form.append("file", file)
  return apiForm(`/design-systems/${id}/logo`, form)
}

export function removeLogo(id: string): Promise<void> {
  return apiRequest(`/design-systems/${id}/logo`, { method: "DELETE" })
}

export async function createDesignSystemFromInput(form: {
  name: string
  tagline?: string
  mission?: string
  industry?: string
  audience?: string
  style?: string
  handle?: string
  referenceImage?: File | null
  logoImage?: File | null
}): Promise<{ job_id: string }> {
  const fd = new FormData()
  fd.append("name", form.name)
  if (form.tagline) fd.append("tagline", form.tagline)
  if (form.mission) fd.append("mission", form.mission)
  if (form.industry) fd.append("industry", form.industry)
  if (form.audience) fd.append("audience", form.audience)
  if (form.style) fd.append("style", form.style)
  if (form.handle) fd.append("handle", form.handle)
  if (form.referenceImage) fd.append("reference_image", form.referenceImage)
  if (form.logoImage) fd.append("logo_image", form.logoImage)
  return apiForm(`/design-systems/from-input`, fd)
}

// ─── Template API helpers ──────────────────────────────────────────────────

export function listTemplates(
  designSystemId: string,
  family?: string,
  includeInactive = false
): Promise<Template[]> {
  const params = new URLSearchParams({ design_system_id: designSystemId })
  if (family) params.set("family", family)
  if (includeInactive) params.set("include_inactive", "true")
  return apiRequest(`/templates?${params.toString()}`)
}

export function getTemplate(id: string): Promise<Template> {
  return apiRequest(`/templates/${id}`)
}

export function createTemplate(body: TemplateCreate): Promise<Template> {
  return apiRequest("/templates", { method: "POST", body: JSON.stringify(body) })
}

export function updateTemplate(
  id: string,
  patch: Partial<Template>
): Promise<Template> {
  return apiRequest(`/templates/${id}`, { method: "PUT", body: JSON.stringify(patch) })
}

export function deleteTemplate(id: string): Promise<void> {
  return apiRequest(`/templates/${id}`, { method: "DELETE" })
}

export function previewTemplate(id: string): Promise<{ html: string }> {
  return apiRequest(`/templates/${id}/preview`, { method: "POST" })
}

export function previewDraft(body: {
  html: string
  family: Template["family"]
  design_system_id: string
  ground?: string
  media_position?: string
  hidden?: string[]
}): Promise<{ html: string }> {
  return apiRequest("/templates/preview-draft", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function validateTemplate(id: string): Promise<{ ok: boolean; issues: string[] }> {
  return apiRequest(`/templates/${id}/render`, { method: "POST" })
}

// ─── Agent jobs ────────────────────────────────────────────────────────────

export function getAgentJob(id: string): Promise<AgentJob> {
  return apiRequest(`/agent-jobs/${id}`)
}

export function listAgentJobs(kind?: string): Promise<AgentJob[]> {
  return apiRequest(`/agent-jobs${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`)
}

export function deleteAgentJob(id: string): Promise<void> {
  return apiRequest(`/agent-jobs/${id}`, { method: "DELETE" })
}

// ─── Template build job ────────────────────────────────────────────────────

export interface TemplateBuildSeed {
  designSystemId: string
  message?: string
  html?: string
  family?: string
  ground?: string
  image?: File | null
}

export async function createTemplateBuild(
  seed: TemplateBuildSeed
): Promise<{ job_id: string; status: string }> {
  const fd = new FormData()
  fd.append("design_system_id", seed.designSystemId)
  if (seed.message) fd.append("message", seed.message)
  if (seed.html) fd.append("html", seed.html)
  if (seed.family) fd.append("family", seed.family)
  if (seed.ground) fd.append("ground", seed.ground)
  if (seed.image) fd.append("file", seed.image)
  return apiForm("/templates/from-input", fd)
}

// ─── Uploads (post media) ──────────────────────────────────────────────────

export async function uploadMedia(file: File): Promise<{ data: string; mime: string; size: number }> {
  const form = new FormData()
  form.append("file", file)
  return apiForm("/uploads", form)
}

// ─── Manual compose (no AI) ────────────────────────────────────────────────

export type ComposeGround = "white" | "black"
export type ComposeMediaPosition = "auto" | "left" | "right" | "top" | "bottom"
export type ComposeExtraKey = "price" | "cta" | "date" | "location" | "stat" | "source"

export interface ComposeCopy {
  kicker: string
  headline: string
  subhead: string
  body: string
  tagline: string
  extra: Record<ComposeExtraKey, string>
}

export type ComposeMedia =
  | { kind: "none" }
  | { kind: "upload"; data: string; mime: string; alt: string }
  | {
      kind: "photo"
      url: string
      credit: string
      provider: string
      photographer: string
      license: string
    }
  | { kind: "illustration"; style: string; seed: string }

export interface ComposeSlideSpec {
  template_id: string
  copy: ComposeCopy
  /** Element toggles; null = the template's default hidden elements. */
  hidden: string[] | null
  media_position: ComposeMediaPosition
  media: ComposeMedia
}

export interface ComposePostSpec {
  platform: string
  slides: ComposeSlideSpec[]
}

export interface ComposeBatchRequest {
  design_system_id: string
  style_language: string
  ground: ComposeGround
  title?: string
  posts: ComposePostSpec[]
}

/** Per-task stored composition (also the PUT /tasks/{id}/composition body). */
export interface ComposeComposition {
  design_system_id: string
  style_language: string
  ground: ComposeGround
  post: ComposePostSpec
}

export interface ComposePreviewRequest {
  design_system_id: string
  style_language: string
  ground: ComposeGround
  platform: string
  slide_index: number
  slide_total: number
  slide: ComposeSlideSpec
}

export interface ComposePreviewResponse {
  html: string
  width: number
  height: number
}

export interface ComposeCreateResponse {
  batch_id: string
  task_ids: string[]
}

export interface ComposeBatchTask {
  task_id: string
  status: string
  platform: string
  composition: ComposeComposition | null
}

export interface ComposeBatch {
  batch_id: string
  tasks: ComposeBatchTask[]
}

export interface ComposePhoto {
  url: string
  thumb: string
  width: number
  height: number
  provider: string
  photographer: string
  credit: string
  license: string
}

export function composePreview(
  body: ComposePreviewRequest,
  signal?: AbortSignal
): Promise<ComposePreviewResponse> {
  return apiRequest("/compose/preview", { method: "POST", body: JSON.stringify(body), signal })
}

export function createComposeBatch(body: ComposeBatchRequest): Promise<ComposeCreateResponse> {
  return apiRequest("/compose", { method: "POST", body: JSON.stringify(body) })
}

export function getComposeBatch(batchId: string): Promise<ComposeBatch> {
  return apiRequest(`/compose/batches/${encodeURIComponent(batchId)}`)
}

export function updateTaskComposition(
  taskId: string,
  body: ComposeComposition
): Promise<{ task_id: string; status: string }> {
  return apiRequest(`/tasks/${taskId}/composition`, { method: "PUT", body: JSON.stringify(body) })
}

export function getComposeIllustration(
  style: string,
  seed: string,
  ground: ComposeGround = "white"
): Promise<{ svg: string }> {
  const params = new URLSearchParams({ style, seed, ground })
  return apiRequest(`/compose/illustration?${params.toString()}`)
}

export function searchComposePhotos(
  q: string,
  orientation: "square" | "portrait" | "landscape" = "square"
): Promise<{ results: ComposePhoto[] }> {
  const params = new URLSearchParams({ q, orientation })
  return apiRequest(`/compose/photos?${params.toString()}`)
}

export function mapComposeTemplates(body: {
  from_design_system_id: string
  to_design_system_id: string
  template_ids: string[]
  platform: string
}): Promise<{ mapping: Record<string, string> }> {
  return apiRequest("/compose/templates/map", { method: "POST", body: JSON.stringify(body) })
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
