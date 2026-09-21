# ADR-0023 — Structured editor: instant preview, editor state, hardened refill

Status: accepted
Date: 2026-09-21

## Context

The structured (AI-post) editor introduced with `POST …/refill` did one slow
round trip per edit — fill, hard checks, a Playwright PNG render, persist —
and returned no document, so the client refetched. It also lost edits when two
requests overlapped (both read the same base HTML, last writer won), wrote
files non-atomically, forgot toggles / media position / media kind on reload,
shared one rate bucket with generation (an instant editor would 429 itself),
and treated designer-LLM posts as read-only.

## Decision

- **One fill routine.** `_build_refill` (api/tasks.py) validates a structured
  edit and produces the finalized document; it writes nothing. `refill/preview`
  returns it directly (no PNG, no checks, no DB/file writes, no render call);
  `refill` runs the same routine then checks/renders/persists, so preview ==
  what is saved. Big inline base64 payloads are hoisted to tokens for the
  structural passes (`services/html_payloads.py`) — the reason preview stays
  fast on posts with an uploaded photo.
- **Serialized, atomic persist.** A refcounted per-(task, format) lock
  (`core/keylock.py`) covers read-latest → build → check → render → write →
  DB, so concurrent edits of different slots merge. Files are written via temp
  file + `os.replace`, then one DB statement updates `result` + `edited_html`
  inside a short per-task lock on a freshly-read row (carousel slides share
  those JSON columns). `rerender` shares the same lock and persist. A PNG or
  check failure never loses the HTML.
- **Editor state.** `GET …/editor` plus `result.platforms[fmt].editor =
  {hidden, media_position, media_kind, media, revision}` (never base64; an
  illustration keeps style + seed so a later toggle re-draws the same figure).
  `revision` is +1 per persist; refill returns `html`, `revision`, `saved_at`.
  A slot hidden by a toggle keeps its text in the stored copy.
- **Designer → template conversion.** `template_id` on a post that has none
  fills the template from the stored copy JSON; the original document is kept
  as `{fmt}.designer.html` (excluded from the files list) and `converted: true`.
- **Rate-limit tiers.** Endpoints tagged `@interactive` (compose preview /
  illustration / photos, refill preview, refill, editor GET) count against
  `rl:interactive:<key>` (`RATE_LIMIT_INTERACTIVE_PER_MIN`, default 600); the
  router-level limiter reads the tag, so a request is charged to one bucket.
  Redis-down still fails open.

## Consequences

- Preview ≈ 10–20 ms server-side (≈ 50–90 ms with a 2 MB image); persisting
  stays multi-second because the PNG + checks go through the render service,
  which the client now does in the background.
- The lock is in-process: correct for the single-worker API (`--workers 1`);
  multiple API workers would need a DB/Redis lock.
- A raw-HTML `rerender` resets the remembered toggles/media (they are unknown
  after arbitrary HTML edits). The designer backup is file-only and follows the
  artifact TTL.
