import { useMemo, useState } from "react"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { ConfirmAction } from "@/components/settings/confirm-action"
import type { PoolFontCreate } from "@/lib/api"

interface FontFormProps {
  value: PoolFontCreate
  isNew: boolean
  /** Roles from GET /api/settings/meta (backend-owned vocabulary). */
  roles: string[]
  saving: boolean
  onChange: (v: PoolFontCreate) => void
  onSave: () => void
  onDelete?: () => void
}

/** "400, 700" → [400, 700]; returns an error for anything unparseable so the
 *  operator sees the problem instead of it being silently dropped. */
function parseWeights(raw: string): { weights: number[]; error: string | null } {
  const parts = raw
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean)
  if (parts.length === 0) return { weights: [], error: "Enter at least one weight" }
  const weights: number[] = []
  for (const p of parts) {
    const n = Number(p)
    if (!Number.isInteger(n) || n < 1 || n > 1000) {
      return { weights: [], error: `"${p}" is not a valid weight (100–900 are typical)` }
    }
    weights.push(n)
  }
  return { weights, error: null }
}

export function FontForm({
  value,
  isNew,
  roles,
  saving,
  onChange,
  onSave,
  onDelete,
}: FontFormProps) {
  const [weightsText, setWeightsText] = useState(value.weights.join(", "))
  const parsed = useMemo(() => parseWeights(weightsText), [weightsText])
  const set = <K extends keyof PoolFontCreate>(key: K, v: PoolFontCreate[K]) =>
    onChange({ ...value, [key]: v })

  return (
    <div className="grid gap-3">
      <div className="grid gap-1.5">
        <Label htmlFor="font-family">Family</Label>
        <Input
          id="font-family"
          value={value.family}
          disabled={!isNew}
          placeholder="Space Grotesk"
          onChange={(e) => set("family", e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          Must match the Google Fonts family name exactly — it is used to build the font link.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor="font-role">Role</Label>
          <Select value={value.role} onValueChange={(v) => set("role", v)}>
            <SelectTrigger id="font-role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {roles.map((r) => (
                <SelectItem key={r} value={r}>
                  {r}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="font-sort">Sort order</Label>
          <Input
            id="font-sort"
            type="number"
            value={value.sort_order}
            onChange={(e) => set("sort_order", Number(e.target.value) || 0)}
          />
        </div>
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="font-weights">Weights</Label>
        <Input
          id="font-weights"
          value={weightsText}
          placeholder="400, 700"
          aria-invalid={parsed.error ? true : undefined}
          aria-describedby={parsed.error ? "font-weights-error" : undefined}
          onChange={(e) => {
            setWeightsText(e.target.value)
            const next = parseWeights(e.target.value)
            if (!next.error) set("weights", next.weights)
          }}
        />
        {parsed.error ? (
          <p id="font-weights-error" className="text-xs text-destructive">
            {parsed.error}
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            Comma-separated. These are the weights the font link requests.
          </p>
        )}
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="font-style">Style</Label>
        <Input
          id="font-style"
          value={value.style}
          placeholder="normal"
          onChange={(e) => set("style", e.target.value)}
        />
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id="font-active"
          checked={value.is_active}
          onCheckedChange={(v) => set("is_active", v === true)}
        />
        <Label htmlFor="font-active">Active</Label>
      </div>
      <p className="-mt-1 text-xs text-muted-foreground">
        Only active families are offered to the brand builder and the font picker.
      </p>

      <div className="flex justify-between gap-2 pt-1">
        {onDelete ? (
          <ConfirmAction
            trigger={
              <Button variant="destructive" size="sm" disabled={saving}>
                Delete
              </Button>
            }
            title={`Delete ${value.family}?`}
            description={
              <>
                Design systems already using this family keep their token value and will fall back
                to their next stack entry. It will no longer be offered to the brand builder.
              </>
            }
            onConfirm={onDelete}
          />
        ) : (
          <span />
        )}
        <Button size="sm" onClick={onSave} disabled={saving || Boolean(parsed.error)}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  )
}
