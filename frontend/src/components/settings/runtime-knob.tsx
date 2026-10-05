import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { parseNumericInput, type SettingSpec } from "@/lib/settings-knobs"

interface RuntimeKnobProps {
  name: string
  spec: SettingSpec
  /** The server's current value for this knob. */
  serverValue: unknown
  /** The operator's pending edit, or undefined when untouched. */
  draftValue: unknown
  dirty: boolean
  onDraft: (value: unknown) => void
  onRevert: () => void
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return ""
  return String(value)
}

/** One runtime setting.
 *
 *  The control is chosen from the server's declared `type` — this component has
 *  no knowledge of individual knobs. That is what makes a boolean knob a real
 *  checkbox instead of a number input coercing `true` to `1`.
 */
export function RuntimeKnob({
  name,
  spec,
  serverValue,
  draftValue,
  dirty,
  onDraft,
  onRevert,
}: RuntimeKnobProps) {
  const value = dirty ? draftValue : serverValue
  const inputId = `knob-${name}`

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_180px] items-start gap-4 border-b py-3 last:border-b-0">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Label htmlFor={inputId} className="font-mono text-xs">
            {name}
          </Label>
          {dirty ? (
            <>
              <span
                aria-hidden="true"
                className="size-1.5 rounded-full bg-amber-500"
                title="Unsaved change"
              />
              <span className="sr-only">Unsaved change</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-1.5 text-xs"
                onClick={onRevert}
              >
                Revert
              </Button>
            </>
          ) : null}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{spec.description}</p>
        {dirty ? (
          <p className="mt-0.5 font-mono text-xs text-muted-foreground">
            {displayValue(serverValue)} → {displayValue(draftValue)}
          </p>
        ) : null}
      </div>

      <div className="flex items-center justify-end gap-2">
        {spec.type === "bool" ? (
          <div className="flex items-center gap-2">
            <Checkbox
              id={inputId}
              checked={value === true}
              onCheckedChange={(v) => onDraft(v === true)}
            />
            <span className="text-sm text-muted-foreground">{value === true ? "on" : "off"}</span>
          </div>
        ) : (
          <Input
            id={inputId}
            type="number"
            className="w-32"
            min={spec.min}
            max={spec.max}
            step={spec.step ?? (spec.type === "int" ? 1 : "any")}
            value={displayValue(value)}
            aria-label={name}
            onChange={(e) => {
              // This branch only renders for numeric knobs (bool uses a Checkbox).
              onDraft(parseNumericInput(e.target.value, spec.type as "int" | "float"))
            }}
          />
        )}
      </div>
    </div>
  )
}
