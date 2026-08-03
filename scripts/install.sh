#!/usr/bin/env bash
#
# install.sh — one-command install / upgrade for Tasbir (self-hosted).
#
# Does:
#   1. Checks prerequisites (docker, docker compose v2, curl)
#   2. Clones or uses the local repo (if run from a checkout, stays in place)
#   3. Creates .env from .env.example if missing, generating strong API keys
#      (API_KEYS + RENDER_SERVICE_KEY) and prompting for GEMINI_API_KEY
#   4. docker compose build + up -d
#   5. Waits for /health and prints the summary
#
# Usage:
#   bash scripts/install.sh                     # run from inside a checkout
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/sapienskid/tasbir/main/scripts/install.sh)" \
#       # one-liner (clones into ./tasbir)
#
# Env overrides:
#   TASBIR_DIR    install directory (default ./tasbir when cloning)
#   GEMINI_API_KEY  provide the key without prompting (non-interactive)
#   TASBIR_SKIP_BUILD=1  reuse existing images / skip rebuild

set -euo pipefail

say()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }
fail() { printf '\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

gen_key() { head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; }

# ── 1. Prerequisites ───────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || fail "docker is required — install it first: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || fail "docker compose v2 is required — upgrade docker or the compose plugin"
command -v curl >/dev/null 2>&1 || warn "curl not found (only needed for the one-liner install path)"

# ── 2. Locate / clone the repo ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
  REPO_ROOT="$SCRIPT_DIR"
elif [[ -f "$(pwd)/docker-compose.yml" ]]; then
  REPO_ROOT="$(pwd)"
else
  REPO_ROOT="${TASBIR_DIR:-$(pwd)/tasbir}"
  if [[ ! -d "$REPO_ROOT" ]]; then
    say "Cloning tasbir into $REPO_ROOT"
    git clone https://github.com/sapienskid/tasbir.git "$REPO_ROOT"
  fi
fi
cd "$REPO_ROOT"
say "Using repo at $REPO_ROOT"

# ── 3. .env setup ──────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  cp .env.example .env
  say "Created .env from .env.example"
  # Generate strong keys; the user supplies the Gemini key.
  sed -i "s/^API_KEYS=.*/API_KEYS=$(gen_key)/" .env
  sed -i "s/^RENDER_SERVICE_KEY=.*/RENDER_SERVICE_KEY=$(gen_key)/" .env
  say "Generated API_KEYS and RENDER_SERVICE_KEY"
fi

# Re-generate keys only if they are still blank (e.g. someone left them empty).
if grep -q '^API_KEYS=$' .env; then
  sed -i "s/^API_KEYS=$/API_KEYS=$(gen_key)/" .env
  say "Filled blank API_KEYS"
fi
if grep -q '^RENDER_SERVICE_KEY=$' .env; then
  sed -i "s/^RENDER_SERVICE_KEY=$/RENDER_SERVICE_KEY=$(gen_key)/" .env
  say "Filled blank RENDER_SERVICE_KEY"
fi

if grep -q '^GEMINI_API_KEY=$' .env; then
  if [[ -n "${GEMINI_API_KEY:-}" ]]; then
    sed -i "s/^GEMINI_API_KEY=$/GEMINI_API_KEY=${GEMINI_API_KEY}/" .env
    say "Set GEMINI_API_KEY from environment"
  else
    warn "GEMINI_API_KEY is empty in .env"
    read -rp "Paste your Google AI Studio API key (https://aistudio.google.com/app/apikey): " KEY_INPUT
    if [[ -n "$KEY_INPUT" ]]; then
      sed -i "s/^GEMINI_API_KEY=$/GEMINI_API_KEY=${KEY_INPUT}/" .env
      say "Saved GEMINI_API_KEY"
    else
      warn "GEMINI_API_KEY left empty — pipeline generation will fail until set"
    fi
  fi
fi

# ── 4. Build + start ───────────────────────────────────────────────────────
if [[ "${TASBIR_SKIP_BUILD:-0}" != "1" ]]; then
  say "Building images (first run downloads deps + Chromium, this takes a while)…"
  docker compose build
else
  warn "TASBIR_SKIP_BUILD=1 — reusing existing images"
fi

say "Starting the stack…"
docker compose up -d

# ── 5. Wait for health ─────────────────────────────────────────────────────
say "Waiting for the API to come up…"
OK=0
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    OK=1
    break
  fi
  sleep 2
done

API_KEY="$(sed -n 's/^API_KEYS=//p' .env | cut -d, -f1)"

cat <<'EOF'

──────────────────────────────────────────────────────────────────────
 Tasbir is ready.
──────────────────────────────────────────────────────────────────────

  Studio (UI):     http://localhost:8000
  API docs:        http://localhost:8000/docs
  Health:          http://localhost:8000/health

  API key (Studio header → API Key):
EOF
echo "    $API_KEY"
cat <<'EOF'

  Management:
    docker compose logs -f api          # API logs
    docker compose ps                   # service status
    scripts/backup-db.sh -k 14          # hourly-ish DB snapshot (see README)
    docker compose down && docker compose up -d   # stop / start
    scripts/install.sh                  # re-run to upgrade (git pull + rebuild)

  Note: deployment is LAN/self-hosted. Do NOT expose port 8000 to the
  public internet without a TLS reverse proxy in front.
──────────────────────────────────────────────────────────────────────
EOF

if [[ "$OK" != "1" ]]; then
  warn "API did not report healthy within ~2 minutes — check: docker compose ps && docker compose logs api"
  exit 1
fi
say "Install complete."
