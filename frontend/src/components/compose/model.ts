// Manual-compose editor model: editor-side state shapes (API specs + stable
// client uids), pure state transforms, field metadata and serialization.
// Everything here is framework-free so the page, the rail and the inspector
// share one set of rules (slide-count limits, caps, defaults).

import type {
  ComposeBatchRequest,
  ComposeComposition,
  ComposeCopy,
  ComposeExtraKey,
  ComposeGround,
  ComposeMedia,
  ComposePostSpec,
  ComposePreviewRequest,
  ComposeSlideSpec,
  PlatformInfo,
  Template,
} from "@/lib/api"
import { familyOfPlatform } from "@/lib/platforms"

export const MAX_POSTS = 20
export const MIN_CAROUSEL_SLIDES = 2
export const MAX_CAROUSEL_SLIDES = 10

export interface EditorSlide extends ComposeSlideSpec {
  uid: string
}

export interface EditorPost {
  uid: string
  platform: string
  slides: EditorSlide[]
  /** Set in edit mode — the GenerationTask this post belongs to. */
  task_id?: string
}

export interface EditorState {
  design_system_id: string
  style_language: string
  ground: ComposeGround
  title: string
  posts: EditorPost[]
}

export interface Selection {
  postUid: string
  slideUid: string
}

// ─── Platforms ─────────────────────────────────────────────────────────────

export function isCarouselPlatform(p: string): boolean {
  return p === "instagram-carousel" || p === "instagram-carousel-portrait"
}

/** Clearer labels for the carousel platforms (aspect encoded in the id). */
export function platformLabel(p: { id: string; name?: string }): string {
  if (p.id === "instagram-carousel") return "Instagram carousel 1:1"
  if (p.id === "instagram-carousel-portrait") return "Instagram carousel 4:5"
  return p.name || p.id
}

/** Template family of a platform — the DB row wins over the dims heuristic. */
export function platformFamily(platform: string, rows: PlatformInfo[]): string {
  return rows.find((r) => r.id === platform)?.family ?? familyOfPlatform(platform)
}

export function slideLimits(platform: string): { min: number; max: number } {
  return isCarouselPlatform(platform)
    ? { min: MIN_CAROUSEL_SLIDES, max: MAX_CAROUSEL_SLIDES }
    : { min: 1, max: 1 }
}

// ─── Text fields ───────────────────────────────────────────────────────────

export type FieldKey =
  | "kicker"
  | "headline"
  | "subhead"
  | "body"
  | "tagline"
  | `extra.${ComposeExtraKey}`

export const EXTRA_KEYS: ComposeExtraKey[] = ["price", "cta", "date", "location", "stat", "source"]

export const ALL_FIELDS: FieldKey[] = [
  "kicker",
  "headline",
  "subhead",
  "body",
  "tagline",
  ...EXTRA_KEYS.map((k) => `extra.${k}` as FieldKey),
]

/** Shown when a template list item carries no `fields` (older backend). */
export const FALLBACK_FIELDS: FieldKey[] = ["headline", "subhead", "body"]

export const FIELD_META: Record<FieldKey, { label: string; cap: number; multiline: boolean }> = {
  kicker: { label: "Kicker", cap: 120, multiline: false },
  headline: { label: "Headline", cap: 300, multiline: true },
  subhead: { label: "Subhead", cap: 500, multiline: true },
  body: { label: "Body", cap: 3000, multiline: true },
  tagline: { label: "Tagline", cap: 120, multiline: false },
  "extra.price": { label: "Price", cap: 200, multiline: false },
  "extra.cta": { label: "Call to action", cap: 200, multiline: false },
  "extra.date": { label: "Date", cap: 200, multiline: false },
  "extra.location": { label: "Location", cap: 200, multiline: false },
  "extra.stat": { label: "Stat", cap: 200, multiline: false },
  "extra.source": { label: "Source", cap: 200, multiline: false },
}

