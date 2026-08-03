import { useEffect, useRef, useState } from "react"
import { Loader2, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { listDefaultFonts, searchGoogleFonts, type GoogleFont } from "@/lib/api"

const CATEGORY_LABEL: Record<string, string> = {
  "sans-serif": "Sans",
  serif: "Serif",
  display: "Display",
  monospace: "Mono",
  handwriting: "Handwriting",
}

const CATEGORY_ORDER = ["sans-serif", "serif", "display", "monospace", "handwriting"]

function categoryLabel(category: string): string {
  return CATEGORY_LABEL[category] ?? "Other"
}

/**
 * Build a single Google Fonts css2 URL for a list of families, subsetted to
 * only the glyphs needed to spell their names (`text=` param). That keeps the
 * whole preview list to a handful of kilobytes per family in ONE request,
 * instead of downloading every full font file.
 */
function buildPreviewLink(fonts: GoogleFont[]): string {
  const fams = fonts.map((f) => f.family)
  const frag = fams.map((f) => `family=${encodeURIComponent(f)}:wght@400`).join("&")
  const text = encodeURIComponent(fams.join(""))
  return `https://fonts.googleapis.com/css2?${frag}&text=${text}&display=swap`
}

/**
 * Searchable Google Fonts picker — type to search the full catalog, pick a
 * family. Results are grouped by type (sans/serif/display/mono/…) and each
 * option is rendered in its own typeface via glyph-subsetted font loading.
 *
 * ``categories`` limits the picker to specific font types (e.g. the sans role
 * only shows sans-serif). Omit it to allow any typeface.
 */
export function FontPickerDialog({
  open,
  onOpenChange,
  currentFamily,
  onPick,
  categories,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentFamily: string
  onPick: (family: string) => void
  categories?: string[]
}) {
  const [q, setQ] = useState("")
  const [defaults, setDefaults] = useState<GoogleFont[]>([])
  const [results, setResults] = useState<GoogleFont[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<number | undefined>(undefined)

  // On open: show the curated per-category set immediately, no search needed.
  useEffect(() => {
    if (open) {
      setQ("")
      setResults([])
      setError(null)
      setLoading(true)
      listDefaultFonts()
        .then((fs) => setDefaults(fs))
        .catch((e) => setError(e instanceof Error ? e.message : "Failed to load fonts"))
        .finally(() => setLoading(false))
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    window.clearTimeout(timer.current)
    const query = q.trim()
    if (!query) {
      setResults([])
      setError(null)
      return
    }
    setLoading(true)
    timer.current = window.setTimeout(() => {
      searchGoogleFonts(query)
        .then((fs) => setResults(fs))
        .catch((e) => setError(e instanceof Error ? e.message : "Search failed"))
        .finally(() => setLoading(false))
    }, 300)
    return () => window.clearTimeout(timer.current)
  }, [q, open])

  const fonts = (q.trim() ? results : defaults).filter(
    (f) => !categories || categories.includes(f.category)
  )

  // Load the visible families as glyph-subsetted webfonts so each row renders
  // in its own typeface. One stylesheet link for the whole result set.
  useEffect(() => {
    if (!open || fonts.length === 0) return
    const link = document.createElement("link")
    link.rel = "stylesheet"
    link.href = buildPreviewLink(fonts)
    link.dataset.fontpicker = "true"
    document.head.appendChild(link)
    return () => {
      link.remove()
    }
  }, [open, fonts])

  function pick(family: string) {
    onPick(family)
    onOpenChange(false)
  }

  const groups = CATEGORY_ORDER.map((cat) => ({
    label: categoryLabel(cat),
    items: fonts.filter((f) => f.category === cat),
  })).filter((g) => g.items.length > 0)
  const leftovers = fonts.filter((f) => !CATEGORY_ORDER.includes(f.category))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Choose a Google Font</DialogTitle>
          <DialogDescription>
            Currently <span className="font-mono">{currentFamily || "—"}</span>. Each option renders
            in its own typeface; the fallback stack is preserved on pick.
          </DialogDescription>
        </DialogHeader>
        <div className="relative">
          <Search aria-hidden="true" className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            autoFocus
            aria-label="Search fonts"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search fonts…"
            className="pl-8"
          />
        </div>
        <ScrollArea className="h-72 rounded-md border">
          {error ? (
            <p className="p-4 text-sm text-destructive">{error}</p>
          ) : loading ? (
            <div className="flex items-center justify-center p-8">
              <Loader2 className="size-5 animate-spin text-muted-foreground" />
            </div>
          ) : fonts.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">
              {q.trim() ? "No matches." : "No fonts available."}
            </p>
          ) : (
            <ul>
              {groups.map((g) => (
                <li key={g.label}>
                  <p className="sticky top-0 border-y bg-background/95 px-3 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground backdrop-blur">
                    {g.label}
                  </p>
                  {g.items.map((f) => (
                    <FontRow key={f.family} font={f} onPick={pick} />
                  ))}
                </li>
              ))}
              {leftovers.length > 0 ? (
                <li>
                  <p className="sticky top-0 border-y bg-background/95 px-3 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground backdrop-blur">
                    Other
                  </p>
                  {leftovers.map((f) => (
                    <FontRow key={f.family} font={f} onPick={pick} />
                  ))}
                </li>
              ) : null}
            </ul>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}

function FontRow({
  font,
  onPick,
}: {
  font: GoogleFont
  onPick: (family: string) => void
}) {
  return (
    <li>
      <Button
        type="button"
        variant="ghost"
        className="h-auto w-full justify-between rounded-none px-3 py-2"
        onClick={() => onPick(font.family)}
      >
        <span
          className="truncate text-base leading-tight"
          style={{ fontFamily: `"${font.family}", sans-serif` }}
        >
          {font.family}
        </span>
        <span className="shrink-0 text-xs capitalize text-muted-foreground">
          {categoryLabel(font.category)}
        </span>
      </Button>
    </li>
  )
}
