import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { AlertTriangle } from "lucide-react"

/** Sentinel for "the design system's own language" — a real value, not "" shown raw. */
export const OWN_LANGUAGE = "__own__"

export interface RecipeControlsProps {
  ground: "white" | "black"
  styleLanguage: string
  /** Languages available for the post's design system. */
  styles: Array<{ id: string; label: string; source?: string }>
  /** The system's own language label, for the "own" option. */
  ownLanguageLabel?: string
  onGround: (g: "white" | "black") => void
  onStyleLanguage: (id: string) => void
  /** Grounds the current template declares; a mismatch is rejected server-side. */
  templateGrounds?: string[]
  disabled?: boolean
}

/**
 * Per-post ground + design language.
 *
 * These live in the format's recipe (see services/format_recipe), which is what
 * finally makes them editable on an AI-generated post: they used to be frozen
 * in the task's strategic brief. Mirrors Manual Compose's BatchSetup controls so
 * the two editors speak the same language.
 */
export function RecipeControls({
  ground,
  styleLanguage,
  styles,
  ownLanguageLabel,
  onGround,
  onStyleLanguage,
  templateGrounds,
  disabled,
}: RecipeControlsProps) {
  const allowed = templateGrounds?.filter((g) => g === "white" || g === "black") ?? []
  const blocked = allowed.length > 0 && !allowed.includes(ground)

  return (
    <div className="grid gap-3">
      <div className="grid gap-1.5">
        <Label htmlFor="recipe-language" className="text-xs text-muted-foreground">
          Design language
        </Label>
        <Select
          value={styleLanguage || OWN_LANGUAGE}
          onValueChange={(v) => onStyleLanguage(v === OWN_LANGUAGE ? "" : v)}
          disabled={disabled}
        >
          <SelectTrigger id="recipe-language" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={OWN_LANGUAGE}>
              System&apos;s own{ownLanguageLabel ? ` (${ownLanguageLabel})` : ""}
            </SelectItem>
            {styles.map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-[11px] text-muted-foreground">
          Re-renders this post with the language&apos;s palette and type rules.
        </p>
      </div>

      <div className="grid gap-1.5">
        <span id="recipe-ground-label" className="text-xs text-muted-foreground">
          Ground
        </span>
        <div
          role="radiogroup"
          aria-labelledby="recipe-ground-label"
          className="flex h-9 overflow-hidden rounded-md border"
        >
          {(["white", "black"] as const).map((g) => {
            // Still selectable — picking it surfaces the server's 422 with an
            // actionable message rather than silently greyed out.
            const unsupported = allowed.length > 0 && !allowed.includes(g)
            return (
              <button
                key={g}
                type="button"
                role="radio"
                aria-checked={ground === g}
                disabled={disabled}
                title={
                  unsupported
                    ? `${g} only — this template was authored for ${allowed.join("/")}`
                    : undefined
                }
                onClick={() => onGround(g)}
                className={`flex items-center gap-1.5 px-3 text-xs font-medium capitalize transition-colors disabled:opacity-50 ${
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
            )
          })}
        </div>
        {blocked ? (
          <p className="flex items-start gap-1.5 text-[11px] text-destructive">
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-3 shrink-0" />
            <span>
              The current template is built for {allowed.join("/")} ground only. Pick a template
              that supports {ground} to switch.
            </span>
          </p>
        ) : allowed.length > 0 ? (
          <p className="text-[11px] text-muted-foreground">
            This template supports {allowed.join(" and ")} ground.
          </p>
        ) : null}
      </div>
    </div>
  )
}
