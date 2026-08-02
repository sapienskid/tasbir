# ADR-0015: All configuration lives in the database

**Status:** Accepted · **Date:** v3.6

## Context
Design systems, templates, and agent prompts already live in the DB (ADR-0012,
ADR-0013), but the rest of the configuration still lived in `data/design_system/*.yaml`
and as hardcoded constants in code:

- **`platforms.yaml`** — read at runtime by `formats.get_format_info` /
  `validate_platforms` (every request), the planner, the prompt preview, and
  `format_family`. Adding a platform required a YAML edit + worker restart +
  frontend rebuild (dims were hardcoded in `preview-frame.tsx` /
  `new-task.tsx`).
- **`fonts.yaml`** (curated Google Font pool) — read by the brand_tokens agent.
- **Hardcoded knobs** — verifier retries, copywriter concurrency, vision
  min-interval, chat HTML cap, template anti-repeat limit.
- **Fallback YAML reads** — several empty-state / degraded paths loaded
  brand/tokens/design-instruction from the YAML files instead of the DB
  default system.

## Decision
- **`platforms` table** (global): `id`, `name`, `width`, `height`, `family`,
  `is_active`, `sort_order`. **`fonts` table** (global curated pool): `family`,
  `role`, `weights`, `style`, `is_active`. **`app_settings` table** (runtime
  tuning knobs): key/value/description.
- **Seed-once + Studio owns** (same policy as agents, ADR-0013): the YAML files
  seed the tables on first boot; from then on the Studio owns the rows and
  there is **no boot reconcile**.
- **`services/platforms.py`** keeps a warm **sync TTL cache** refreshed at
  lifespan, on every API write, and once per `generate_task` (workers never run
  the FastAPI lifespan); YAML is a documented pre-boot/unit-test fallback only.
- **`services/fonts.py`** and **`services/settings.py`** are DB-backed with a
  TTL cache; `settings` replaces the hardcoded knobs (verifier retries,
  copywriter concurrency, vision interval, chat HTML cap, template recent
  limit) and exposes a reset-to-default.
- **`default_design_system_payload()`** centralizes the default-DS fallback so
  no runtime path reads brand/tokens/campaigns/design-instruction YAML —
  those files are pure seed sources for `seeding.py`.
- **APIs**: `GET/POST/PUT/DELETE /api/platforms`, `GET/POST/PUT/DELETE
  /api/fonts/pool`, `GET/PUT /api/settings` + `/api/settings/reset`.
- **Frontend**: a new **Settings** page (Platforms / Fonts / Runtime tabs); the
  platform list, dimension maps, and family mapping now come from
  `GET /api/platforms` via `lib/platforms.ts` + `usePlatforms()` — the
  hardcoded `KNOWN_PLATFORMS` / `FORMAT_DIMS` / `FAMILY_DIMS` /
  `FAMILY_OF_PLATFORM` are gone.

## Result
At runtime (post-seed) **nothing reads `data/design_system/*.yaml`**: all
config — brand, tokens, campaigns, design-instruction, platforms, fonts,
templates, agents, runtime knobs — is DB-backed and Studio-editable, and every
reader resolves through the DB.

## Future
- Env variables remain the source for infra/secrets (API keys, Redis URL,
  render key); a `runtime` knob could later supersede env for things like the
  rate limit and retention TTL if the Studio should own them.
