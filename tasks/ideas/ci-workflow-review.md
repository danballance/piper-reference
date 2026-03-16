# CI Workflow Review Findings

There are two CI workflow files — one for the template repo, one for generated projects. They are structurally identical (same steps, same order) and differ only in path prefixes and the copier generation preamble.

- **Template repo:** `.github/workflows/ci.yml` — generates the project via copier, then validates/publishes from `./build`
- **Generated projects:** `_template/.github/workflows/ci.yml` — copied automatically by copier's `_subdirectory`, uses direct paths

---

## Walkthrough: `_template/.github/workflows/ci.yml` (Generated Projects)

This is the canonical reference. The template repo variant is identical except every path is prefixed with `./build` and each job has a copier generation step.

### Trigger & concurrency (lines 1–14)

- **Triggers:** PRs run `validate` only; pushes to `main` and `v*` tags also run `publish-backend` and `publish-ui`.
- **Concurrency group** cancels superseded runs on the same branch/tag.

### `validate` job

| Step | Notes |
|------|-------|
| Checkout | No `fetch-depth: 0` needed (not a template) |
| Configure git for private packages | Rewrites GitHub HTTPS URLs to include `PRIVATE_REPO_TOKEN` |
| Install uv | `astral-sh/setup-uv@v4` |
| Install backend deps | `uv sync --frozen` — fails on lockfile drift |
| Backend linting | `lint-py.sh fast` — ruff format/check + ty, runs before tests for fast failure |
| Backend tests | `pytest -m "not schemathesis"` — regular tests |
| Backend schema tests | `pytest -m schemathesis` — property-based API schema tests (ASGI transport) |
| Install pnpm | Pinned to `9` (matches lockfile v9.0) |
| Install Node.js | `22` (matches `node:22-alpine` in Dockerfile), caches pnpm store |
| Install frontend deps | `pnpm install --frozen-lockfile` |
| Frontend linting | `lint-ts.sh fast` — biome format/lint + tsc |
| Frontend unit tests | `pnpm test` (vitest with browser-playwright) |
| Start Docker Compose | `up -d --wait --wait-timeout 120 api ui` — blocks until healthchecks pass |
| Run E2E tests | `--profile test run --rm playwright` — Playwright in Docker |
| Upload Playwright report | On failure only, 7-day retention |
| Stop Docker Compose | `down -v --remove-orphans` — always runs, removes volumes |

### `publish-backend` job

- Needs `validate`, runs on push only
- Minimal permissions: `contents: read`, `packages: write`
- Docker tags: `latest` (default branch), `sha-*` (every push), semver `{{version}}` and `{{major}}.{{minor}}` (tags)
- Build context: `./backend` — Dockerfile at default location
- Multi-platform: `linux/amd64,linux/arm64` via QEMU
- GHA layer cache with `mode=max`

### `publish-ui` job

- Same as backend, with `IMAGE_NAME: ${{ github.repository }}-ui`
- Build context: `.` (project root) with `file: ./ui/Dockerfile` — the UI Dockerfile references `../schema/openapi.json`
- Otherwise identical to backend publish

---

## Walkthrough: `.github/workflows/ci.yml` (Template Repo)

Differences from the generated-project variant:

| Aspect | Generated project | Template repo |
|--------|-------------------|---------------|
| Name | `CI & Publish` | `Template CI & Publish` |
| Checkout | Default depth | `fetch-depth: 0` (needed for copier `--vcs-ref`) |
| Copier step | None | `pip install 'copier>=9,<10'` + `copier copy --defaults --trust --vcs-ref HEAD` |
| All paths | Direct (e.g., `./backend`) | Prefixed (e.g., `./build/backend`) |
| Docker compose | `docker compose up` | `docker compose -f ./build/docker-compose.yml up` |

Everything else (steps, ordering, versions, tags, caching) is identical.

---

## Issues Resolved

| # | Category | Fix Applied |
|---|----------|-------------|
| 1 | Bug | Added `--frozen` to `uv sync` — catches lockfile drift |
| 2 | Reproducibility | Pinned pnpm to `9` — was `latest` |
| 3 | Reproducibility | Pinned copier to `>=9,<10` — was unpinned |
| 4 | Traceability | Added `type=sha,prefix=sha-` Docker tags |
| 5 | Performance | Added `concurrency` group — cancels superseded runs |
| 6 | Performance | Moved linting before tests — fails faster on trivial issues |
| 7 | Coverage | Added frontend unit test step (`pnpm test` / vitest) |
| 8 | Simplicity | Split into two purpose-specific CI files — eliminated all conditionals and `workdir` indirection |
| 9 | Simplicity | Removed `scripts/copy_ci_workflow.py` and copier `_tasks` — copier's `_subdirectory` handles CI file copying natively |

## Remaining Notes

- **`astral-sh/setup-uv@v4`** doesn't pin a uv version. Generally fine since uv maintains backward compatibility.
- **Duplicate copier generation** across the 3 template-repo jobs. Could be optimized with artifact upload/download if CI time matters.
- **API healthcheck is TCP-only** in dev docker-compose. Covered in `tasks/ideas/docker-compose-review.md`.
