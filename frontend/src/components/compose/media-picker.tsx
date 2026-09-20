import { useState } from "react"
import { Loader2, Search, Shuffle, X } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Dropzone } from "@/components/tasks/dropzone"
import { useIllustration } from "@/hooks/use-compose"
import {
  searchComposePhotos,
  uploadMedia,
  type ComposeGround,
  type ComposeMedia,
  type ComposePhoto,
} from "@/lib/api"
import { ILLUSTRATION_STYLES, randomSeed } from "./model"

type Kind = ComposeMedia["kind"]

const KINDS: Array<{ id: Kind; label: string }> = [
  { id: "none", label: "None" },
  { id: "upload", label: "Upload" },
  { id: "photo", label: "Stock photo" },
  { id: "illustration", label: "Illustration" },
]

// Upload/photo need an image slot; illustration needs an {{ illustration }} slot.
function kindAllowed(kind: Kind, mediaKinds: Array<"image" | "illustration">): boolean {
  if (kind === "none") return true
  if (kind === "illustration") return mediaKinds.includes("illustration")
  return mediaKinds.includes("image")
}

// The illustration SVG only uses ground-adaptive CSS vars — give the sandboxed
// thumbnail a neutral monochrome palette so it reads like the rendered post.
function illustrationDoc(svg: string, ground: ComposeGround): string {
  const dark = ground === "black"
  const vars = dark
    ? "--color-text:#fff;--color-text-inverted:#fff;--color-text-secondary:#aaa;--color-text-tertiary:#555;--color-bg:#000;--color-bg-inverted:#000"
    : "--color-text:#000;--color-text-inverted:#fff;--color-text-secondary:#555;--color-text-tertiary:#bbb;--color-bg:#fff;--color-bg-inverted:#000"
  return `<!doctype html><html><head><style>:root{${vars}}html,body{margin:0;height:100%;background:var(--color-bg)}
.figure{--ill-ink:var(--color-text);--ill-mid:var(--color-text-secondary);--ill-light:var(--color-text-tertiary);--ill-paper:var(--color-bg);width:100%;height:100%}
.figure svg,body>svg{width:100%;height:100%;display:block}</style></head><body data-ground="${ground}">${svg}</body></html>`
}

function IllustrationThumb({ style, seed, ground }: { style: string; seed: string; ground: ComposeGround }) {
  const { data, error, isLoading } = useIllustration(style, seed, ground)
  return (
    <div className="flex size-40 items-center justify-center overflow-hidden rounded-md border bg-muted/20">
      {data ? (
        <iframe
          title={`${style} illustration preview`}
          srcDoc={illustrationDoc(data.svg, ground)}
          sandbox=""
          className="size-full border-0"
        />
      ) : error ? (
        <span className="p-2 text-center text-[11px] text-destructive">
          {error instanceof Error ? error.message : "Preview failed"}
        </span>
      ) : isLoading ? (
        <Loader2 aria-hidden="true" className="size-4 animate-spin text-muted-foreground" />
      ) : null}
    </div>
  )
}

/**
 * Media tab: none / upload (via /uploads) / stock photo search / procedural or
 * DiceBear illustration with a shuffle that re-rolls the seed.
 */
