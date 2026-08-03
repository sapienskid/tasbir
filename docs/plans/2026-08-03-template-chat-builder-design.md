# Task-based Agent Jobs + One-shot Template Build

## Motivation

Template creation (from-image) and the brand builder were modal-dialog flows whose
job tracking lived in dialog/page state — close the dialog or navigate away and the
job disappeared from view. Template creation was also image-only.

Goal, per the user:
1. Template creation and the brand builder become **task-based**: jobs survive closing
   the dialog, are listed persistently, and stay reachable from the Tasks page.
2. Template creation accepts **context** — an **image**, **HTML**, or a **text
   description** — but stays a **one-shot background build** (old-style dialog +
   inline job status), NOT a chat conversation.

An early chat-inbox prototype was rejected by the user ("weird"); the chat thread was
removed in favor of a single validated-template result per job.

Decisions confirmed with the user:
- Agent jobs are **merged into the Tasks page** (one list, type badges).
- Template creation is a **form dialog with three context tabs** (Describe / Image /
  HTML) + ratio/ground, submitting a **background job** that authors → validates →
  **saves a template directly**. No conversational refinement.
- Brand builder keeps its existing form; it only gains **task-based tracking**.

## Reused infrastructure

- `AgentJob` rows (kind, status, result, error) — persistent, no schema change.
- `services/template_author.py` — `author_template_html(...)`, `build_layout_spec(...)`,
  `validate_template_html(...)` (render sample copy + overflow + deterministic QC),
  `FAMILY_DIMS`, `clean_html`, `repair_jinja`.
- `template_author` agent config (Studio-editable) drives authorship.
- `POST /templates` create endpoint reused for validation-gated saves.

## Part 1 — Task-based job tracking

### Backend
- `GET /agent-jobs?kind=&limit=` — list agent jobs newest-first:
  `{id, kind, status, result, error, created_at, updated_at, title}` where `title` is
  derived from `result.template_id` / `result.design_system_id` / a friendly default.
- `DELETE /agent-jobs/{id}` — remove a job row (mirrors task delete).
- `AgentJobRepository.list_recent(limit, kind)` + `delete(id)`.

### Frontend
- Tasks page is a merged list: generation tasks + agent jobs, sorted by `created_at`
  desc, with a **Type** badge (`Post` / `Template` / `Design system`). Post rows route
  to `/tasks/{id}`; job rows to `/jobs/{id}`. Delete works for both.
- New route `/jobs/:jobId` → `JobDetailPage`:
  - kind `template` → status card; on completion shows the created `template_id` and an
    **Open template** button (`/templates?open={id}` opens the edit dialog).
  - kind `design_system` → status + created-system link (`/design-systems?ds=`).

## Part 2 — One-shot template build (image / HTML / text)

### Endpoint
`POST /templates/from-input` (multipart):
`design_system_id`, optional `message` (text brief), `html` (pasted markup), `family`,
`ground`, `file` (mockup image). Requires at least one of image / html / message.

Creates an `AgentJob` (kind `template`) with the seed in `job.payload` and dispatches
the Celery task `run_template_build_task`.

### Celery task `run_template_build_task`
- Resolves the design system; defaults family/ground from payload.
- Builds the author spec:
  - image → `build_layout_spec(image)` (vision), family/ground override accepted;
  - text → `{family, ground, layout_description: message}`;
  - html → `{family, ground, layout_description: "convert the provided HTML"}`,
    passing the pasted markup via `author_template_html(source_html=...)` so the
    author converts rather than rewrites from scratch.
- Authors → `validate_template_html` (render + overflow + deterministic QC), retrying
  with critique up to 2 extra attempts.
- On success, saves a `Template` row (`source="ai"`) and marks the job `completed`
  with `result.template_id`. On failure, `failed` with the validation issues.

### Frontend dialog (`CreateTemplateDialog`, old-style)
- Tabs: **Describe** (textarea) / **Image** (dropzone) / **HTML** (paste) + ratio/ground.
- Submit → `createTemplateBuild(...)` → dialog switches to an **inline job-status view**
  (status badge, spinner while running, `template_id` when done, error on failure,
  **Done** button). Closing the dialog never kills the job — it stays on the Tasks page.

## Malformed-Jinja repair (`repair_jinja`)

LLMs occasionally fuse a block-close `%}` with a following `>`/`}}`, e.g.
`{% endif %>` instead of `{% endif %}`, which makes `Environment.parse` raise
`expected token 'end of statement block', got '%'`. `repair_jinja(html)` rewrites
those fused closes for known Jinja keywords (leaving CSS/JS `%>` alone) and runs as
part of `clean_html`, so authored drafts parse and render.

## Data flow

```
POST /templates/from-input ──> AgentJob(kind=template) + dispatch
        │
        ▼
   Celery run_template_build_task
      │  spec ← image | text | html(source_html)
      ▼
   author_template_html ──> validate_template_html (retry ×2 on critique)
        │
        ├─ ok  ──> save Template row ──> job completed{template_id}
        └─ bad ──> job failed{validation issues}
        ▲
   UI polls GET /agent-jobs/{id} (dialog inline + Tasks list)
```

## Error handling

- Missing design system / empty input → 422 at creation.
- Validation failure → job `failed` with issues (no half-saved template).
- LLM empty output → job `failed` with a clear message.
- Template id collision → suffix increment (e.g. `-2`) before save.

## Testing

- Backend: pytest for `GET /agent-jobs` (list/filter/delete/title), `POST
  /templates/from-input` (image/html/text dispatch + validation guards), and
  `repair_jinja` regression cases.
- Frontend: `npm run typecheck` + `npm run build`.

## Out of scope (YAGNI)

- Conversational template refinement (chat removed per user).
- Brand builder chat — tracking only.
- Auto-expiry of agent-job rows (kept indefinitely; rows are small).
