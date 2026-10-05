/** Pure helpers for the runtime tuning panel.
 *
 *  Kept out of the component so the dirty-tracking rules (which decide what gets
 *  PUT to the server) are unit-testable without a DOM. */

export type SettingType = "int" | "float" | "bool"

export interface SettingSpec {
  value: unknown
  description: string
  type: SettingType
  min?: number
  max?: number
  step?: number
}

/** Normalize for comparison so `2` and `2.0` never read as an unsaved edit. */
export function canonical(value: unknown): unknown {
  if (typeof value === "number") return String(value)
  return value
}

/** Keys whose draft value differs from the server's current value. */
export function dirtyKeys(
  draft: Record<string, unknown>,
  values: Record<string, unknown>
): string[] {
  return Object.keys(draft).filter(
    (key) => !(key in values) || canonical(draft[key]) !== canonical(values[key])
  )
}

/** Build the PUT payload from the dirty keys.
 *
 *  A cleared numeric field is skipped rather than sent as `""` — the server
 *  rejects a non-numeric value, so an in-progress edit must not be mistaken for
 *  a real one. Returns null when nothing is actually sendable. */
export function buildPayload(
  draft: Record<string, unknown>,
  values: Record<string, unknown>
): Record<string, unknown> | null {
  const payload: Record<string, unknown> = {}
  for (const key of dirtyKeys(draft, values)) {
    const value = draft[key]
    if (value === "") continue
    payload[key] = value
  }
  return Object.keys(payload).length > 0 ? payload : null
}

/** Parse a number field's text into the knob's declared type.
 *
 *  Returns "" for an empty box so the draft records "cleared" rather than 0. */
export function parseNumericInput(raw: string, type: "int" | "float"): unknown {
  if (raw === "") return ""
  return type === "int" ? Number.parseInt(raw, 10) : Number(raw)
}

/** Group a dotted knob key for section headings ("verifier.max_retries" → "verifier"). */
export function knobGroup(key: string): string {
  const i = key.indexOf(".")
  return i === -1 ? "general" : key.slice(0, i)
}

/** Knob keys grouped in declaration order. */
export function groupKnobs(defaults: Record<string, SettingSpec>): [string, string[]][] {
  const byGroup = new Map<string, string[]>()
  for (const key of Object.keys(defaults)) {
    const group = knobGroup(key)
    const list = byGroup.get(group) ?? []
    list.push(key)
    byGroup.set(group, list)
  }
  return [...byGroup.entries()]
}
