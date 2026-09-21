import { Loader2 } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { ComposeGround, DesignSystem, StyleLanguage } from "@/lib/api"

// Radix Select forbids "" as an item value — sentinel for "DS's own".
const OWN_LANGUAGE = "__own__"

/**
 * Batch-level settings shared by every post: design system, design language
 * override, ground and an optional title.
 */
export function BatchSetup({
  systems,
  styles,
  designSystemId,
  styleLanguage,
  ground,
  title,
  remapping,
  showTitle = true,
  onDesignSystem,
  onStyleLanguage,
  onGround,
  onTitle,
}: {
  systems: DesignSystem[]
  styles: StyleLanguage[]
  designSystemId: string
  styleLanguage: string
  ground: ComposeGround
  title: string
  remapping: boolean
  /** The title only applies to new batches (PUT has no title). */
  showTitle?: boolean
  onDesignSystem: (id: string) => void
  onStyleLanguage: (id: string) => void
  onGround: (g: ComposeGround) => void
  onTitle: (t: string) => void
}) {
  const ds = systems.find((s) => s.id === designSystemId)
  const ownLanguage =
    (ds?.design_instruction as { style_language?: string } | undefined)?.style_language ||
    "none"
  return (
    <div className="grid gap-3 rounded-md border p-3 sm:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_minmax(0,1fr)] xl:items-end">
      <div className="grid gap-1.5">
        <Label htmlFor="compose-ds" className="text-xs text-muted-foreground">
          Design system
        </Label>
        <div className="flex items-center gap-2">
          <Select value={designSystemId} onValueChange={onDesignSystem} disabled={remapping}>
            <SelectTrigger id="compose-ds" className="w-full">
              <SelectValue placeholder="Choose…" />
            </SelectTrigger>
            <SelectContent>
              {systems.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {remapping ? (
            <Loader2
              aria-label="Remapping templates"
              className="size-4 shrink-0 animate-spin text-muted-foreground"
            />
          ) : null}
        </div>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="compose-lang" className="text-xs text-muted-foreground">
          Design language
        </Label>
        <Select
          value={styleLanguage || OWN_LANGUAGE}
          onValueChange={(v) => onStyleLanguage(v === OWN_LANGUAGE ? "" : v)}
        >
          <SelectTrigger id="compose-lang" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={OWN_LANGUAGE}>System's own ({ownLanguage})</SelectItem>
            {styles.map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-1.5">
        <span id="compose-ground-label" className="text-xs text-muted-foreground">
          Ground
        </span>
        <div
          role="radiogroup"
          aria-labelledby="compose-ground-label"
          className="flex h-9 overflow-hidden rounded-md border"
        >
          {(["white", "black"] as const).map((g) => (
            <button
              key={g}
              type="button"
              role="radio"
              aria-checked={ground === g}
              onClick={() => onGround(g)}
              className={`flex items-center gap-1.5 px-3 text-xs font-medium capitalize transition-colors ${
                ground === g
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              <span
                aria-hidden="true"
                className={`size-3 rounded-full border ${g === "white" ? "bg-white" : "bg-black"}`}
              />
              {g}
            </button>
          ))}
        </div>
      </div>
      {showTitle ? (
        <div className="grid gap-1.5">
          <Label htmlFor="compose-title" className="text-xs text-muted-foreground">
            Batch title (optional)
          </Label>
          <Input
            id="compose-title"
            value={title}
            maxLength={200}
            placeholder="e.g. Weekly quotes"
            onChange={(e) => onTitle(e.target.value)}
          />
        </div>
      ) : null}
    </div>
  )
}
