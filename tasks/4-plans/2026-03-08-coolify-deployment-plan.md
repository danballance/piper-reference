# Coolify Self-Hosted CD Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable self-hosted continuous delivery on a Mac Studio (Asahi Fedora ARM64) using Coolify, with Cloudflare Tunnel for public access.

**Architecture:** Production Dockerfiles embed a copier generator stage to render `.jinja` templates before building. Coolify deploys via Docker Compose build pack, building ARM64 images natively. Cloudflare Tunnel routes public traffic through Coolify's Traefik to the UI container's Caddy, which serves the SPA and proxies `/api/*` to the backend.

**Tech Stack:** Docker, Docker Compose, Coolify, Cloudflare Tunnel, Copier

**Design doc:** `tasks/4-plans/2026-03-08-coolify-deployment-design.md`

---

### Task 1: Update `.dockerignore` for deploy build context

The deploy Dockerfiles need the full repo (including `backend/`) as build context
for the copier stage. The current `.dockerignore` excludes `backend/`.

**Files:**
- Modify: `.dockerignore:5-6`

**Step 1: Remove the `backend/` exclusion**

Replace lines 5-6:
```
# Backend (not needed for UI image)
backend/
```

With nothing (delete both lines). The existing UI Dockerfile explicitly copies
only `ui/` and `schema/` paths, so having `backend/` in the context is harmless —
just a slightly larger context.

**Step 2: Verify existing builds still work**

Run:
```bash
docker compose build ui
```
Expected: Builds successfully (UI Dockerfile never references `backend/`).

**Step 3: Commit**

```bash
git add .dockerignore
git commit -m "chore: remove backend/ from .dockerignore for deploy builds"
```

---

### Task 2: Create `deploy/Dockerfile.api`

Mirrors `backend/Dockerfile` exactly but prepends a copier generator stage.
The generator renders `.jinja` files so `pyproject.toml` and `uv.lock` exist
for the builder stage.

**Files:**
- Create: `deploy/Dockerfile.api`

**Reference:** `backend/Dockerfile` (all stages), `.github/workflows/validate-template.yml:31` (copier command), `.github/workflows/validate-template.yml:96-102` (backend build context is `./build/backend`)

**Step 1: Create the Dockerfile**

```dockerfile
# Stage 0: Generate project from copier template
FROM python:3.12-slim AS generator

RUN pip install --no-cache-dir copier

WORKDIR /template
COPY . .

RUN copier copy --defaults --trust ./ /generated

# Stage 1: Builder (mirrors backend/Dockerfile)
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (layer caching)
COPY --from=generator /generated/backend/pyproject.toml /generated/backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY --from=generator /generated/backend/api/ api/

# Install the project itself
RUN uv sync --frozen --no-dev

# Stage 2: Runtime (mirrors backend/Dockerfile)
FROM python:3.12-slim

RUN groupadd --system app && useradd --system --gid app app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/api /app/api

ENV PATH="/app/.venv/bin:$PATH"

USER app

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Key differences from `backend/Dockerfile`:
- Stage 0 added: installs copier, copies entire repo, generates project
- All `COPY` instructions in Stage 1 use `COPY --from=generator /generated/backend/...`
  instead of `COPY` (mirroring how GHA uses `./build/backend` as context)
- Stages 1-2 are structurally identical otherwise

**Step 2: Test the build**

Run from repo root (context must be `.`):
```bash
docker build -f deploy/Dockerfile.api -t piper-api:test .
```
Expected: Builds successfully through all 3 stages.

**Step 3: Verify the image runs**

```bash
docker run --rm -p 8080:8080 piper-api:test
```
Expected: Uvicorn starts on port 8080. `curl http://localhost:8080/` returns a response.

Stop the container with Ctrl+C.

**Step 4: Clean up test artifacts**

```bash
docker rmi piper-api:test
```

**Step 5: Commit**

```bash
git add deploy/Dockerfile.api
git commit -m "feat: add production Dockerfile for API with copier stage"
```

---

### Task 3: Create `deploy/Dockerfile.ui`

Mirrors `ui/Dockerfile` exactly but prepends the same copier generator stage.
The GHA workflow uses the project root (`./build`) as context for the UI build,
with `./build/ui/Dockerfile` as the dockerfile path.

**Files:**
- Create: `deploy/Dockerfile.ui`

**Reference:** `ui/Dockerfile` (all stages), `ui/Caddyfile` (copied into image), `.github/workflows/validate-template.yml:158-167` (UI build context is `./build`, dockerfile is `./build/ui/Dockerfile`)

**Step 1: Create the Dockerfile**

