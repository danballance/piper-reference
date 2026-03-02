# Dockerization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Containerize the Litestar backend with a multi-stage Dockerfile, GHA publish pipeline to ghcr.io, and docker-compose for local development.

**Architecture:** Multi-stage Docker build using uv for dependency installation. Builder stage installs deps, runtime stage runs uvicorn on port 8080 as non-root user. GHA pipeline triggers on version tags and publishes to ghcr.io.

**Tech Stack:** Docker (multi-stage), uv, uvicorn, GitHub Actions, docker-compose

**Design doc:** `docs/plans/2026-03-02-dockerization-design.md`

---

### Task 1: Create .dockerignore

**Files:**
- Create: `.dockerignore`

**Step 1: Create the .dockerignore file**

```
# Version control
.git
.gitignore

# Tests
tests/

# Documentation and planning
docs/
tasks/
README.md
CLAUDE.md

# Development environment
devenv.yaml
devenv.nix
devenv.lock
.devenv/
.direnv/
.envrc

# Python artifacts
__pycache__/
*.pyc
*.pyo
*.egg-info/
.pytest_cache/

# IDE
.vscode/
.idea/

# Docker
Dockerfile
docker-compose.yml
.dockerignore

# CI
.github/

# Lock files not needed (uv.lock IS needed)
poetry.lock

# Claude
.claude/
```

**Step 2: Commit**

```bash
git add .dockerignore
git commit -m "chore: add .dockerignore"
```

---

### Task 2: Create Dockerfile

**Files:**
- Create: `Dockerfile`

**Reference:** The app entry point is `api.main:app` (see `api/main.py:19`). Dependencies are defined in `pyproject.toml` with a `uv.lock` lockfile. The project uses `setuptools` as the build backend with packages discovered from the repo root (`[tool.setuptools.packages.find] where = ["."]`).

**Step 1: Create the Dockerfile**

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY api/ api/

# Install the project itself
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.12-slim

# Create non-root user
RUN groupadd --system app && useradd --system --gid app app

WORKDIR /app

# Copy the virtual environment and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/api /app/api

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER app

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Step 2: Build the image locally to verify it works**

```bash
docker build -t piper-reference:local .
```

Expected: Build completes successfully.

**Step 3: Run the container to verify the app starts**

```bash
docker run --rm -p 8080:8080 piper-reference:local &
sleep 2
curl -s http://localhost:8080/ | head -20
```

Expected: Returns `[]` (empty todo list). Kill the container after verifying.

**Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: add multi-stage Dockerfile with uv"
```

---

### Task 3: Create docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

**Step 1: Create docker-compose.yml**

```yaml
services:
  api:
    build: .
    ports:
      - "8080:8080"
```

**Step 2: Test with docker compose**

```bash
docker compose up --build -d
sleep 2
curl -s http://localhost:8080/
docker compose down
```

Expected: Returns `[]` (empty todo list).

**Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose for local development"
```

---

### Task 4: Create GHA publish pipeline

**Files:**
- Create: `.github/workflows/publish-image.yml`

**Step 1: Create the workflow file**

The `GITHUB_TOKEN` permissions must include `packages: write` to push to ghcr.io. The metadata action automatically generates tags from the git tag.

```yaml
name: Publish Docker Image

on:
  push:
    tags:
      - "v*"

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  publish:
    runs-on: ubuntu-latest

    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Step 2: Verify YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/publish-image.yml'))"
```

Expected: No output (valid YAML).

**Step 3: Commit**

```bash
git add .github/workflows/publish-image.yml
git commit -m "ci: add GHA pipeline to publish Docker image to ghcr.io"
```

---

### Task 5: Final verification

**Step 1: Run full docker compose cycle**

```bash
docker compose up --build -d
sleep 2

# Test GET (empty list)
curl -s http://localhost:8080/

# Test POST (add a todo)
curl -s -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{"title": "test", "done": false}'

# Test GET with filter
curl -s "http://localhost:8080/?done=false"

docker compose down
```

Expected:
- GET returns `[]`
- POST returns `[{"title":"test","done":false}]`
- Filtered GET returns `[{"title":"test","done":false}]`

**Step 2: Verify all files are committed**

```bash
git status
```

Expected: Clean working tree.
