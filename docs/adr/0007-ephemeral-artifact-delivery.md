# ADR-0007 — Artifact Delivery and Retention (Persist-until-TTL)

- Status: accepted (updated 2026-08-02)
- Related: ADR-0008 (trust boundary), ADR-0009 (SSRF policy)

## Context

Generated artifacts (per-format HTML + PNG) are written to
`data/output/{task_id}/`. The original model deleted a file immediately after
it was served (one-time download). The operator rejected that: downloads must
be repeatable within a retention window, and cleanup should be time-based.

## Decision

- `GET /tasks/{id}/files` lists available artifacts.
- `GET /tasks/{id}/files/{filename}` streams a file and **keeps it**; a second
  download succeeds. `?consume=true` opts into delete-after-delivery
  (one-time download). The `DELETE_ON_DOWNLOAD` env flips the global default.
- A Celery beat task (`retention.sweep_expired`, hourly) removes any output
  directory older than `OUTPUT_TTL_HOURS` (default 24) and purges the matching
  SQLite rows, bounding disk and DB growth.
- `DELETE /tasks/{id}` removes the output directory too.

Files are the store; the TTL sweep is the cleanup. Downloading is
non-destructive unless the consumer explicitly asks.

## Consequences

- Downloads and "Save as Template" work repeatedly within the window (the
  promote flow reads the HTML from disk, which no longer disappears on fetch).
- Disk footprint is bounded by the retention window, not by download count.
- The one-time behavior remains available on demand (`?consume=true`).
