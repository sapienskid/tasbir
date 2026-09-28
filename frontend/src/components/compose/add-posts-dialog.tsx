import { useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { PlatformInfo } from "@/lib/api"
import type { AddMode } from "./post-list"
import {
  MAX_CAROUSEL_SLIDES,
  MIN_CAROUSEL_SLIDES,
  isCarouselPlatform,
  newPost,
  newSlide,
  platformLabel,
  splitPasted,
  uid,
  type EditorPost,
} from "./model"

const TITLES: Record<AddMode, { title: string; desc: string }> = {
  single: { title: "Add a post", desc: "One single-slide post." },
  carousel: {
    title: "Add a carousel",
    desc: `One carousel post with ${MIN_CAROUSEL_SLIDES}–${MAX_CAROUSEL_SLIDES} slides.`,
  },
  multiple: {
    title: "Add multiple posts",
    desc: "N single-slide posts on one platform — e.g. a set of quote cards.",
  },
  paste: {
    title: "Paste a list",
    desc: "Each item becomes its own post (or its own slide of one carousel), using the selected template.",
  },
}

/**
 * Presets + paste helper for adding posts. Emits ready-made editor posts;
 * the page appends them (capped at `remaining`).
 */
export function AddPostsDialog({
  open,
  mode,
  platforms,
  remaining,
  defaultPlatform,
  templateFor,
  onOpenChange,
  onCreate,
}: {
  open: boolean
  mode: AddMode
  platforms: PlatformInfo[]
  remaining: number
  defaultPlatform: string
  /** Template id to use for a platform (prefers the currently selected one). */
  templateFor: (platform: string) => string
  onOpenChange: (open: boolean) => void
  onCreate: (posts: EditorPost[]) => void
}) {
  const carouselRows = useMemo(() => platforms.filter((p) => isCarouselPlatform(p.id)), [platforms])
  const singleRows = useMemo(() => platforms.filter((p) => !isCarouselPlatform(p.id)), [platforms])

  const [platform, setPlatform] = useState("")
  const [count, setCount] = useState(3)
  const [text, setText] = useState("")
  const [split, setSplit] = useState<"paragraphs" | "lines">("paragraphs")
  const [target, setTarget] = useState<"headline" | "body">("headline")
  const [pasteAs, setPasteAs] = useState<"posts" | "carousel">("posts")

  const choices =
    mode === "carousel" || (mode === "paste" && pasteAs === "carousel")
      ? carouselRows
      : singleRows

  // Re-seed the form whenever the dialog opens for a (new) mode.
  useEffect(() => {
    if (!open) return
    setCount(mode === "carousel" ? 5 : 3)
    setText("")
  }, [open, mode])

  useEffect(() => {
    if (!open) return
    if (choices.some((p) => p.id === platform)) return
    const pref = choices.find((p) => p.id === defaultPlatform) ?? choices[0]
    setPlatform(pref?.id ?? "")
  }, [open, choices, platform, defaultPlatform])

  const items = useMemo(() => (mode === "paste" ? splitPasted(text, split) : []), [mode, text, split])

  let preview = ""
  let blocked = !platform
  if (mode === "multiple") {
    blocked ||= count < 1
    preview = `${Math.min(count, remaining)} post(s)`
  } else if (mode === "paste") {
    if (pasteAs === "carousel") {
      blocked ||= items.length < MIN_CAROUSEL_SLIDES
      preview = `1 carousel · ${Math.min(items.length, MAX_CAROUSEL_SLIDES)} slide(s)`
    } else {
      blocked ||= items.length === 0
      preview = `${Math.min(items.length, remaining)} post(s)`
    }
  }
  blocked ||= remaining <= 0

  function create() {
    const tid = templateFor(platform)
    let posts: EditorPost[] = []
    if (mode === "single") {
      posts = [newPost(platform, 1, tid)]
    } else if (mode === "carousel") {
      posts = [newPost(platform, count, tid)]
    } else if (mode === "multiple") {
      posts = Array.from({ length: Math.min(count, remaining) }, () => newPost(platform, 1, tid))
    } else if (pasteAs === "carousel") {
      const slides = items
        .slice(0, MAX_CAROUSEL_SLIDES)
        .map((item) => newSlide(tid, { [target]: item }))
      posts = [{ uid: uid(), platform, slides }]
    } else {
      // Paste as posts: one single-slide post per item (non-carousel platforms).
      posts = items.slice(0, remaining).map((item) => ({
        uid: uid(),
        platform,
        slides: [newSlide(tid, { [target]: item })],
      }))
    }
    onCreate(posts)
    onOpenChange(false)
  }

  const meta = TITLES[mode]
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{meta.title}</DialogTitle>
          <DialogDescription>{meta.desc}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          {mode === "paste" ? (
            <div className="grid gap-1.5">
              <span id="paste-as-label" className="text-xs text-muted-foreground">
                Create
              </span>
              <div role="radiogroup" aria-labelledby="paste-as-label" className="flex w-fit overflow-hidden rounded-md border">
                {(["posts", "carousel"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    role="radio"
                    aria-checked={pasteAs === v}
                    onClick={() => setPasteAs(v)}
                    className={`px-3 py-1.5 text-xs font-medium ${
                      pasteAs === v ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                    }`}
                  >
                    {v === "posts" ? "One post per item" : "One carousel, slide per item"}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="grid gap-1.5">
            <Label htmlFor="add-platform">Platform</Label>
            <Select value={platform} onValueChange={setPlatform}>
              <SelectTrigger id="add-platform" className="w-full">
                <SelectValue placeholder="Choose a platform" />
              </SelectTrigger>
              <SelectContent>
                {choices.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {platformLabel(p)} · {p.width}×{p.height}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {mode === "carousel" || mode === "multiple" ? (
            <div className="grid gap-1.5">
              <Label htmlFor="add-count">
                {mode === "carousel" ? "Slides" : "Number of posts"}
              </Label>
              <Input
                id="add-count"
                type="number"
                className="w-24"
                min={mode === "carousel" ? MIN_CAROUSEL_SLIDES : 1}
                max={mode === "carousel" ? MAX_CAROUSEL_SLIDES : Math.max(1, remaining)}
                value={count}
                onChange={(e) => {
                  const n = Number(e.target.value) || 1
                  setCount(
                    mode === "carousel"
                      ? Math.min(MAX_CAROUSEL_SLIDES, Math.max(MIN_CAROUSEL_SLIDES, n))
                      : Math.min(Math.max(1, remaining), Math.max(1, n))
                  )
                }}
              />
            </div>
          ) : null}

          {mode === "paste" ? (
            <>
              <div className="grid gap-1.5">
                <Label htmlFor="add-paste">Items</Label>
                <Textarea
                  id="add-paste"
                  className="min-h-40"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={
                    split === "paragraphs"
                      ? "First quote…\n\nSecond quote…\n\nThird quote…"
                      : "One item per line"
                  }
                />
              </div>
              <div className="flex flex-wrap items-center gap-4">
                <div className="grid gap-1.5">
                  <Label htmlFor="add-split" className="text-xs text-muted-foreground">
                    Split by
                  </Label>
                  <Select value={split} onValueChange={(v) => setSplit(v as typeof split)}>
                    <SelectTrigger id="add-split" className="w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="paragraphs">Blank lines</SelectItem>
                      <SelectItem value="lines">Each line</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="add-target" className="text-xs text-muted-foreground">
                    Put text into
                  </Label>
                  <Select value={target} onValueChange={(v) => setTarget(v as typeof target)}>
                    <SelectTrigger id="add-target" className="w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="headline">Headline</SelectItem>
                      <SelectItem value="body">Body</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {pasteAs === "carousel" && items.length > MAX_CAROUSEL_SLIDES ? (
                <p className="text-xs text-amber-600">
                  Only the first {MAX_CAROUSEL_SLIDES} items fit in one carousel.
                </p>
              ) : null}
              {pasteAs === "posts" && items.length > remaining ? (
                <p className="text-xs text-amber-600">
                  Only {remaining} more post(s) fit in this batch — the rest are dropped.
                </p>
              ) : null}
            </>
          ) : null}

          {remaining <= 0 ? (
            <p className="text-xs text-destructive">This batch already has the maximum number of posts.</p>
          ) : null}
          {platform && !templateFor(platform) ? (
            <p className="text-xs text-muted-foreground">
              No template for this platform's family in the design system — pick one per slide later.
            </p>
          ) : null}
        </div>
        <DialogFooter className="items-center">
          {preview ? <span className="mr-auto text-xs text-muted-foreground">{preview}</span> : null}
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={create} disabled={blocked}>
            Add
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