```dockerfile
# Stage 0: Generate project from copier template
FROM python:3.12-slim AS generator

RUN pip install --no-cache-dir copier

WORKDIR /template
COPY . .

RUN copier copy --defaults --trust ./ /generated

# Stage 1: Build (mirrors ui/Dockerfile)
FROM node:22-alpine AS builder

RUN corepack enable pnpm

WORKDIR /app

# Install dependencies first (layer caching)
COPY --from=generator /generated/ui/package.json /generated/ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy schema for API client generation
COPY --from=generator /generated/schema/openapi.json ../schema/openapi.json

# Copy source
COPY --from=generator /generated/ui/ .

# Generate API client from OpenAPI schema
RUN pnpm run codegen

# Build: vite plugin generates route tree, then bundles the app
RUN pnpm exec vite build

# Stage 2: Serve (mirrors ui/Dockerfile)
FROM caddy:2-alpine

COPY --from=generator /generated/ui/Caddyfile /etc/caddy/Caddyfile
COPY --from=builder /app/dist /srv/dist
```

Key differences from `ui/Dockerfile`:
- Stage 0 added (same copier generator as API)
- `COPY ui/package.json ui/pnpm-lock.yaml ./` becomes
  `COPY --from=generator /generated/ui/package.json /generated/ui/pnpm-lock.yaml ./`
- `COPY schema/openapi.json ../schema/openapi.json` becomes
  `COPY --from=generator /generated/schema/openapi.json ../schema/openapi.json`
- `COPY ui/ .` becomes `COPY --from=generator /generated/ui/ .`
- `COPY ui/Caddyfile ...` becomes `COPY --from=generator /generated/ui/Caddyfile ...`
- Structurally identical otherwise

**Step 2: Test the build**

```bash
docker build -f deploy/Dockerfile.ui -t piper-ui:test .
```
Expected: Builds successfully through all 3 stages (codegen + vite build complete).

**Step 3: Verify the image runs**

```bash
docker run --rm -p 8080:80 -e PORT=80 -e BACKEND_URL=localhost:9999 piper-ui:test
```
Expected: Caddy starts. `curl http://localhost:8080/health` returns `OK`.

Stop the container with Ctrl+C.

**Step 4: Clean up test artifacts**

```bash
docker rmi piper-ui:test
```

**Step 5: Commit**

```bash
git add deploy/Dockerfile.ui
git commit -m "feat: add production Dockerfile for UI with copier stage"
```

---

### Task 4: Create `deploy/docker-compose.coolify.yml`

This is the compose file Coolify will use to deploy the template repo.
Both services build from the deploy Dockerfiles with context set to repo root.

**Files:**
- Create: `deploy/docker-compose.coolify.yml`

**Reference:** `docker-compose.yml` (dev compose for structure reference), `ui/Caddyfile:8` (BACKEND_URL default is `backend.railway.internal:8080`)

**Step 1: Create the compose file**

```yaml
services:
  api:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.api
    expose:
      - "8080"
    restart: unless-stopped

  ui:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.ui
    expose:
      - "80"
    environment:
      PORT: "80"
      BACKEND_URL: api:8080
    depends_on:
      - api
    restart: unless-stopped
```

Notes:
- `context: ..` — build context is repo root (parent of `deploy/`), required
  so `COPY . .` in the generator stage gets copier.yml and all .jinja files
- `expose` not `ports` — Coolify's Traefik handles external routing
- `BACKEND_URL: api:8080` — overrides the Railway default in `ui/Caddyfile:8`
- `PORT: "80"` — explicit Caddy listen port

**Step 2: Test the full stack build**

```bash
docker compose -f deploy/docker-compose.coolify.yml build
```
Expected: Both services build successfully.

**Step 3: Test the full stack runs**

```bash
docker compose -f deploy/docker-compose.coolify.yml up -d
```
Expected: Both containers start. Check with:
```bash
docker compose -f deploy/docker-compose.coolify.yml ps
```
Both services should be running.

**Step 4: Test connectivity**

Since services only `expose` (no host port mapping), test via docker network:
```bash
docker compose -f deploy/docker-compose.coolify.yml exec ui curl -s http://localhost:80/health
```
Expected: `OK`

```bash
docker compose -f deploy/docker-compose.coolify.yml exec ui curl -s http://api:8080/
```
Expected: API response (confirms inter-service networking works).

**Step 5: Tear down**

```bash
docker compose -f deploy/docker-compose.coolify.yml down
```

**Step 6: Commit**

```bash
git add deploy/docker-compose.coolify.yml
git commit -m "feat: add Coolify docker-compose for template repo deployment"
```

