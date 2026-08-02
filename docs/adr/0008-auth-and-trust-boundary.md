# ADR-0008 — Auth and Trust Boundary

- Status: accepted
- Date: 2026-08-01
- Related: ADR-0007 (ephemeral delivery), ADR-0009 (SSRF policy)

## Context

The API was open by default (`API_KEYS` empty → auth silently disabled), the
Playwright render service was published to the host on port 4000 with
`--disable-web-security` and no auth, CORS was `*` with credentials, and
there was no rate limiting. Anyone who could reach the host could trigger
generation (burning Gemini free-tier quota) or abuse the renderer.

## Decision

- **Auth fails closed.** If `API_KEYS` is empty, all `/generate` and `/tasks`
  requests are rejected with 401. `x-api-key` is a static shared key —
  acceptable for a single-operator, LAN-only deployment.
- **Per-key rate limiting.** A Redis token bucket (default 30 req/min/key,
  `RATE_LIMIT_PER_MIN`) rejects excess requests with 429. Redis failure
  fails open (the request would fail downstream anyway without the broker).
- **Render service is internal-only.** The host port is removed; the service
  is reachable only on the docker network and requires a shared secret
  (`RENDER_SERVICE_KEY`) on `/render` and `/extract-dom`. `--disable-web-security`
  is removed — Chromium enforces same-origin again.
- **CORS** defaults to the dev origins (`localhost:5173`), never `*`.
- The deployment is **local/LAN-only** — no public exposure assumed, no TLS
  in scope (put a reverse proxy in front if ever exposed).

## Consequences

- A misconfiguration can no longer silently open the API.
- The renderer can no longer be reached from outside the docker network or
  used to bypass same-origin policy.
- The operator must set `API_KEYS` and (for Docker) `RENDER_SERVICE_KEY`.
- Rate limits protect the free-tier LLM quota from accidental or malicious
  bursts.
