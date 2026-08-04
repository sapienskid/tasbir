# Multi-stage build: the SPA is built and baked into the api image, so the
# api container serves the Studio itself — no separate frontend container.
#
# Build context = repo root (docker build -f backend/Dockerfile .)
#
# Stage 1 — build the Tasbir Studio SPA.
FROM node:22-alpine AS frontend-build
WORKDIR /frontend
RUN corepack enable && corepack prepare pnpm@latest --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

# Stage 2 — the api/worker/beat image.
FROM python:3.12-slim
WORKDIR /app

COPY backend/pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY backend/ .
# Bake the SPA into the image at /app/static (served by the api at /).
COPY --from=frontend-build /frontend/dist /app/static

# Seed assets (backend/data/design_system/) ship inside the image so a fresh
# named volume gets them on first boot. data/output is generated at runtime.
RUN mkdir -p data/output \
    && chown -R 1000:1000 /app/data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
