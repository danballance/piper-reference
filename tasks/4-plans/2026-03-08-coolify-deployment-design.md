# Self-Hosted CD Pipeline with Coolify

## Context

The project is deployed to Railway, but we want an alternative self-hosted
deployment on a Mac Studio running Asahi Fedora (ARM64) using Coolify.
This enables a continuous delivery pipeline without relying on cloud PaaS.

## Decisions

- **Build locally on ARM64** — Coolify builds Docker images natively on the Mac
  Studio. CI validates/tests but does not publish ARM64 images.
- **Docker Compose deployment** — Coolify uses its Docker Compose build pack.
- **Copier embedded in Dockerfiles** — each production Dockerfile includes a
  copier generator stage so the build is fully self-contained.
- **Cloudflare Tunnel** — public access without opening ports or needing a
  static IP.
- **Reusable** — template repo uses `deploy/` Dockerfiles with copier; generated
  projects use existing Dockerfiles directly via `docker-compose.prod.yml`.

## Architecture

```
Push to main → GitHub Actions (validate/test)
                    ↓ webhook
               Coolify (Mac Studio ARM64)
                    ↓
               git pull → docker compose build (native ARM64)
                    ↓
               docker compose up
                    ↓
               Cloudflare Tunnel → public domain
```

Runtime traffic flow:

```
Internet → Cloudflare Tunnel → Coolify Traefik → UI container (Caddy :80)
                                                    ├── /* → static files (SPA)
                                                    └── /api/* → api container :8080
```

## Key Constraint: Copier Required for Template Repo

These files only exist as `.jinja` templates:
- `backend/pyproject.toml.jinja` (needed for `uv sync`)
- `ui/package.json.jinja` (needed for `pnpm install`)
- `ui/index.html.jinja`, `ui/src/routes/index.tsx.jinja`

Without `copier copy`, Docker builds fail. The CI workflow handles this with:
```bash
copier copy --defaults --trust --vcs-ref HEAD ./ ./build
```

The deploy Dockerfiles replicate this as a build stage, omitting `--vcs-ref HEAD`
since the Docker build context has no `.git` directory (copier works fine on
local paths without VCS).

## File Changes

### New files

| File | Purpose |
|------|---------|
| `deploy/Dockerfile.api` | Copier stage + mirrors `backend/Dockerfile` |
| `deploy/Dockerfile.ui` | Copier stage + mirrors `ui/Dockerfile` |
| `deploy/docker-compose.coolify.yml` | Compose file for Coolify (template repo) |
| `docker-compose.prod.yml` | Production compose for generated projects |

### Modified files

| File | Change |
|------|--------|
| `copier.yml` | Add `"deploy/"` to `_exclude` |
| `.dockerignore` | Remove `backend/` exclusion (deploy builds need full context) |

### Unchanged files

- `backend/Dockerfile` — used by generated projects and CI
- `ui/Dockerfile` — used by generated projects and CI
- `ui/Caddyfile` — already parameterised via `{$BACKEND_URL}`
- `.github/workflows/validate-template.yml` — CI unchanged

## Production Dockerfiles

### `deploy/Dockerfile.api`

Three stages:
1. **generator** — `python:3.12-slim`, installs copier, copies entire repo,
   runs `copier copy --defaults --trust ./ /generated`
2. **builder** — mirrors `backend/Dockerfile` stage 1, but `COPY --from=generator`
   instead of `COPY`. Installs uv, syncs deps, copies `api/` source.
3. **runtime** — mirrors `backend/Dockerfile` stage 2. Non-root user, port 8080.

### `deploy/Dockerfile.ui`

Three stages:
1. **generator** — identical to API generator
2. **builder** — mirrors `ui/Dockerfile` stage 1, but `COPY --from=generator`.
   Installs pnpm deps, copies schema for codegen, builds Vite SPA.
3. **serve** — `caddy:2-alpine`, copies Caddyfile and built `dist/`.

### `deploy/docker-compose.coolify.yml`

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

- `context: ..` sets build context to repo root (copier needs entire template)
- `expose` (not `ports`) — Coolify's Traefik handles external routing
- `BACKEND_URL: api:8080` overrides the Railway default in the Caddyfile

### `docker-compose.prod.yml` (for generated projects)

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

Uses existing Dockerfiles directly — no copier stage needed.

## Infrastructure Setup

### 1. Coolify Installation

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Requirements: Docker Engine 24+, 2 CPU cores, 2 GB RAM, 30 GB storage.
ARM64 is officially supported.

### 2. Coolify Configuration

1. Add GitHub repo as a source (GitHub App or Deploy Key)
2. Create Application → Docker Compose build pack
3. Set Docker Compose location to `deploy/docker-compose.coolify.yml`
4. Set base directory to `/` (repo root)
5. Configure domain in Coolify UI (Traefik auto-routes)
6. Enable auto-deploy on push to `main`

### 3. Cloudflare Tunnel

```bash
# Install cloudflared
sudo dnf install cloudflared

# Authenticate
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create piper-app

# Configure routing (in ~/.cloudflared/config.yml)
tunnel: <tunnel-id>
credentials-file: ~/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: app.yourdomain.com
    service: http://localhost:80
  - service: http_status:404

# Route DNS
cloudflared tunnel route dns piper-app app.yourdomain.com

# Run as systemd service
sudo cloudflared service install
```

Cloudflare handles SSL termination. Coolify's Traefik routes to the UI
container.

### 4. GitHub Webhook

Coolify provides a webhook URL in the application settings. Add it to the
GitHub repo Settings → Webhooks with:
- Payload URL: Coolify's webhook URL
- Content type: application/json
- Events: Just the push event
- Active: enabled

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Copier without `.git` | Omit `--vcs-ref HEAD`; copier works on plain directories |
| ARM64 image compat | All base images have ARM64 variants |
| Traefik port conflict | Use `expose` not `ports`; let Coolify manage routing |
| Copier runs twice (once per Dockerfile) | <1s operation on local files; negligible |
| `.dockerignore` blocks `backend/` | Remove that exclusion; UI Dockerfile never copies `backend/` anyway |

## Verification

1. Build locally: `docker compose -f deploy/docker-compose.coolify.yml build`
2. Run locally: `docker compose -f deploy/docker-compose.coolify.yml up`
3. Test endpoints: `curl http://localhost:80/health`, `curl http://localhost:80/api/`
4. Validate copier exclusion: `copier copy --defaults --trust ./ /tmp/test && ls /tmp/test/deploy` (should not exist)
5. Deploy via Coolify and verify webhook triggers rebuild
6. Verify Cloudflare Tunnel routes correctly
