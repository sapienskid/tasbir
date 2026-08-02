FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM alpine:3.20
# Static build output staged into the volume-mounted /out at container start.
COPY --from=build /app/dist /static
CMD ["sh", "-c", "cp -rf /static/. /out/ && echo 'Tasbir Studio assets staged'"]
