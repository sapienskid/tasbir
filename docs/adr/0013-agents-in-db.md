# ADR-0013: Agent configuration moves to the database

**Status:** Accepted · **Date:** v3.5

## Context
Agent personas, system prompts, LLM model selection, temperature, and
max_tokens lived in two disconnected places: YAML prompt files
(`config/prompts/*.yaml`) and the hardcoded `MODEL_ROUTES` dict in
`services/llm.py`. Editing required a worker restart (the `lru_cache` on the
YAML loader), and prompt text was not versioned or inspectable. Worse, the
four pipeline prompts hardcoded design-system content — category labels, the
three type voices, the Swiss audit rubric — duplicating (and drifting from)
what the nodes already inject dynamically from the design-system rows.

This is a deliberate re-inversion of the v2 → v3 change that moved prompts
out of DB tables into YAML (see `PLAN.md`), now done in the same style as
ADR-0012 (design systems + templates → DB).

## Decision
- **`agents` table** — global, shared, keyed by the role name (the string
  used everywhere as `agent_role`): `persona`, `role`, `system_prompt`,
  `model`, `temperature`, `max_tokens`, `source` (`seed`|`manual`),
  `is_active`. Covers all ten roles (strategist, copywriter, designer,
  verifier, editor_chat, brand_vision, brand_tokens, brand_campaigns,
  template_vision, template_author). Single editable row — no versioning.
- **Runtime loader** (`services/agents.py`): `get_agent_config(name)` resolves
  **DB row → YAML seed → hardcoded fallback**, with a ~5s TTL cache and
  `invalidate_agent_config()` on update so edits apply without a worker
  restart. `resolve_model(role)` feeds `llm.py` so every LLM path (pipeline,
  brand builder, template author, editor chat, OpenRouter fallback) honors
  the DB model; `MODEL_ROUTES` remains the fallback default.
- **Seeding**: YAML prompt files seed first boot only (idempotent). There is
  deliberately **no boot reconcile** (unlike design systems) so a YAML edit
  never clobbers a Studio edit; restore via `POST /api/agents/{name}/reset`.
- **Automatic prompts**: design-system-specific content is no longer written
  into the system prompts. The prompts reference the blocks the nodes already
  inject — approved categories, the design-instruction block + CSS variables
  (via `{TEMPLATE_CONTEXT}`), footer/ground/category blocks, and the verifier's
  design-system specification. Prompts are now portable across design systems.
- **API**: `GET /api/agents`, `GET /api/agents/{name}`, `PUT /api/agents/{name}`,
  `POST /api/agents/{name}/reset`, `GET /api/agents/graph` (topology +
  enrichment), `POST /api/agents/{name}/prompt-preview` (assembled
  system + user prompt for a representative sample post).
- **Studio**: new top-level **Agents** page — React Flow (`@xyflow/react` +
  `@dagrejs/dagre`) pipeline graph (expandable per-format sub-flow) plus
  Support-agent lanes (Brand Builder, Template Author, Editor Chat), with a
  config inspector (Monaco prompt editor, model, temperature, max_tokens,
  Save / Reset-to-seed / Preview-prompt dialog).
- **Light observability**: the previously-dead `audit_logs` table is now
  written per step (strategist, copywriter, and each per-format chain step)
  and surfaced as a Trace tab in the task inspector via
  `GET /api/tasks/{id}/audit`.

## Future (documented, not built)
- **Checkpoint persistence**: swap `MemorySaver` for `AsyncSqliteSaver`
  (`langgraph-checkpoint-sqlite`); the thread id already equals the task id,
  so per-node state becomes inspectable (state viewer) and resumable. Add
  retention integration so expired tasks sweep checkpoints too.
- **Human-in-the-loop**: `graph.interrupt()` at the designer→render and
  verifier gates, resumed via `update_state`, enabling pause/approve/
  intercept/edit in the task UI.
- **Heavy observability**: live node-by-node streaming on top of the existing
  `astream_events` progress + the audit timeline.

## API surface
- `GET /api/agents?include_inactive=`
- `GET /api/agents/{name}` · `PUT /api/agents/{name}` · `POST /api/agents/{name}/reset`
- `GET /api/agents/graph`
- `POST /api/agents/{name}/prompt-preview` → `{agent, system_prompt, user_prompt}`
