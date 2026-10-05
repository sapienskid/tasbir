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
import type { PlatformCreate } from "@/lib/api"

interface PlatformFormProps {
  value: PlatformCreate
  isNew: boolean
  /** Families from GET /api/settings/meta (backend-owned vocabulary). */
  families: string[]
  saving: boolean
  onChange: (v: PlatformCreate) => void
  onSave: () => void
  onDelete?: () => void
}

/** Simplest-whole-number ratio, for the read-only aspect hint. */
function aspectLabel(width: number, height: number): string {
  if (!width || !height) return "—"
  const gcd = (a: number, b: number): number => (b === 0 ? a : gcd(b, a % b))
  const g = gcd(width, height)
  return `${width / g}:${height / g}`
}

export function PlatformForm({
  value,
  isNew,
  families,
  saving,
  onChange,
  onSave,
  onDelete,
}: PlatformFormProps) {
  const set = <K extends keyof PlatformCreate>(key: K, v: PlatformCreate[K]) =>
    onChange({ ...value, [key]: v })

  return (
    <div className="grid gap-3">
      <div className="grid gap-1.5">
        <Label htmlFor="plat-id">ID</Label>
        <Input
          id="plat-id"
          value={value.id}
          disabled={!isNew}
          placeholder="instagram-story"
          onChange={(e) => set("id", e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          Lowercase letters, digits and dashes. Changing it renames the format key used by
          templates and jobs, so it is fixed once created.
        </p>
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="plat-name">Name</Label>
        <Input
          id="plat-name"
          value={value.name}
          placeholder="Instagram Story"
          onChange={(e) => set("name", e.target.value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor="plat-width">Width</Label>
          <Input
            id="plat-width"
            type="number"
            min={16}
            max={8192}
            value={value.width}
            onChange={(e) => set("width", Number(e.target.value) || 1080)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="plat-height">Height</Label>
          <Input
            id="plat-height"
            type="number"
            min={16}
            max={8192}
            value={value.height}
            onChange={(e) => set("height", Number(e.target.value) || 1080)}
          />
        </div>
      </div>
      <p className="-mt-1 text-xs text-muted-foreground">
        Aspect ratio {aspectLabel(value.width, value.height)}. This size drives every render and
        template preview for the family.
      </p>

      <div className="grid grid-cols-2 gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor="plat-family">Family</Label>
          <Select value={value.family} onValueChange={(v) => set("family", v)}>
            <SelectTrigger id="plat-family">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {families.map((f) => (
                <SelectItem key={f} value={f}>
                  {f}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="plat-sort">Sort order</Label>
          <Input
            id="plat-sort"
            type="number"
            value={value.sort_order}
            onChange={(e) => set("sort_order", Number(e.target.value) || 0)}
          />
        </div>
      </div>
      <p className="-mt-1 text-xs text-muted-foreground">
        The first active platform in a family sets that family&apos;s preview canvas.
      </p>

      <div className="flex items-center gap-2">
        <Checkbox
          id="plat-active"
          checked={value.is_active}
          onCheckedChange={(v) => set("is_active", v === true)}
        />
        <Label htmlFor="plat-active">Active</Label>
      </div>

      <div className="flex justify-between gap-2 pt-1">
        {onDelete ? (
          <ConfirmAction
            trigger={
              <Button variant="destructive" size="sm" disabled={saving}>
                Delete
              </Button>
            }
            title={`Delete ${value.id}?`}
            description={
              <>
                Templates and jobs reference this platform id. Deleting it will make them fall back
                to auto-selection, and the family falls back to its default canvas if no other
                platform in it stays active.
              </>
            }
            onConfirm={onDelete}
          />
        ) : (
          <span />
        )}
        <Button size="sm" onClick={onSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  )
}