---

### Task 5: Create `docker-compose.prod.yml` for generated projects

This simpler compose file is for projects generated from the template
(post-copier). It uses the existing Dockerfiles directly since all `.jinja`
files have already been rendered.

**Files:**
- Create: `docker-compose.prod.yml`

**Reference:** `backend/Dockerfile` (context is `./backend`), `ui/Dockerfile` (context is project root `.`, dockerfile at `ui/Dockerfile`)

**Step 1: Create the compose file**

```yaml
services:
  api:
    build:
      context: ./backend
    expose:
      - "8080"
    restart: unless-stopped

  ui:
    build:
      context: .
      dockerfile: ui/Dockerfile
    expose:
      - "80"
    environment:
      PORT: "80"
      BACKEND_URL: api:8080
    depends_on:
      - api
    restart: unless-stopped
```

Notes:
- `context: ./backend` — matches the GHA workflow's backend build context
- `context: .` with `dockerfile: ui/Dockerfile` — matches the GHA workflow's
  UI build (context is project root because UI Dockerfile copies from
  `ui/` and `schema/` relative paths)
- No copier stage needed — generated projects have real files

**Step 2: Verify it works with a generated project**

```bash
copier copy --defaults --trust --vcs-ref HEAD ./ /tmp/test-prod-compose
cd /tmp/test-prod-compose
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml down
cd -
rm -rf /tmp/test-prod-compose
```
Expected: Both services build and start successfully.

**Step 3: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat: add production docker-compose for generated projects"
```

---

### Task 6: Update `copier.yml` to exclude `deploy/`

Generated projects should not include the `deploy/` directory (it's only
for the template repo). Generated projects use `docker-compose.prod.yml`
with the existing Dockerfiles.

**Files:**
- Modify: `copier.yml:3-7`

**Step 1: Add the exclusion**

Add `"deploy/"` to the `_exclude` list after line 5 (`"build/"`):

```yaml
_exclude:
  - "copier.yml"
  - "build/"
  - "deploy/"
  - "tasks/plans/2026-*-copier-*"
  - ".github/workflows/validate-template.yml"
  - "docs/template-guide.md"
```

**Step 2: Verify the exclusion works**

```bash
copier copy --defaults --trust --vcs-ref HEAD ./ /tmp/test-exclusion
ls /tmp/test-exclusion/deploy 2>&1
```
Expected: `ls: cannot access '/tmp/test-exclusion/deploy': No such file or directory`

```bash
ls /tmp/test-exclusion/docker-compose.prod.yml
```
Expected: File exists (prod compose IS included in generated projects).

```bash
rm -rf /tmp/test-exclusion
```

**Step 3: Commit**

```bash
git add copier.yml
git commit -m "chore: exclude deploy/ from copier template output"
```

---

### Task 7: End-to-end verification

Full integration test of the complete deployment stack.

**Files:** None (verification only)

**Step 1: Verify template repo deployment (Coolify path)**

```bash
docker compose -f deploy/docker-compose.coolify.yml build
docker compose -f deploy/docker-compose.coolify.yml up -d
docker compose -f deploy/docker-compose.coolify.yml ps
```
Expected: Both `api` and `ui` services running.

**Step 2: Test health and API connectivity**

```bash
docker compose -f deploy/docker-compose.coolify.yml exec ui curl -s http://localhost:80/health
docker compose -f deploy/docker-compose.coolify.yml exec ui curl -s http://api:8080/
```
Expected: Health returns `OK`, API returns a response.

**Step 3: Tear down**

```bash
docker compose -f deploy/docker-compose.coolify.yml down
```

**Step 4: Verify generated project deployment (prod path)**

```bash
copier copy --defaults --trust --vcs-ref HEAD ./ /tmp/test-e2e
cd /tmp/test-e2e
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml down
cd -
rm -rf /tmp/test-e2e
```
Expected: Both services build, start, and run successfully.

**Step 5: Verify copier exclusions are correct**

```bash
copier copy --defaults --trust --vcs-ref HEAD ./ /tmp/test-final
test ! -d /tmp/test-final/deploy && echo "PASS: deploy/ excluded"
test -f /tmp/test-final/docker-compose.prod.yml && echo "PASS: prod compose included"
test -f /tmp/test-final/backend/Dockerfile && echo "PASS: backend Dockerfile included"
test -f /tmp/test-final/ui/Dockerfile && echo "PASS: UI Dockerfile included"
rm -rf /tmp/test-final
```
Expected: All four checks print PASS.

**Step 6: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: address issues found in e2e verification"
```
(Skip if no fixes needed.)
