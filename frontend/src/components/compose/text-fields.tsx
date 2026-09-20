import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { ComposeCopy } from "@/lib/api"
import { FIELD_META, getField, setField, type FieldKey } from "./model"

/**
 * Text tab: only the inputs the selected template actually renders, each
 * with a live counter against the backend cap.
 */
export function TextFields({
  fields,
  copy,
  hidden,
  fallback,
  onChange,
}: {
  fields: FieldKey[]
  copy: ComposeCopy
  hidden: string[]
  /** True when the template did not declare its fields (older backend). */
  fallback: boolean
  onChange: (copy: ComposeCopy) => void
}) {
  return (
    <div className="grid gap-3">
      {fallback ? (
        <p className="text-[11px] text-muted-foreground">
          This template doesn't list its text fields — showing the common ones.
        </p>
      ) : null}
      {fields.map((key) => {
        const meta = FIELD_META[key]
        const value = getField(copy, key)
        const id = `field-${key.replace(".", "-")}`
        const over = value.length > meta.cap
        const near = !over && value.length > meta.cap * 0.9
        const isHidden = hidden.includes(key)
        return (
          <div key={key} className="grid gap-1">
            <div className="flex items-baseline justify-between gap-2">
              <Label htmlFor={id} className="text-xs">
                {meta.label}
                {isHidden ? (
                  <span className="ml-1.5 font-normal text-muted-foreground">(hidden)</span>
                ) : null}
              </Label>
              <span
                id={`${id}-count`}
                className={`text-[10px] tabular-nums ${
                  over ? "text-destructive" : near ? "text-amber-600" : "text-muted-foreground"
                }`}
              >
                {value.length}/{meta.cap}
              </span>
            </div>
            {meta.multiline ? (
              <Textarea
                id={id}
                aria-describedby={`${id}-count`}
                aria-invalid={over || undefined}
                value={value}
                maxLength={meta.cap}
                className={key === "body" ? "min-h-32" : "min-h-16"}
                onChange={(e) => onChange(setField(copy, key, e.target.value))}
              />
            ) : (
              <Input
                id={id}
                aria-describedby={`${id}-count`}
                aria-invalid={over || undefined}
                value={value}
                maxLength={meta.cap}
                onChange={(e) => onChange(setField(copy, key, e.target.value))}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
