import { describe, expect, it } from "vitest"
import {
  buildPayload,
  canonical,
  dirtyKeys,
  groupKnobs,
  knobGroup,
  parseNumericInput,
  type SettingSpec,
} from "../settings-knobs"

function spec(over: Partial<SettingSpec> = {}): SettingSpec {
  return { value: 0, description: "d", type: "int", ...over }
}

describe("canonical", () => {
  it("treats 2 and 2.0 as the same value", () => {
    expect(canonical(2)).toBe(canonical(2.0))
    expect(canonical(2)).not.toBe(canonical(3))
  })

  it("leaves booleans and strings alone", () => {
    expect(canonical(true)).toBe(true)
    expect(canonical("x")).toBe("x")
  })
})

describe("dirtyKeys", () => {
  const values = { "verifier.max_retries": 3, "publish.enabled": true }

  it("is empty when the draft matches", () => {
    expect(dirtyKeys({ "verifier.max_retries": 3, "publish.enabled": true }, values)).toEqual([])
  })

  it("flags a genuinely changed number", () => {
    expect(dirtyKeys({ "verifier.max_retries": 5 }, values)).toEqual(["verifier.max_retries"])
  })

  it("flags a boolean flip", () => {
    expect(dirtyKeys({ "publish.enabled": false }, values)).toEqual(["publish.enabled"])
  })

  it("does not flag 2 versus 2.0", () => {
    expect(dirtyKeys({ "verifier.max_retries": 3.0 }, values)).toEqual([])
  })

  it("flags a reverted value as clean again", () => {
    expect(dirtyKeys({ "verifier.max_retries": 3 }, values)).toEqual([])
  })
})

describe("buildPayload", () => {
  const values = { "verifier.max_retries": 3, "publish.enabled": true }

  it("returns null when nothing changed", () => {
    expect(buildPayload({}, values)).toBeNull()
  })

  it("only includes changed keys", () => {
    expect(
      buildPayload({ "verifier.max_retries": 3, "publish.enabled": false }, values)
    ).toEqual({ "publish.enabled": false })
  })

  it("skips a cleared numeric field rather than sending an empty string", () => {
    // The server rejects non-numeric values, so an in-progress clear is dropped.
    expect(buildPayload({ "verifier.max_retries": "" }, values)).toBeNull()
  })

  it("still sends the real edits alongside a cleared one", () => {
    expect(
      buildPayload({ "verifier.max_retries": "", "publish.enabled": false }, values)
    ).toEqual({ "publish.enabled": false })
  })
})

describe("parseNumericInput", () => {
  it("returns the empty marker for a cleared box, not 0", () => {
    expect(parseNumericInput("", "int")).toBe("")
    expect(parseNumericInput("", "float")).toBe("")
  })

  it("parses ints without keeping a fraction", () => {
    expect(parseNumericInput("5", "int")).toBe(5)
    expect(parseNumericInput("5.9", "int")).toBe(5)
  })

  it("keeps fractions for floats", () => {
    expect(parseNumericInput("2.5", "float")).toBe(2.5)
  })
})

describe("knobGroup / groupKnobs", () => {
  it("splits a dotted key", () => {
    expect(knobGroup("verifier.max_retries")).toBe("verifier")
  })

  it("falls back to 'general' for an undotted key", () => {
    expect(knobGroup("flag")).toBe("general")
  })

  it("groups knobs in declaration order", () => {
    const defaults = {
      "verifier.max_retries": spec(),
      "copywriter.concurrency": spec(),
      "verifier.clef_first": spec({ type: "bool", value: true }),
    }
    expect(groupKnobs(defaults)).toEqual([
      ["verifier", ["verifier.max_retries", "verifier.clef_first"]],
      ["copywriter", ["copywriter.concurrency"]],
    ])
  })
})
