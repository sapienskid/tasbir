# ADR-0007 — Ephemeral Artifact Delivery (Serve-and-Delete + TTL Sweep)

- Status: accepted
- Date: 2026-08-01
- Related: ADR-0008 (trust boundary), ADR-0009 (SSRF policy)

## Context

Generated artifacts (per-format HTML + PNG) were written to
`data/output/{task_id}/` and surfaced to callers only as server-local paths
in the task result. There was no HTTP endpoint to fetch them, so n8n/UI had
to read the bind-mounted volume. Simply adding plain file-serve endpoints
would accumulate PNGs (multi-MB each) on the server forever — the operator
explicitly rejected that.

## Decision

- `GET /tasks/{id}/files` lists remaining artifacts.
- `GET /tasks/{id}/files/{filename}` streams a file then **deletes it**
  (one-time download; a second request returns 404).
- A Celery beat task (`retention.sweep_expired`, hourly) removes any output
  directory older than `OUTPUT_TTL_HOURS` (default 24) and purges the
  matching SQLite rows so neither disk nor DB can grow unbounded.
- `DELETE /tasks/{id}` removes the output directory too.
- The Tasbir Studio UI fetches HTML/PNG once and holds them in-memory
  (per-format `Map` caches), re-rendering regenerates files when needed.

Files are the store, delivery is consuming. No object storage was added —
v2 removed MinIO specifically for this bloat.

## Consequences

- Disk footprint is bounded by the retention window, not by usage.
- Consumers must download within the window; the UI handles this by caching.
- The UI re-render flow re-creates artifacts, so edits never get lost.
- Task rows disappear after the window (404 on `GET /tasks/{id}`), which is
  fine because n8n polls until completion and downloads promptly.
