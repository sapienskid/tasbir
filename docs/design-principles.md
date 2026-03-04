# Design Principles

Validated on March 4, 2026.

## 1. Configuration-first behavior

All defaults are centralized in `config/pipeline.config.yaml`:
- brand defaults
- feature flags
- model settings
- style taxonomy
- post archetypes
- slot schema
- format dimensions
- template registry

## 2. Template files over inline markup

All visual layouts live in `templates/**/*.html`.
Renderer code only handles selection, slot interpolation, and shared frame styling.

## 3. Archetype + style separation

Visual style (`template_style`) and content intent (`post_archetype`) are separate signals.
This enables one archetype (e.g., metric) to render in different visual styles (e.g., data or bold) without changing business logic.

## 4. Slot-based content contracts

Templates consume semantic slots (`headline`, `metric_value`, `quote_text`, `step_1`, etc.) instead of hardcoded field assumptions.
Slots are populated from model output, request overrides, and YAML defaults.

## 5. Deterministic Worker runtime

YAML + HTML are compiled at build time into `src/generated/template-assets.ts`.
Runtime never reads from filesystem, keeping rendering deterministic in Worker execution.
