import { useState } from "react"
import useSWR from "swr"
import type { CoverMeta } from "@/lib/covers"
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

function IllustrationThumb({ style, seed, ground, designSystemId, styleLanguage, motif, size }: {
  style: string; seed: string; ground: ComposeGround; designSystemId: string;
  styleLanguage: string; motif: string; size: string;
}) {
  const { data, error, isLoading } = useIllustration(style, seed, ground, designSystemId, styleLanguage, motif, size)
  return (
    <div className="flex aspect-[5/3] w-full items-center justify-center overflow-hidden rounded-md border bg-muted/20">
      {data ? <iframe title={`${style} illustration preview`} srcDoc={data.html} sandbox="" className="size-full border-0" />
        : error ? <span className="p-2 text-center text-xs text-destructive">{error instanceof Error ? error.message : "Preview failed"}</span>
        : isLoading ? <Loader2 aria-hidden="true" className="size-4 animate-spin text-muted-foreground" /> : null}
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
  designSystemId = "default",
  styleLanguage = "",
  orientation,
  multiSlide,
  onChange,
  onApplyAll,
  hideApply = false,
}: {
  media: ComposeMedia
  designSystemId?: string
  styleLanguage?: string
  mediaKinds: Array<"image" | "illustration">
  ground: ComposeGround
  orientation: "square" | "portrait" | "landscape"
  multiSlide: boolean
  onChange: (m: ComposeMedia) => void
  onApplyAll: (scope: "post" | "all") => void
  /** Hide the bulk-apply buttons (single-format editors apply directly). */
  hideApply?: boolean
}) {
  const { data: artMeta } = useSWR<CoverMeta>("/covers/meta")
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
        <div role="radiogroup" aria-label="Media type" className="flex min-w-0 flex-wrap overflow-hidden rounded-md border">
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
          {!hideApply ? (
            <Button size="xs" variant="outline" onClick={() => onApplyAll("all")}>
              Apply to all posts
            </Button>
          ) : null}
        </div>
      </div>

      {media.kind === "upload" ? (
        <div className="grid gap-3">
          {media.data ? (
            <div className="relative w-fit">
              <img
                src={`data:${media.mime};base64,${media.data}`}
                alt={media.alt || "Uploaded image"}
                className="max-h-48 max-w-full rounded-md border object-contain"
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
            className="flex min-w-0 gap-2"
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
              className="min-w-0 flex-1"
            />
            <Button type="submit" variant="outline" disabled={searching || !query.trim()} className="shrink-0">
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
            <div role="radiogroup" aria-label="Photo results" className="grid max-h-80 min-w-0 grid-cols-3 gap-1.5 overflow-y-auto">
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
          {media.style === "procedural" && <div className="grid gap-2">
            <Label htmlFor="ill-motif">Composition</Label>
            <select id="ill-motif" value={media.motif || "auto"} className="h-9 w-full border bg-background px-2 text-sm"
              onChange={(e) => onChange({ ...media, motif: e.target.value })}>
              <option value="auto">From the post</option>
              {(artMeta?.concepts ?? []).map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </div>}
          <div className="grid gap-2">
            <Label htmlFor="ill-size">Art size in post</Label>
            <select id="ill-size" value={media.size || "template"} className="h-9 w-full border bg-background px-2 text-sm"
              onChange={(e) => onChange({ ...media, size: e.target.value as "template" | "large" })}>
              <option value="template">Template size</option><option value="large">Larger fitted artwork</option>
            </select>
          </div>
          <IllustrationThumb style={media.style} seed={media.seed} ground={ground} designSystemId={designSystemId}
            styleLanguage={styleLanguage} motif={media.motif || "auto"} size={media.size || "template"} />
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
