# Stage 1: Build
FROM node:22-alpine AS builder

RUN corepack enable pnpm

WORKDIR /app

# Install dependencies first (layer caching)
COPY ui/package.json ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy schema for API client generation
COPY schema/openapi.json ../schema/openapi.json

# Copy source
COPY ui/ .

# Generate API client from OpenAPI schema
RUN pnpm run codegen

# Build using the project's canonical build script so type-checking and bundling stay aligned.
RUN pnpm run build

# Stage 2: Serve
FROM caddy:2-alpine

COPY ui/Caddyfile /etc/caddy/Caddyfile
COPY --from=builder /app/dist /srv/dist
