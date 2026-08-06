// Auto-derive togglable elements from a template's Jinja `{% if %}` conditions.
// Mirrors backend `detect_elements` (app/services/templates.py). A toggle exists
// for every content var the template conditions on; structural/comparison
// conditions (ground/variant/loops/not/in) are skipped.

export interface TemplateElement {
  name: string
  label: string
}

const IF_RE = /\{%-?\s*(?:if|elif)\s+([^%]+?)\s*-?%\}/g
const TOKEN_RE = /[A-Za-z_][A-Za-z0-9_.]*/g
// Conditions that compare, negate, loop, or call — not element toggles.
const SKIP_IF = /==|!=|<=|>=|\bnot\b|\bin\b|\bfor\b|\(|%/
const STRUCT_VARS = new Set([
  "ground",
  "variant",
  "loop",
  "loop_index",
  "slide_index",
  "slide_total",
  "range",
])
const BOOL_WORDS = new Set(["or", "and", "not", "in", "is", "true", "false"])
// Elements that are mandatory and must never be hideable — the verifier
// hard-fails a design missing the footer handle.
const MANDATORY = new Set(["footer_right"])

const LABELS: Record<string, string> = {
  kicker: "Category / kicker",
  headline: "Headline",
  subhead: "Subhead",
  body: "Body",
  tagline: "Tagline",
  badge: "Badge",
  meta: "Meta line",
  footer_left: "Footer (left)",
  footer_right: "Footer handle",
  has_image: "Image",
  logo: "Logo",
  illustration: "Illustration",
  "extra.cta": "CTA",
  "extra.price": "Price",
  "extra.date": "Date",
  "extra.location": "Location",
  "extra.stat": "Stat",
  "extra.source": "Source",
}

export function detectTemplateElements(html: string): TemplateElement[] {
  const names = new Set<string>()
  for (const m of html.matchAll(IF_RE)) {
    const cond = m[1]
    if (SKIP_IF.test(cond)) continue
    for (const tok of cond.matchAll(TOKEN_RE)) {
      const name = tok[0]
      if (STRUCT_VARS.has(name) || BOOL_WORDS.has(name) || MANDATORY.has(name)) continue
      names.add(name)
    }
  }
  return [...names].map((name) => ({
    name,
    label: LABELS[name] ?? name,
  }))
}
