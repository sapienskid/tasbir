# Dev-only build stage — used by docker-compose.dev.yml (target: build) to run
# the Vite dev server. Production bakes the built SPA into the api image
# (backend/Dockerfile multi-stage), so there is no production frontend image.
FROM node:22-alpine AS build
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build
