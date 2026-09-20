import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import {
  ArrowLeft,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Copy,
  Loader2,
  Plus,
  Save,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { AddPostsDialog } from "@/components/compose/add-posts-dialog"
import { BatchResults } from "@/components/compose/batch-results"
import { BatchSetup } from "@/components/compose/batch-setup"
import { LivePreview } from "@/components/compose/live-preview"
import { ModeSwitch } from "@/components/compose/mode-switch"
import { PostList, type AddMode } from "@/components/compose/post-list"
import { SlideInspector } from "@/components/compose/slide-inspector"
import {
  MAX_POSTS,
  batchRequest,
  clonePost,
  cloneSlide,
  compositionOf,
  copyIsEmpty,
  defaultTemplateFor,
  editorPostFromSpec,
  mapAllSlides,
  mapPost,
  mapSlide,
  move,
  newPost,
  newSlide,
  platformFamily,
  previewRequest,
  slideLimits,
  specKey,
  templateHasMedia,
  validateState,
  type EditorPost,
  type EditorSlide,
  type EditorState,
  type Selection,
} from "@/components/compose/model"
import { useDesignSystems, useTemplates } from "@/hooks/use-library"
import { usePlatforms } from "@/hooks/use-platforms"
import {
  clearDraft,
  draftStorageKey,
  readDraft,
  useBeforeUnload,
  useComposeBatch,
  useDraftAutosave,
} from "@/hooks/use-compose"
import {
  ApiError,
  createComposeBatch,
  listStyleLanguages,
  mapComposeTemplates,
  updateTaskComposition,
  type ComposeGround,
  type StyleLanguage,
  type Template,
} from "@/lib/api"
import { formatDims } from "@/lib/platforms"

const DEFAULT_PLATFORM = "instagram-square"

function orientationOf(platform: string): "square" | "portrait" | "landscape" {
  const d = formatDims(platform)
  return d.height > d.width ? "portrait" : d.width > d.height ? "landscape" : "square"
}

/** Drop upload payloads so an oversized draft still fits in localStorage. */
function stripUploads(s: EditorState | null): EditorState | null {
  if (!s) return s
  return mapAllSlides(s, (slide) =>
    slide.media.kind === "upload" ? { ...slide, media: { ...slide.media, data: "" } } : slide
  )
}

function isEditorState(v: unknown): v is EditorState {
  const s = v as EditorState | null
  return Boolean(s && typeof s.design_system_id === "string" && Array.isArray(s.posts))
}

/** Route wrapper — remount the editor when switching between batches. */
export default function ComposeRoute() {
  const { batchId } = useParams<{ batchId: string }>()
  return <ComposePage key={batchId ?? "new"} batchId={batchId} />
}

function ComposePage({ batchId }: { batchId?: string }) {
  const editMode = Boolean(batchId)
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const focusTask = params.get("task")
  const draftKey = draftStorageKey(batchId)

  const { data: systems } = useDesignSystems()
  const { platforms } = usePlatforms()
  const [styles, setStyles] = useState<StyleLanguage[]>([])
  const { data: batch, error: batchError, mutate: mutateBatch } = useComposeBatch(batchId ?? null)

  const [state, setState] = useState<EditorState | null>(null)
  const [sel, setSel] = useState<Selection | null>(null)
  // Edit mode: task_id → spec key of what the server has (dirty tracking).
  const [baseline, setBaseline] = useState<Record<string, string>>({})
  const [pendingDraft, setPendingDraft] = useState<EditorState | null>(null)
  const [view, setView] = useState<"edit" | "results">(editMode && !focusTask ? "results" : "edit")
  const [addMode, setAddMode] = useState<AddMode | null>(null)
  const [remapping, setRemapping] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const stateRef = useRef(state)
  stateRef.current = state

  useEffect(() => {
    listStyleLanguages()
      .then(setStyles)
      .catch(() => setStyles([]))
  }, [])

  const activeSystems = useMemo(() => (systems ?? []).filter((s) => s.is_active), [systems])

  // ── Initialize: new → draft or blank; edit → server batch (+ draft offer).
  useEffect(() => {
    if (state || editMode || activeSystems.length === 0) return
    const draft = readDraft<EditorState>(draftKey)
    if (isEditorState(draft) && draft.posts.length > 0) {
      setState(draft)
      toast.message("Restored your unsaved composition", {
        action: {
          label: "Start over",
          onClick: () => {
            clearDraft(draftKey)
            setState(blankState(activeSystems[0].id))
          },
        },
      })
      return
    }
    const preferred = activeSystems.find((s) => s.id === "default") ?? activeSystems[0]
    setState(blankState(preferred.id))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSystems, editMode])

  useEffect(() => {
    if (state || !editMode || !batch) return
    const withComp = batch.tasks.filter((t) => t.composition)
    if (withComp.length === 0) return
    const first = withComp[0].composition!
    const posts = withComp.map((t) => editorPostFromSpec(t.composition!.post, t.task_id))
    const loaded: EditorState = {
      design_system_id: first.design_system_id,
      style_language: first.style_language ?? "",
      ground: first.ground ?? "white",
      title: "",
      posts,
    }
    const base: Record<string, string> = {}
    for (const p of posts) base[p.task_id!] = specKey(compositionOf(loaded, p))
    setBaseline(base)
    setState(loaded)
    const target = posts.find((p) => p.task_id === focusTask) ?? posts[0]
    setSel({ postUid: target.uid, slideUid: target.slides[0].uid })
    const draft = readDraft<EditorState>(draftKey)
    if (isEditorState(draft) && draft.posts.some((p) => p.task_id)) setPendingDraft(draft)
  }, [batch, editMode, state, focusTask, draftKey])

  const { data: templates, isLoading: templatesLoading } = useTemplates(state?.design_system_id || null)
  const templatesById = useMemo(() => {
    const m = new Map<string, Template>()
    for (const t of templates ?? []) m.set(t.id, t)
    return m
  }, [templates])

  const familyOf = useCallback((platform: string) => platformFamily(platform, platforms), [platforms])

  // Fill slides that have no template yet with the family default.
  useEffect(() => {
    if (!state || !templates) return
    let changed = false
    const next = mapAllSlides(state, (slide, post) => {
      if (slide.template_id) return slide
      const tid = defaultTemplateFor(familyOf(post.platform), templates, state.ground)
      if (!tid) return slide
      changed = true
      return { ...slide, template_id: tid }
    })
    if (changed) setState(next)
  }, [state, templates, familyOf])

  // Keep the selection valid (deleted post/slide → nearest survivor).
  const selected = useMemo(() => {
    if (!state || state.posts.length === 0) return null
    const post = state.posts.find((p) => p.uid === sel?.postUid) ?? state.posts[0]
    const idx = Math.max(0, post.slides.findIndex((s) => s.uid === sel?.slideUid))
    return { post, slideIdx: idx, slide: post.slides[idx] }
  }, [state, sel])

  // ── Dirty tracking, unload guard, draft autosave ────────────────────────
  const modifiedPosts = useMemo(() => {
    const out = new Set<string>()
    if (!state || !editMode) return out
    for (const p of state.posts) {
      if (p.task_id && baseline[p.task_id] !== specKey(compositionOf(state, p))) out.add(p.uid)
    }
    return out
  }, [state, baseline, editMode])

  const hasContent = useMemo(
    () =>
      Boolean(
        state?.posts.some((p) => p.slides.some((s) => !copyIsEmpty(s.copy) || s.media.kind !== "none"))
      ),
    [state]
  )
  const dirty = editMode ? modifiedPosts.size > 0 : hasContent
  useBeforeUnload(dirty && !submitting)
  useDraftAutosave(draftKey, state, Boolean(state) && dirty && !submitting, stripUploads)
  // Back to a clean state (reverted, or everything saved) → drop the draft.
  useEffect(() => {
    if (state && !dirty && !pendingDraft) clearDraft(draftKey)
  }, [state, dirty, draftKey, pendingDraft])

  // ── Mutations ───────────────────────────────────────────────────────────
  const update = useCallback((fn: (s: EditorState) => EditorState) => {
    setState((s) => (s ? fn(s) : s))
  }, [])

  const withUndo = useCallback((message: string, fn: (s: EditorState) => EditorState) => {
    const prev = stateRef.current
    if (!prev) return
    setState(fn(prev))
    toast(message, { action: { label: "Undo", onClick: () => setState(prev) } })
  }, [])

  function templateFor(platform: string): string {
    if (!state) return ""
    const fam = familyOf(platform)
    const cur = selected ? templatesById.get(selected.slide.template_id) : undefined
    if (cur && cur.family === fam) return cur.id
    return defaultTemplateFor(fam, templates, state.ground)
  }

  function addPosts(posts: EditorPost[]) {
    if (!state || posts.length === 0) return
    // A lone untouched starter post is replaced by the first preset.
    const base = isPristine(state) ? [] : state.posts
    const room = MAX_POSTS - base.length
    const accepted = posts.slice(0, room)
    if (accepted.length < posts.length) toast.warning(`Only ${room} more post(s) fit — max ${MAX_POSTS} per batch.`)
    setState({ ...state, posts: [...base, ...accepted] })
    if (accepted[0]) setSel({ postUid: accepted[0].uid, slideUid: accepted[0].slides[0].uid })
  }

  async function changeDesignSystem(newId: string) {
    const cur = stateRef.current
    if (!cur || newId === cur.design_system_id) return
    const byPlatform = new Map<string, Set<string>>()
    for (const p of cur.posts) {
      for (const s of p.slides) {
        if (!s.template_id) continue
        if (!byPlatform.has(p.platform)) byPlatform.set(p.platform, new Set())
        byPlatform.get(p.platform)!.add(s.template_id)
      }
    }
    if (byPlatform.size === 0) {
      update((s) => ({ ...s, design_system_id: newId }))
      return
    }
    setRemapping(true)
    try {
      const entries = await Promise.all(
        [...byPlatform].map(async ([platform, ids]) => {
          const res = await mapComposeTemplates({
            from_design_system_id: cur.design_system_id,
            to_design_system_id: newId,
            template_ids: [...ids],
            platform,
          })
          return [platform, res.mapping ?? {}] as const
        })
      )
      const maps = new Map(entries)
      const changes = new Set<string>()
      for (const [, mapping] of maps) {
        for (const [from, to] of Object.entries(mapping)) if (from !== to) changes.add(`${from} → ${to || "default"}`)
      }
      update((s) =>
        mapAllSlides({ ...s, design_system_id: newId }, (slide, post) => {
          const map = maps.get(post.platform)
          // The target system has no template of this family → clear it so the
          // family-default backfill picks one (a stale id would 422 on create).
          if (!map || !(slide.template_id in map)) return { ...slide, template_id: "", hidden: null }
          const to = map[slide.template_id]
          if (to === slide.template_id) return slide
          // A different template has different elements — reset the toggles.
          return { ...slide, template_id: to, hidden: null }
        })
      )
      const name = activeSystems.find((d) => d.id === newId)?.name ?? newId
      if (changes.size === 0) {
        toast.success(`Switched to ${name} — all templates kept`)
      } else {
        const list = [...changes]
        toast.success(`Switched to ${name} — remapped ${list.length} template(s)`, {
          description: list.slice(0, 4).join(", ") + (list.length > 4 ? ", …" : ""),
        })
      }
    } catch (err) {
      toast.error(
        `Couldn't remap templates — kept the current design system. ${err instanceof Error ? err.message : ""}`
      )
    } finally {
      setRemapping(false)
    }
  }

  function patchSlide(patch: Partial<EditorSlide>) {
    if (!selected) return
    update((s) => mapSlide(s, selected.post.uid, selected.slide.uid, (sl) => ({ ...sl, ...patch })))
  }

  function applyTemplate(scope: "post" | "all") {
    if (!selected || !state) return
    const src = selected.slide
    const fam = familyOf(selected.post.platform)
    let applied = 0
    let skipped = 0
    const next = mapAllSlides(state, (slide, post) => {
      if (scope === "post" && post.uid !== selected.post.uid) return slide
      if (familyOf(post.platform) !== fam) {
        skipped++
        return slide
      }
      if (slide.uid !== src.uid) applied++
      return { ...slide, template_id: src.template_id, hidden: src.hidden ? [...src.hidden] : null, media_position: src.media_position }
    })
    setState(next)
    toast.success(
      `Template applied to ${applied} other slide(s)` +
        (skipped ? ` · ${skipped} skipped (different platform family)` : "")
    )
  }

  function applyMedia(scope: "post" | "all") {
    if (!selected || !state) return
    const media = selected.slide.media
    let applied = 0
    let skipped = 0
    const next = mapAllSlides(state, (slide, post) => {
      if (scope === "post" && post.uid !== selected.post.uid) return slide
      if (slide.uid === selected.slide.uid) return slide
      if (!templateHasMedia(templatesById.get(slide.template_id))) {
        skipped++
        return slide
      }
      applied++
      return { ...slide, media: { ...media } }
    })
    setState(next)
    toast.success(
      `Media applied to ${applied} slide(s)` + (skipped ? ` · ${skipped} skipped (no media slot)` : "")
    )
  }

  // Slide-level actions on the selected post.
  function addSlide(postUid: string) {
    const post = state?.posts.find((p) => p.uid === postUid)
    if (!post) return
    const { max } = slideLimits(post.platform)
    if (post.slides.length >= max) return
    const last = post.slides[post.slides.length - 1]
    const slide = newSlide(last?.template_id ?? "")
    update((s) => mapPost(s, postUid, (p) => ({ ...p, slides: [...p.slides, slide] })))
    setSel({ postUid, slideUid: slide.uid })
  }

  function duplicateSlide() {
    if (!selected) return
    const { post, slideIdx } = selected
    if (post.slides.length >= slideLimits(post.platform).max) return
    const copy = cloneSlide(post.slides[slideIdx])
    update((s) =>
      mapPost(s, post.uid, (p) => {
        const slides = [...p.slides]
        slides.splice(slideIdx + 1, 0, copy)
        return { ...p, slides }
      })
    )
    setSel({ postUid: post.uid, slideUid: copy.uid })
  }

  function deleteSlide() {
    if (!selected) return
    const { post, slide } = selected
    if (post.slides.length <= slideLimits(post.platform).min) return
    withUndo("Slide deleted", (s) =>
      mapPost(s, post.uid, (p) => ({ ...p, slides: p.slides.filter((x) => x.uid !== slide.uid) }))
    )
  }

  function moveSlide(dir: -1 | 1) {
    if (!selected) return
    const { post, slideIdx } = selected
    update((s) => mapPost(s, post.uid, (p) => ({ ...p, slides: move(p.slides, slideIdx, slideIdx + dir) })))
  }

  // ── Submit ──────────────────────────────────────────────────────────────
  function reportProblems(problems: string[]): boolean {
    if (problems.length === 0) return false
    toast.error(problems[0], {
      description:
        problems.length > 1
          ? problems.slice(1, 4).join(" ") + (problems.length > 4 ? ` (+${problems.length - 4} more)` : "")
          : undefined,
    })
    return true
  }

  async function create() {
    if (!state || reportProblems(validateState(state))) return
    setSubmitting(true)
    try {
      const res = await createComposeBatch(batchRequest(state))
      clearDraft(draftKey)
      toast.success(`Queued ${res.task_ids.length} post(s)`)
      if (res.task_ids.length === 1) navigate(`/tasks/${res.task_ids[0]}`)
      else navigate(`/compose/${res.batch_id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create the batch")
      setSubmitting(false)
    }
  }

  async function save() {
    if (!state || reportProblems(validateState(state))) return
    const targets = state.posts.filter((p) => p.task_id && modifiedPosts.has(p.uid))
    if (targets.length === 0) {
      toast.message("Nothing to save")
      return
    }
    setSubmitting(true)
    const results = await Promise.allSettled(
      targets.map((p) => updateTaskComposition(p.task_id!, compositionOf(state, p)))
    )
    const saved: Record<string, string> = {}
    let failures = 0
    results.forEach((r, i) => {
      const p = targets[i]
      if (r.status === "fulfilled") {
        saved[p.task_id!] = specKey(compositionOf(state, p))
      } else {
        failures++
        const err = r.reason
        const msg =
          err instanceof ApiError && err.status === 409
            ? "still rendering — try again when it finishes"
            : err instanceof Error
              ? err.message
              : "save failed"
        const idx = state.posts.indexOf(p) + 1
        toast.error(`Post ${idx}: ${msg}`)
      }
    })
    setBaseline((b) => ({ ...b, ...saved }))
    setSubmitting(false)
    void mutateBatch()
    if (failures === 0) {
      clearDraft(draftKey)
      toast.success(`Saved ${targets.length} post(s) — re-rendering`)
      setView("results")
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────
  if (systems && activeSystems.length === 0) {
    return (
      <div className="grid gap-4">
        <h1 className="text-xl font-semibold">Compose</h1>
        <div className="rounded-md border p-6 text-sm">
          <p className="font-medium">No design systems yet.</p>
          <p className="text-muted-foreground">
            Create one in{" "}
            <Link to="/design-systems" className="underline">
              Design Systems
            </Link>{" "}
            first.
          </p>
        </div>
      </div>
    )
  }

  const header = (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        <Button asChild variant="ghost" size="icon" aria-label="Back">
          <Link to="/">
            <ArrowLeft aria-hidden="true" className="size-4" />
          </Link>
        </Button>
        <div className="grid gap-1">
          <h1 className="text-xl font-semibold">{editMode ? "Composition" : "Compose"}</h1>
          <p className="text-sm text-muted-foreground">
            {editMode
              ? `Batch ${batchId}`
              : "Pick templates, write the text, choose media — no AI involved."}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {editMode ? (
          <div role="tablist" aria-label="Batch view" className="flex overflow-hidden rounded-md border">
            {(["results", "edit"] as const).map((v) => (
              <button
                key={v}
                type="button"
                role="tab"
                aria-selected={view === v}
                onClick={() => setView(v)}
                className={`px-3 py-1.5 text-xs font-medium ${
                  view === v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
                }`}
              >
                {v === "results" ? "Results" : "Edit"}
              </button>
            ))}
          </div>
        ) : (
          <ModeSwitch active="manual" />
        )}
        {view === "edit" && state ? (
          editMode ? (
            <Button onClick={() => void save()} disabled={submitting || modifiedPosts.size === 0}>
              {submitting ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Save aria-hidden="true" className="size-4" />
              )}
              Save changes{modifiedPosts.size ? ` (${modifiedPosts.size})` : ""}
            </Button>
          ) : (
            <Button onClick={() => void create()} disabled={submitting || state.posts.length === 0}>
              {submitting ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <ArrowRight aria-hidden="true" className="size-4" />
              )}
              Create {state.posts.length} post{state.posts.length === 1 ? "" : "s"}
            </Button>
          )
        ) : null}
      </div>
    </div>
  )

  if (editMode && view === "results") {
    return (
      <div className="grid gap-4">
        {header}
        <BatchResults batchId={batchId!} platforms={platforms} onEdit={() => setView("edit")} />
      </div>
    )
  }

  if (!state) {
    return (
      <div className="grid gap-4">
        {header}
        {batchError ? (
          <p className="rounded-md border border-destructive/50 p-4 text-sm text-destructive">
            {batchError instanceof Error ? batchError.message : "Failed to load the batch"}
          </p>
        ) : batch && batch.tasks.every((t) => !t.composition) ? (
          <p className="rounded-md border p-4 text-sm text-muted-foreground">
            This batch has no stored compositions to edit.
          </p>
        ) : (
          <div className="h-96 animate-pulse rounded-md border bg-muted/30" />
        )}
      </div>
    )
  }

  const post = selected?.post
  const slide = selected?.slide
  const family = post ? familyOf(post.platform) : "square"
  const familyTemplates = (templates ?? [])
    .filter((t) => t.family === family && t.is_active !== false)
    .sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0))
  const limits = post ? slideLimits(post.platform) : { min: 1, max: 1 }
  const postIdx = post ? state.posts.indexOf(post) : -1

  return (
    <div className="grid gap-4">
      {header}

      {pendingDraft ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
          <span>You have unsaved edits to this batch from an earlier session.</span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setState(pendingDraft)
                const first = pendingDraft.posts[0]
                if (first) setSel({ postUid: first.uid, slideUid: first.slides[0].uid })
                setPendingDraft(null)
              }}
            >
              Restore
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                clearDraft(draftKey)
                setPendingDraft(null)
              }}
            >
              Discard
            </Button>
          </div>
        </div>
      ) : null}

      <BatchSetup
        systems={activeSystems}
        styles={styles}
        designSystemId={state.design_system_id}
        styleLanguage={state.style_language}
        ground={state.ground}
        title={state.title}
        remapping={remapping}
        showTitle={!editMode}
        onDesignSystem={(id) => void changeDesignSystem(id)}
        onStyleLanguage={(v) => update((s) => ({ ...s, style_language: v }))}
        onGround={(g: ComposeGround) => update((s) => ({ ...s, ground: g }))}
        onTitle={(t) => update((s) => ({ ...s, title: t }))}
      />
      {editMode ? (
        <p className="-mt-2 text-xs text-muted-foreground">
          Editing re-renders the existing tasks. Adding or removing posts isn't available here — start
          a new composition for more posts.
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[250px_minmax(0,1fr)_340px] xl:grid-cols-[280px_minmax(0,1fr)_400px]">
        <PostList
          state={state}
          platforms={platforms}
          selection={selected ? { postUid: selected.post.uid, slideUid: selected.slide.uid } : null}
          editMode={editMode}
          modifiedPosts={modifiedPosts}
          onSelect={setSel}
          onAdd={setAddMode}
          onMovePost={(uid, dir) =>
            update((s) => {
              const i = s.posts.findIndex((p) => p.uid === uid)
              return { ...s, posts: move(s.posts, i, i + dir) }
            })
          }
          onDuplicatePost={(uid) => {
            const src = state.posts.find((p) => p.uid === uid)
            if (!src || state.posts.length >= MAX_POSTS) return
            const copy = clonePost(src)
            update((s) => {
              const i = s.posts.findIndex((p) => p.uid === uid)
              const posts = [...s.posts]
              posts.splice(i + 1, 0, copy)
              return { ...s, posts }
            })
            setSel({ postUid: copy.uid, slideUid: copy.slides[0].uid })
          }}
          onDeletePost={(uid) =>
            withUndo("Post deleted", (s) => ({ ...s, posts: s.posts.filter((p) => p.uid !== uid) }))
          }
          onAddSlide={addSlide}
        />

        <div className="grid min-w-0 content-start gap-2 lg:sticky lg:top-20 lg:h-[calc(100vh-7rem)] lg:grid-rows-[auto_minmax(0,1fr)]">
          {post && slide ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium">
                  Post {postIdx + 1}
                  {post.slides.length > 1 ? (
                    <span className="text-muted-foreground">
                      {" "}
                      · slide {selected!.slideIdx + 1}/{post.slides.length}
                    </span>
                  ) : null}
                </p>
                {limits.max > 1 ? (
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Move slide left"
                      disabled={selected!.slideIdx === 0}
                      onClick={() => moveSlide(-1)}
                    >
                      <ChevronLeft aria-hidden="true" className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Move slide right"
                      disabled={selected!.slideIdx === post.slides.length - 1}
                      onClick={() => moveSlide(1)}
                    >
                      <ChevronRight aria-hidden="true" className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Duplicate slide"
                      disabled={post.slides.length >= limits.max}
                      onClick={duplicateSlide}
                    >
                      <Copy aria-hidden="true" className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Delete slide"
                      disabled={post.slides.length <= limits.min}
                      onClick={deleteSlide}
                    >
                      <Trash2 aria-hidden="true" className="size-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={post.slides.length >= limits.max}
                      onClick={() => addSlide(post.uid)}
                    >
                      <Plus aria-hidden="true" className="size-4" /> Slide
                    </Button>
                  </div>
                ) : null}
              </div>
              <LivePreview req={previewRequest(state, post, selected!.slideIdx)} />
            </>
          ) : (
            <div className="flex min-h-[360px] items-center justify-center rounded-md border border-dashed p-6 text-sm text-muted-foreground">
              {editMode ? "No posts." : "Add a post to start composing."}
            </div>
          )}
        </div>

        <aside aria-label="Slide settings" className="min-w-0 rounded-md border p-3">
          {post && slide ? (
            <SlideInspector
              key={slide.uid}
              slide={slide}
              family={family}
              orientation={orientationOf(post.platform)}
              templates={familyTemplates}
              templatesLoading={templatesLoading}
              ground={state.ground}
              multiSlide={post.slides.length > 1}
              onChange={patchSlide}
              onApplyTemplate={applyTemplate}
              onApplyMedia={applyMedia}
            />
          ) : (
            <p className="text-xs text-muted-foreground">Select a slide to edit it.</p>
          )}
        </aside>
      </div>

      {addMode ? (
        <AddPostsDialog
          open
          mode={addMode}
          platforms={platforms}
          remaining={MAX_POSTS - state.posts.length + (isPristine(state) ? 1 : 0)}
          defaultPlatform={post?.platform ?? DEFAULT_PLATFORM}
          templateFor={templateFor}
          onOpenChange={(o) => {
            if (!o) setAddMode(null)
          }}
          onCreate={addPosts}
        />
      ) : null}
    </div>
  )
}

function isPristine(s: EditorState): boolean {
  return (
    s.posts.length === 1 &&
    s.posts[0].slides.every((sl) => copyIsEmpty(sl.copy) && sl.media.kind === "none")
  )
}

function blankState(dsId: string): EditorState {
  return {
    design_system_id: dsId,
    style_language: "",
    ground: "white",
    title: "",
    posts: [newPost(DEFAULT_PLATFORM, 1, "")],
  }
}