export function isFieldKey(k: string): k is FieldKey {
  return (ALL_FIELDS as string[]).includes(k)
}

/** Input fields a template renders, in a stable order. */
export function templateFields(t: Template | undefined): FieldKey[] {
  if (!t?.fields || t.fields.length === 0) return FALLBACK_FIELDS
  const known = t.fields.filter(isFieldKey)
  return ALL_FIELDS.filter((f) => known.includes(f))
}

export function getField(copy: ComposeCopy, key: FieldKey): string {
  if (key.startsWith("extra.")) return copy.extra[key.slice(6) as ComposeExtraKey] ?? ""
  return copy[key as Exclude<FieldKey, `extra.${string}`>] ?? ""
}

export function setField(copy: ComposeCopy, key: FieldKey, value: string): ComposeCopy {
  if (key.startsWith("extra.")) {
    return { ...copy, extra: { ...copy.extra, [key.slice(6)]: value } }
  }
  return { ...copy, [key]: value }
}

export function copyIsEmpty(copy: ComposeCopy): boolean {
  return ALL_FIELDS.every((f) => !getField(copy, f).trim())
}

/** Whether a template takes media (image slot or illustration). */
export function templateHasMedia(t: Template | undefined): boolean {
  if (!t) return false
  if (typeof t.has_media === "boolean") return t.has_media
  return (t.image_slots?.length ?? 0) > 0 || Boolean(t.has_illustration_slot)
}

/** Media the template can host; older API rows fall back to slot scanning. */
export function templateMediaKinds(t: Template | undefined): Array<"image" | "illustration"> {
  if (!t) return []
  if (t.media_kinds) return t.media_kinds
  const kinds: Array<"image" | "illustration"> = []
  if ((t.image_slots?.length ?? 0) > 0) kinds.push("image")
  if (t.has_illustration_slot) kinds.push("illustration")
  return kinds
}

// ─── Illustration styles ───────────────────────────────────────────────────

// Mirrors the backend ILLUSTRATE_TOOL style enum (procedural + curated DiceBear
// styles in app/services/tools/peep_styles.py).
export const ILLUSTRATION_STYLES: Array<{ id: string; label: string }> = [
  { id: "procedural", label: "Procedural (abstract)" },
  { id: "open-peeps", label: "Open Peeps" },
  { id: "lorelei", label: "Lorelei" },
  { id: "notionists", label: "Notionists" },
  { id: "bottts", label: "Bottts (robot)" },
  { id: "blobs", label: "Blobs" },
  { id: "initials", label: "Initials" },
  { id: "shapes", label: "Shapes" },
  { id: "waves", label: "Waves" },
  { id: "landscape", label: "Landscape" },
]

// ─── Factories ─────────────────────────────────────────────────────────────

export function uid(): string {
  try {
    return crypto.randomUUID()
  } catch {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
  }
}

export function randomSeed(): string {
  return Math.random().toString(36).slice(2, 10)
}

export function emptyCopy(): ComposeCopy {
  return {
    kicker: "",
    headline: "",
    subhead: "",
    body: "",
    tagline: "",
    extra: { price: "", cta: "", date: "", location: "", stat: "", source: "" },
  }
}

export function newSlide(templateId: string, copy?: Partial<ComposeCopy>): EditorSlide {
  return {
    uid: uid(),
    template_id: templateId,
    copy: { ...emptyCopy(), ...copy },
    hidden: null,
    media_position: "auto",
    media: { kind: "none" },
  }
}

export function newPost(platform: string, slideCount: number, templateId: string): EditorPost {
  const { min, max } = slideLimits(platform)
  const n = Math.min(max, Math.max(min, slideCount))
  return {
    uid: uid(),
    platform,
    slides: Array.from({ length: n }, () => newSlide(templateId)),
  }
}

