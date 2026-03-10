# E2E Testing

End-to-end tests use [Playwright](https://playwright.dev/) running in a Docker
container against the full application stack in Docker Compose.

## Running Locally

Start the stack and wait for all services to be healthy:

```bash
docker compose up -d --wait
```

Run the tests in a container:

```bash
docker compose --profile test run --rm playwright
```

Tear down when finished:

```bash
docker compose --profile test down
```

## How It Works

Playwright runs inside a Docker container on the same Docker Compose network as
the application stack. It connects to Caddy at `http://caddy:3000`, which routes
requests to the backend API and frontend dev server.

```
Container (Playwright) → caddy:3000 (Caddy) → api:8080 / ui:5173
```

Docker Compose healthchecks on all three services (api, ui, caddy) ensure the
stack is ready before the Playwright container starts (via `depends_on`).

The `test` profile keeps the Playwright container from starting during normal
`docker compose up` — it only runs on demand.

## CI Pipeline

The GitHub Actions workflow (`validate-template.yml`) runs E2E tests as part of
the `validate` job:

1. `docker compose up -d --wait --wait-timeout 120` — starts the stack
2. `docker compose --profile test run --rm playwright` — runs tests in container
3. Uploads the Playwright HTML report as an artifact on failure
4. `docker compose --profile test down` — tears down everything (runs even if tests fail)

## Writing Tests

Tests live in `ui/tests/e2e/` and use `@playwright/test`. The `baseURL` is
configured via the `PLAYWRIGHT_BASE_URL` env var (set to `http://caddy:3000`
by Docker Compose). Falls back to `http://localhost:3000` for host-based runs.

```typescript
import { test, expect } from "@playwright/test";

test("example", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("expected text")).toBeVisible();
});
```

## Configuration

- Playwright config: `ui/playwright.config.ts`
- Playwright service: `docker-compose.yml` (profile: `test`)
- Docker Compose healthchecks: `docker-compose.yml`
- Caddy health endpoint: `ui/Caddyfile.dev` (`/health`)
- Test script: `pnpm test:e2e` (defined in `ui/package.json`)

## Troubleshooting

**Stack not healthy / `--wait` times out:**
Check individual service health with `docker compose ps`. The api and ui
services have a 30-second start period to allow for dependency installation on
first run.

**Port 3000 already in use:**
Stop any other process on port 3000, or stop a previous Docker Compose
stack with `docker compose --profile test down`.
