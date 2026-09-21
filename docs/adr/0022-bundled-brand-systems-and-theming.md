# ADR-0022 — Bundled brand design systems, brand languages and template theming

Status: accepted
Date: 2026-09-21

## Context

Design languages (ADR-0020) recoloured Swiss layouts and little else: measured
across all five languages the templates never referenced `--color-accent`,
`--shadow-*` (radius once) and hard-coded font weights, and the LLM designer
treated the accent rule as optional. A brand system (logo, fonts, palette,
accent, rules) therefore could not show up in output. New design systems also
started with the Swiss language pre-selected and zero templates.

## Decision

- **Bundled brand systems.** `data/design_system/bundled/<id>/system.yaml`
  (+ logo files) seeds Fundaments.work and Theorem on first boot
  (`seeding.sync_bundled_design_systems`): the system, its own **brand design
  language** (a custom `design_languages` row, source `bundled`), and its own
  copy of the standard layouts (`<id>-<template>`). Seed-owned rows are
  refreshed from the files on restart; a Studio edit is never overwritten; a
  deleted system is not resurrected (marker in `app_settings`, filtered out of
  the Studio's settings).
- **Brand languages, not borrowed presets.** Each bundled system points at its
  own language (`fundaments`, `theorem`): palette + accent tokens, rules,
  layout archetypes, media policy. Fonts stay on the system (language rule).
- **Template theming.** Templates get `has_accent` (Jinja) and put accent
  devices — fills, rules, highlight chips behind ink text, never text colour —
  inside `{% if has_accent %}`, so accent-less output is unchanged. Radius,
  shadow and headline weight follow tokens (`--radius-*`, `--shadow-md`,
  `--font-weight-display`).
- **Designer gate.** An LLM-designed post in an accent language must reference
  `var(--color-accent…)`; the verifier fails it with a critique otherwise, and
  the rules block says "REQUIRED". Template posts are exempt.
- **Logos.** A design-system logo may carry per-ground variants
  (`logo.grounds.{white,black}`); `DSContext.logo_for(ground)` /
  `pick_logo` resolve it, and `substitute_logo` never overwrites a logo a
  template already baked in. Templates render the logo when present.
- **New design systems start empty of language** (`style_language: ""`, no
  accent/archetypes) but get their own user-owned copy of the standard layouts.

## Consequences

- Switching design system in Compose remaps templates by layout tags and
  changes palette, fonts, weight, accent and logo together.
- Design-instruction `spacing` and `type_scale.roles` still only steer the LLM
  designer; template layouts use fixed proportional spacing.
- Reversed logo variants that the brand does not publish (Theorem on the
  inverted ground) are derived by recolouring the official mark.