export function cloneSlide(s: EditorSlide): EditorSlide {
  return {
    ...s,
    uid: uid(),
    copy: { ...s.copy, extra: { ...s.copy.extra } },
    hidden: s.hidden ? [...s.hidden] : null,
    media: { ...s.media },
  }
}

export function clonePost(p: EditorPost): EditorPost {
  return { uid: uid(), platform: p.platform, slides: p.slides.map(cloneSlide) }
}

/** Best default template for a platform family: ground-compatible, heaviest. */
export function defaultTemplateFor(
  family: string,
  templates: Template[] | undefined,
  ground: ComposeGround
): string {
  const fam = (templates ?? [])
    .filter((t) => t.family === family && t.is_active !== false)
    .sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0))
  const onGround = fam.find((t) => !t.grounds?.length || t.grounds.includes(ground))
  return (onGround ?? fam[0])?.id ?? ""
}

// ─── Pure transforms ───────────────────────────────────────────────────────

export function move<T>(list: T[], from: number, to: number): T[] {
  if (to < 0 || to >= list.length || from === to) return list
  const next = [...list]
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

export function mapPost(
  state: EditorState,
  postUid: string,
  fn: (p: EditorPost) => EditorPost
): EditorState {
  return { ...state, posts: state.posts.map((p) => (p.uid === postUid ? fn(p) : p)) }
}

export function mapSlide(
  state: EditorState,
  postUid: string,
  slideUid: string,
  fn: (s: EditorSlide) => EditorSlide
): EditorState {
  return mapPost(state, postUid, (p) => ({
    ...p,
    slides: p.slides.map((s) => (s.uid === slideUid ? fn(s) : s)),
  }))
}

export function mapAllSlides(
  state: EditorState,
  fn: (s: EditorSlide, p: EditorPost) => EditorSlide
): EditorState {
  return {
    ...state,
    posts: state.posts.map((p) => ({ ...p, slides: p.slides.map((s) => fn(s, p)) })),
  }
}

// ─── Serialization ─────────────────────────────────────────────────────────

export function slideSpec(s: EditorSlide): ComposeSlideSpec {
  return {
    template_id: s.template_id,
    copy: s.copy,
    hidden: s.hidden,
    media_position: s.media_position,
    media: s.media,
  }
}

export function postSpec(p: EditorPost): ComposePostSpec {
  return { platform: p.platform, slides: p.slides.map(slideSpec) }
}

export function batchRequest(state: EditorState): ComposeBatchRequest {
  return {
    design_system_id: state.design_system_id,
    style_language: state.style_language,
    ground: state.ground,
    title: state.title.trim() || undefined,
    posts: state.posts.map(postSpec),
  }
}

export function compositionOf(state: EditorState, p: EditorPost): ComposeComposition {
  return {
    design_system_id: state.design_system_id,
    style_language: state.style_language,
    ground: state.ground,
    post: postSpec(p),
  }
}

export function previewRequest(
  state: EditorState,
  post: EditorPost,
  slideIdx: number
): ComposePreviewRequest {
  return {
    design_system_id: state.design_system_id,
    style_language: state.style_language,
    ground: state.ground,
    platform: post.platform,
    slide_index: slideIdx + 1,
    slide_total: post.slides.length,
    slide: previewSlideSpec(post.slides[slideIdx]),
  }
}

/**
 * Slide spec for the live preview. Picking "Upload" / "Stock photo" before a
 * file or photo is chosen leaves the media spec incomplete (the API rejects an
 * empty upload / photo url with a 422), so preview it as "no media yet".
 * Create still sends the real spec — validateState blocks incomplete media.
 */
function previewSlideSpec(s: EditorSlide): ComposeSlideSpec {
  const spec = slideSpec(s)
  const m = spec.media
  const incomplete = (m.kind === "upload" && !m.data) || (m.kind === "photo" && !m.url)
  return incomplete ? { ...spec, media: { kind: "none" } } : spec
}

/**
 * Compact cache key for a spec. Upload payloads can be megabytes of base64,
 * so they are fingerprinted (length + head + tail) instead of embedded.
 */
export function specKey(value: unknown): string {
  return JSON.stringify(value, (k, v: unknown) =>
    k === "data" && typeof v === "string" && v.length > 96
      ? `${v.length}:${v.slice(0, 32)}:${v.slice(-32)}`
      : v
  )
}

function normalizeCopy(raw: Partial<ComposeCopy> | undefined): ComposeCopy {
  const base = emptyCopy()
  return {
    kicker: raw?.kicker ?? "",
    headline: raw?.headline ?? "",
    subhead: raw?.subhead ?? "",
    body: raw?.body ?? "",
    tagline: raw?.tagline ?? "",
    extra: { ...base.extra, ...(raw?.extra ?? {}) },
  }
}

function normalizeMedia(raw: ComposeMedia | undefined): ComposeMedia {
  if (!raw || !raw.kind) return { kind: "none" }
  switch (raw.kind) {
    case "upload":
      return { kind: "upload", data: raw.data ?? "", mime: raw.mime ?? "image/png", alt: raw.alt ?? "" }
    case "photo":
      return {
        kind: "photo",
        url: raw.url ?? "",
        credit: raw.credit ?? "",
        provider: raw.provider ?? "",
        photographer: raw.photographer ?? "",
        license: raw.license ?? "",
      }
    case "illustration":
      return { kind: "illustration", style: raw.style || "procedural", seed: raw.seed || randomSeed() }
    default:
      return { kind: "none" }
  }
}

/** API post spec (server composition) → editor post with fresh uids. */
export function editorPostFromSpec(spec: ComposePostSpec, taskId?: string): EditorPost {
  return {
    uid: uid(),
    platform: spec.platform,
    task_id: taskId,
    slides: (spec.slides ?? []).map((s) => ({
      uid: uid(),
      template_id: s.template_id ?? "",
      copy: normalizeCopy(s.copy),
      hidden: Array.isArray(s.hidden) ? s.hidden : null,
      media_position: s.media_position ?? "auto",
      media: normalizeMedia(s.media),
    })),
  }
}

/** Human-readable problems that would make POST /compose 422. */
export function validateState(state: EditorState): string[] {
  const problems: string[] = []
  if (!state.design_system_id) problems.push("Pick a design system.")
  if (state.posts.length === 0) problems.push("Add at least one post.")
  if (state.posts.length > MAX_POSTS) problems.push(`At most ${MAX_POSTS} posts per batch.`)
  state.posts.forEach((p, pi) => {
    const { min, max } = slideLimits(p.platform)
    if (p.slides.length < min || p.slides.length > max) {
      problems.push(
        min === max
          ? `Post ${pi + 1}: needs exactly ${min} slide.`
          : `Post ${pi + 1}: needs ${min}–${max} slides.`
      )
    }
    p.slides.forEach((s, si) => {
      const where = p.slides.length > 1 ? `Post ${pi + 1}, slide ${si + 1}` : `Post ${pi + 1}`
      if (!s.template_id) problems.push(`${where}: choose a template.`)
      for (const f of ALL_FIELDS) {
        if (getField(s.copy, f).length > FIELD_META[f].cap) {
          problems.push(`${where}: ${FIELD_META[f].label} exceeds ${FIELD_META[f].cap} characters.`)
        }
      }
      if (s.media.kind === "upload" && !s.media.data) problems.push(`${where}: upload is empty.`)
      if (s.media.kind === "photo" && !s.media.url) problems.push(`${where}: pick a photo.`)
    })
  })
  return problems
}

/** Split pasted text into items — by blank lines (paragraphs) or single lines. */
export function splitPasted(text: string, mode: "paragraphs" | "lines"): string[] {
  const parts = mode === "lines" ? text.split(/\r?\n/) : text.split(/\r?\n\s*\r?\n/)
  return parts.map((p) => p.trim()).filter(Boolean)
}