export function MediaPicker({
  media,
  mediaKinds,
  ground,
  orientation,
  multiSlide,
  onChange,
  onApplyAll,
}: {
  media: ComposeMedia
  mediaKinds: Array<"image" | "illustration">
  ground: ComposeGround
  orientation: "square" | "portrait" | "landscape"
  multiSlide: boolean
  onChange: (m: ComposeMedia) => void
  onApplyAll: (scope: "post" | "all") => void
}) {
  const [uploading, setUploading] = useState(false)
  const [query, setQuery] = useState("")
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState<ComposePhoto[] | null>(null)
  const [illStyle, setIllStyle] = useState(
    media.kind === "illustration" ? media.style : "procedural"
  )

  function switchKind(kind: Kind) {
    if (kind === media.kind) return
    if (kind === "none") onChange({ kind: "none" })
    else if (kind === "illustration") onChange({ kind: "illustration", style: illStyle, seed: randomSeed() })
    else if (kind === "upload") onChange({ kind: "upload", data: "", mime: "image/png", alt: "" })
    else onChange({ kind: "photo", url: "", credit: "", provider: "", photographer: "", license: "" })
  }

  async function handleFile(file: File) {
    setUploading(true)
    try {
      const res = await uploadMedia(file)
      onChange({
        kind: "upload",
        data: res.data,
        mime: res.mime,
        alt: media.kind === "upload" ? media.alt : "",
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploading(false)
    }
  }

  async function search() {
    const q = query.trim()
    if (!q) return
    setSearching(true)
    try {
      const res = await searchComposePhotos(q, orientation)
      setResults(res.results ?? [])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Photo search failed")
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="radiogroup" aria-label="Media type" className="flex overflow-hidden rounded-md border">
          {KINDS.filter((k) => kindAllowed(k.id, mediaKinds)).map((k) => (
            <button
              key={k.id}
              type="button"
              role="radio"
              aria-checked={media.kind === k.id}
              onClick={() => switchKind(k.id)}
              className={`px-2.5 py-1.5 text-xs font-medium transition-colors ${
                media.kind === k.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              {k.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {multiSlide ? (
            <Button size="xs" variant="outline" onClick={() => onApplyAll("post")}>
              Apply to all slides
            </Button>
          ) : null}
          <Button size="xs" variant="outline" onClick={() => onApplyAll("all")}>
            Apply to all posts
          </Button>
        </div>
      </div>

      {media.kind === "upload" ? (
        <div className="grid gap-3">
          {media.data ? (
            <div className="relative w-fit">
              <img
                src={`data:${media.mime};base64,${media.data}`}
                alt={media.alt || "Uploaded image"}
                className="max-h-48 rounded-md border object-contain"
              />
              <Button
                size="icon-xs"
                variant="secondary"
                aria-label="Remove image"
                className="absolute top-1 right-1"
                onClick={() => onChange({ ...media, data: "" })}
              >
                <X aria-hidden="true" />
              </Button>
            </div>
          ) : null}
          <Dropzone
            busy={uploading}
            onFile={(f) => void handleFile(f)}
            hint={media.data ? "Replaces the current image" : "PNG, JPEG, WebP or GIF"}
          />
          <div className="grid gap-1">
            <Label htmlFor="media-alt" className="text-xs">
              Alt text
            </Label>
            <Input
              id="media-alt"
              value={media.alt}
              maxLength={300}
              onChange={(e) => onChange({ ...media, alt: e.target.value })}
            />
          </div>
        </div>
      ) : null}

      {media.kind === "photo" ? (
        <div className="grid gap-3">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              void search()
            }}
          >
            <Input
              aria-label="Search stock photos"
              placeholder="Search stock photos…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <Button type="submit" variant="outline" disabled={searching || !query.trim()}>
              {searching ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Search aria-hidden="true" className="size-4" />
              )}
              Search
            </Button>
          </form>
          {media.url ? (
            <p className="text-[11px] text-muted-foreground">
              Selected: {media.credit || media.photographer || media.url}
            </p>
          ) : null}
          {results && results.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No photos found. Stock photo search needs a Pexels / Unsplash / Pixabay API key on the server.
            </p>
          ) : null}
          {results && results.length > 0 ? (
            <div role="radiogroup" aria-label="Photo results" className="grid max-h-80 grid-cols-3 gap-1.5 overflow-y-auto">
              {results.map((p) => {
                const selected = media.url === p.url
                return (
                  <button
                    key={p.url}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    aria-label={p.credit || `Photo by ${p.photographer}`}
                    title={p.credit}
                    onClick={() =>
                      onChange({
                        kind: "photo",
                        url: p.url,
                        credit: p.credit,
                        provider: p.provider,
                        photographer: p.photographer,
                        license: p.license,
                      })
                    }
                    className={`aspect-square overflow-hidden rounded-md border ${
                      selected ? "ring-2 ring-primary" : "hover:opacity-80"
                    }`}
                  >
                    <img src={p.thumb || p.url} alt="" loading="lazy" className="size-full object-cover" />
                  </button>
                )
              })}
            </div>
          ) : null}
        </div>
      ) : null}

      {media.kind === "illustration" ? (
        <div className="grid gap-3">
          <div className="flex flex-wrap items-end gap-2">
            <div className="grid gap-1">
              <Label htmlFor="ill-style" className="text-xs">
                Style
              </Label>
              <Select
                value={media.style}
                onValueChange={(v) => {
                  setIllStyle(v)
                  onChange({ ...media, style: v })
                }}
              >
                <SelectTrigger id="ill-style" className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ILLUSTRATION_STYLES.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button variant="outline" onClick={() => onChange({ ...media, seed: randomSeed() })}>
              <Shuffle aria-hidden="true" className="size-4" />
              Shuffle
            </Button>
          </div>
          <IllustrationThumb style={media.style} seed={media.seed} ground={ground} />
          <p className="text-[11px] text-muted-foreground">Seed {media.seed}</p>
        </div>
      ) : null}

      {media.kind === "none" ? (
        <p className="text-xs text-muted-foreground">
          No media — the template renders its text-only layout.
        </p>
      ) : null}
    </div>
  )
}
