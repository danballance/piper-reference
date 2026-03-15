# Docker Compose Review Findings

Review of `docker-compose.yml` (dev) and `docker-compose.images.yml` (prod).

---

## Walkthrough: `docker-compose.yml` (Development)

### `api` service (lines 2–23)

- **Image:** `python:3.12-slim` — official slim Python image, no custom Dockerfile needed since source is mounted in.
- **Volumes:** Mounts `backend/api/`, `pyproject.toml`, and `uv.lock` individually (not the whole `backend/` dir). A named volume `api-venv` persists the virtualenv across container restarts so `uv sync` is fast on subsequent runs.
- **Command:** Installs `uv` via pip on every start, syncs deps with `--frozen` (lockfile not modified), then runs uvicorn with `--reload` for hot-reloading on `0.0.0.0:8080`.
- **Expose:** Port 8080 is exposed to the Docker network only — not to the host.
- **Healthcheck:** TCP socket check (not HTTP). 12 retries x 5s interval = 60s max wait after a 30s start period, so worst case ~90s before declared unhealthy.

### `ui` service (lines 25–47)

- **Image:** `node:22-alpine`.
- **Volumes:** Mounts the full `ui/` dir plus `schema/` (for codegen). Named volumes for `node_modules` and `.pnpm-store` avoid the host-vs-container `node_modules` conflict and speed up installs.
- **Command:** Enables pnpm via corepack, installs deps with `--frozen-lockfile`, runs codegen (presumably from the shared schema), then starts the Vite dev server with `--host` (listens on 0.0.0.0).
- **Expose:** Port 5173 (Vite default), Docker network only.
- **Healthcheck:** HTTP check via `wget` on `http://localhost:5173/`. Longer `start_period` (60s) accounts for `pnpm install` + codegen time.

### `playwright` service (lines 54–74)

- **Image:** `mcr.microsoft.com/playwright:v1.58.2-noble` — pinned version for reproducibility.
- **Volumes:** Mounts `ui/` with a **separate** `node_modules` named volume from the `ui` service, preventing version conflicts between dev and test.
- **Command:** Enables pnpm, installs deps, runs `pnpm test:e2e`.
- **Environment:** `PLAYWRIGHT_BASE_URL` tells tests where to find the running app.
- **depends_on:** Waits for `api` and `ui` to be healthy.
- **Profiles:** `test` — not started by default, only with `docker compose --profile test up`.

### Named volumes (lines 93–97)

Four named volumes (`api-venv`, `ui-node-modules`, `ui-pnpm-store`, `playwright-node-modules`). All use the default local driver. These persist dependency caches across container restarts.

---

## Walkthrough: `docker-compose.images.yml` (Production)

This file defines the same 2-container topology using prebuilt images. The UI image handles reverse proxying to the API via embedded Caddy.

### `api` service (lines 9–20)

- **Image:** `${API_IMAGE:?...}` — the `:?` syntax makes the variable **required**; compose errors with the message if unset.
- **Expose:** Port 8080, Docker network only. No host port mapping — the deployment platform handles routing.
- **Restart:** `unless-stopped` — survives crashes but respects manual stops.
- **Healthcheck:** HTTP check via `wget` on `http://localhost:8080/health`. Longer interval (10s vs 5s in dev) since prod doesn't need aggressive polling. Shorter start period (10s vs 30s) since prebuilt images skip dependency installation.

### `ui` service (lines 22–38)

- **Image:** `${UI_IMAGE:?...}` — also required.
- **Expose:** Port 80. The production UI image serves static assets and reverse-proxies API requests via embedded Caddy.
- **Environment:** `PORT: "80"` and `BACKEND_URL: api:8080` so the embedded proxy can route API calls.
- **depends_on:** Only `api`.
- **Restart/Healthcheck:** Same pattern as the api service, checking `http://localhost:80/health`.

---

## Bugs (Resolved)

### ~~Playwright `PLAYWRIGHT_BASE_URL` pointed to wrong service~~ (Fixed)

Resolved by removing the caddy service entirely. Playwright now uses `http://ui:5173` and depends on both `api` and `ui`.

## Minor

### API healthcheck is TCP-only (dev)

- **File:** `docker-compose.yml:19`
- All other services use HTTP healthchecks, but the API service uses a raw TCP socket check.
- This won't catch an app that's listening but returning 500s.
- Could use `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"` for an HTTP check without needing wget/curl in the slim image.

### Production images assume `wget` is available

- **File:** `docker-compose.images.yml:16, 33`
- Both api and ui healthchecks use `wget`. Verify that the production Dockerfiles include it in the final stage.
