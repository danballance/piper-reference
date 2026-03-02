# Dockerization & CI Design

**Date:** 2026-03-02
**Status:** Approved

## Goal

Containerize the Litestar backend for deployment to Railway, with a GHA pipeline for publishing images to ghcr.io and a docker-compose file for local development.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Package manager | uv | Already in use, fast, lockfile present |
| ASGI server | uvicorn | Included via litestar[standard], simple |
| Dockerfile strategy | Multi-stage build | Smaller image, no build tools in production |
| Container port | 8080 | Common for cloud deployments |
| GHA trigger | Git tags (`v*`) | Controlled releases |
| CI tests in pipeline | No | Handled by separate workflow |
| Docker Compose mode | Local build only | Simple, development-focused |

## Dockerfile

Multi-stage build:

**Builder stage** (`python:3.12-slim`):
- Install uv via copy from official image
- Copy `pyproject.toml` + `uv.lock` first for layer caching
- `uv sync --frozen --no-dev` to install production deps into a venv
- Copy `api/` source code

**Runtime stage** (`python:3.12-slim`):
- Create non-root `app` user
- Copy venv and `api/` from builder
- Add venv `bin/` to `PATH`
- Expose 8080
- CMD: `uvicorn api.main:app --host 0.0.0.0 --port 8080`

A `.dockerignore` excludes tests, docs, tasks, devenv files, and git metadata.

## GitHub Actions Pipeline

**File:** `.github/workflows/publish-image.yml`
**Trigger:** Tag push matching `v*`

Steps:
1. Checkout
2. Login to ghcr.io (built-in `GITHUB_TOKEN`)
3. Extract metadata (version tag + `latest`)
4. Build and push with `docker/build-push-action` and layer caching

Actions used:
- `actions/checkout@v4`
- `docker/login-action@v3`
- `docker/metadata-action@v5`
- `docker/build-push-action@v6`

## Docker Compose

**File:** `docker-compose.yml`

Single service `api` with `build: .` and port mapping `8080:8080`. Local build only. Ready to extend with database services later.

## Files to Create

1. `Dockerfile`
2. `.dockerignore`
3. `.github/workflows/publish-image.yml`
4. `docker-compose.yml`
