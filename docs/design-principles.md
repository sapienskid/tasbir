# Design Principles

Validated on March 4, 2026.

These principles explain how the project is intended to evolve.

## 1. Config First, Code Second

Behavior should be controlled through config fragments (`config/pipeline/templates.yaml`, `config/pipeline/content.yaml`, `config/pipeline/runtime.yaml`) whenever possible.

Examples:

- adding archetypes
- changing default styles/fonts
- adjusting generation limits
- changing output dimensions

Only add TypeScript logic when config cannot express the requirement.

## 2. Templates Are Product Surface Area

All visual layout lives in `templates/**/*.html`.

Renderer code should remain generic:

- select template
- resolve tokens and slots
- apply design system
- render output

Avoid creating format-specific custom renderer branches.

## 3. Style and Intent Are Separate Axes

- style = how it looks (`template_style`)
- archetype = what kind of message it is (`post_archetype`)

Keeping these independent allows one intent to be rendered in multiple visual languages.

## 4. Slot Contracts Over Hardcoded Fields

Templates should use semantic slots (`headline`, `quote_text`, `metric_value`, etc.) so content can adapt across layouts.

Use slot defaults in config and let model/output overrides refine values.

## 5. Deterministic Runtime

Worker should not read filesystem assets at runtime.

All config/templates are compiled into `src/generated/template-assets.ts` during build. This keeps runtime behavior deterministic and deploy-friendly.

## 6. Safe Fallbacks Everywhere

Pipeline should continue producing usable output when model fields are missing.

Fallback strategy includes:

- caption truncation
- slide count enforcement
- slot defaults
- template/style/archetype defaults
- image source fallback chain

## 7. Explicit Override Precedence

When multiple sources provide values, precedence is deterministic and documented.

Typical precedence pattern:

1. request payload
2. model output
3. config defaults

This keeps behavior predictable for automation and manual use.

## 8. One Build Step Validates Everything

`pnpm run build:templates` should fail fast for config/template inconsistencies.

A broken template registry must be caught before deploy.

## 9. Observability-Friendly APIs

Responses include normalized `llm_output`, selected image source, and asset keys so callers can inspect actual decisions made by the pipeline.

## 10. Extend by Adding, Not Rewriting

Preferred extension path:

1. add config entries
2. add templates
3. rebuild assets
4. test via preview and generation routes

This keeps long-term maintenance simple and prevents renderer sprawl.
