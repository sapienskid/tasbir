# Design Principles

Validated on March 4, 2026.

These principles define how this system should evolve.

## 1. Templates Are Structure, CSS Is Design

- `templates/*.html` define layout skeletons and slot contracts.
- `src/styles/template.css` is the visual source of truth.
- avoid scattering design logic across TypeScript files.

## 2. One Design System, Token-Driven

- use semantic token aliases (`--token-*`, `--color-*`, `--radius-*`)
- keep typography, spacing, color, and radii centrally controlled
- avoid per-template hardcoded visual systems

## 3. Runtime Must Be Template-Driven

- template requirements come from actual `{{SLOT:key}}` placeholders
- LLM content generation must satisfy selected template slot requirements
- avoid hardcoded post archetype/style taxonomies

## 4. Dynamic Template Registry

- templates are discovered from `templates.yaml`
- adding a template should not require runtime code edits
- selection should stay valid even as template set changes frequently

## 5. Clear Separation of Concerns

- config controls behavior and limits
- templates control structure
- CSS controls visuals
- TypeScript orchestrates and validates

## 6. Deterministic Build Output

- runtime should not read filesystem templates directly
- compile config/templates/CSS into generated assets at build time
- fail early on invalid template registry references

## 7. Explicit Override Precedence

When multiple value sources exist, precedence must remain deterministic.

Typical pattern:

1. request overrides
2. model output
3. config defaults
4. code fallbacks

## 8. Safe Fallbacks

Even with imperfect model output, rendering should succeed:

- normalize captions and slides
- infer missing slot values
- fallback template and image paths
- enforce bounded lengths

## 9. Extend by Adding, Not Rewriting

Preferred extension path:

1. add/update template
2. register in YAML
3. adjust CSS tokens/classes if needed
4. rebuild assets
5. verify via preview and generation routes

## 10. Documentation Is Part of the System

Architecture/API/config docs must be updated with each structural change.
Outdated docs create incorrect integrations faster than code bugs.
