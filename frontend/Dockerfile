FROM node:22-alpine AS build
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build

FROM alpine:3.20
# Static build output staged into the volume-mounted /out at container start.
COPY --from=build /app/dist /static
CMD ["sh", "-c", "cp -rf /static/. /out/ && echo 'Tasbir Studio assets staged'"]
