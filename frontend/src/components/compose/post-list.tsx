import { ArrowDown, ArrowUp, Copy, Layers, ListPlus, Plus, Trash2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { PlatformInfo } from "@/lib/api"
import {
  MAX_POSTS,
  isCarouselPlatform,
  platformLabel,
  previewRequest,
  slideLimits,
  type EditorState,
  type Selection,
} from "./model"
import { SlideThumb } from "./slide-thumb"

export type AddMode = "single" | "carousel" | "multiple" | "paste"

/**
 * Left rail: every post of the batch with its slide thumbnails, post-level
 * actions (reorder / duplicate / delete) and the "Add" menu (presets + paste).
 */
export function PostList({
  state,
  platforms,
  selection,
  editMode,
  modifiedPosts,
  onSelect,
  onAdd,
  onMovePost,
  onDuplicatePost,
  onDeletePost,
  onAddSlide,
}: {
  state: EditorState
  platforms: PlatformInfo[]
  selection: Selection | null
  editMode: boolean
  modifiedPosts: Set<string>
  onSelect: (sel: Selection) => void
  onAdd: (mode: AddMode) => void
  onMovePost: (uid: string, dir: -1 | 1) => void
  onDuplicatePost: (uid: string) => void
  onDeletePost: (uid: string) => void
  onAddSlide: (postUid: string) => void
}) {
  const full = state.posts.length >= MAX_POSTS
  const labelOf = (id: string) => platformLabel(platforms.find((p) => p.id === id) ?? { id })

  return (
    <section aria-labelledby="compose-posts-heading" className="grid content-start gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="compose-posts-heading" className="text-sm font-semibold">
          Posts{" "}
          <span className="font-normal text-muted-foreground tabular-nums">
            {state.posts.length}/{MAX_POSTS}
          </span>
        </h2>
        {editMode ? (
          <span className="text-[11px] text-muted-foreground">Editing existing posts</span>
        ) : (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="outline" disabled={full}>
                <Plus aria-hidden="true" className="size-4" />
                Add
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => onAdd("single")}>
                <Plus aria-hidden="true" className="size-4" /> Single post
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onAdd("carousel")}>
                <Layers aria-hidden="true" className="size-4" /> Carousel (N slides)
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onAdd("multiple")}>
                <Copy aria-hidden="true" className="size-4" /> Multiple posts
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onAdd("paste")}>
                <ListPlus aria-hidden="true" className="size-4" /> Paste list…
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {state.posts.length === 0 ? (
        <p className="rounded-md border border-dashed p-4 text-center text-xs text-muted-foreground">
          No posts yet — use Add to start.
        </p>
      ) : null}

      <ol className="grid gap-2">
        {state.posts.map((post, pi) => {
          const activePost = selection?.postUid === post.uid
          const { max } = slideLimits(post.platform)
          const carousel = isCarouselPlatform(post.platform)
          return (
            <li
              key={post.uid}
              className={`grid gap-2 rounded-md border p-2 ${activePost ? "border-primary" : ""}`}
            >
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onSelect({ postUid: post.uid, slideUid: post.slides[0].uid })}
                >
                  <span className="block truncate text-xs font-medium">
                    {pi + 1}. {labelOf(post.platform)}
                  </span>
                  <span className="block text-[10px] text-muted-foreground">
                    {carousel ? `${post.slides.length} slides` : "single"}
                    {modifiedPosts.has(post.uid) ? " · modified" : ""}
                  </span>
                </button>
                {!editMode ? (
                  <>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      aria-label={`Move post ${pi + 1} up`}
                      disabled={pi === 0}
                      onClick={() => onMovePost(post.uid, -1)}
                    >
                      <ArrowUp aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      aria-label={`Move post ${pi + 1} down`}
                      disabled={pi === state.posts.length - 1}
                      onClick={() => onMovePost(post.uid, 1)}
                    >
                      <ArrowDown aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      aria-label={`Duplicate post ${pi + 1}`}
                      disabled={full}
                      onClick={() => onDuplicatePost(post.uid)}
                    >
                      <Copy aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      aria-label={`Delete post ${pi + 1}`}
                      onClick={() => onDeletePost(post.uid)}
                    >
                      <Trash2 aria-hidden="true" />
                    </Button>
                  </>
                ) : post.task_id ? (
                  <Badge variant="outline" className="text-[9px]">
                    task
                  </Badge>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {post.slides.map((slide, si) => (
                  <SlideThumb
                    key={slide.uid}
                    req={previewRequest(state, post, si)}
                    label={`Post ${pi + 1}, slide ${si + 1}`}
                    selected={activePost && selection?.slideUid === slide.uid}
                    onSelect={() => onSelect({ postUid: post.uid, slideUid: slide.uid })}
                  />
                ))}
                {carousel && post.slides.length < max ? (
                  <button
                    type="button"
                    aria-label={`Add slide to post ${pi + 1}`}
                    onClick={() => onAddSlide(post.uid)}
                    className="flex w-10 items-center justify-center rounded-md border border-dashed text-muted-foreground hover:bg-muted/40"
                  >
                    <Plus aria-hidden="true" className="size-4" />
                  </button>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
