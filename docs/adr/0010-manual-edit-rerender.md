# ADR-0010 — Manual Edit / Re-render Flow (Skip the Designer LLM)

- Status: accepted
- Date: 2026-08-01
- Related: ADR-0007 (ephemeral delivery)

## Context

The pipeline's QC loop (deterministic checks + vision audit) drives the
designer LLM to fix issues, but an operator reviewing a render often knows
exactly what to fix (a typo, a cramped footer, a wrong margin). Running the
designer LLM again on a human-approved edit wastes quota and can regress the
design. There was also no UI to view or edit the generated HTML.

## Decision

Add an operator-facing re-render path that **skips the designer LLM**:

- `POST /tasks/{id}/formats/{fmt_id}/rerender` takes the edited HTML document,
  sanitizes it (preserving the system-injected KaTeX/font CDN resources),
  re-injects tokens/fonts/KaTeX/images, renders the PNG, runs the
  deterministic checks + overflow detection, and returns
  `{png_b64, quality}`.
- The vision audit runs **only on demand** (`?audit=true`) so interactive
  edits never silently burn the free-tier vision quota.
- The rerender persists fresh HTML/PNG into the task output directory and
  reflects the QC result back in the task's stored result.

Delivered through **Tasbir Studio**, a React + Vite + shadcn/ui SPA served
same-origin by FastAPI (Monaco editor for HTML, live PNG preview, QC report,
downloads, delete). The UI caches artifacts in-memory to respect the
serve-and-delete delivery model (ADR-0007).

## Consequences

- Human edits produce deterministic renders with zero LLM cost; AI regen
  remains available by re-running a full generation or the opt-in audit.
- Interactive editing no longer triggers retry loops.
- The editor is a heavy dependency (Monaco) but is lazy-loaded, so it never
  affects the entry bundle.
