# Design: Convert Reference Project to Copier Template

**Date**: 2026-03-07
**Status**: Approved

## Goal

Convert this reference project into a copier template so new full-stack projects can be scaffolded quickly and kept in sync with improvements to the reference over time. The template is for personal/team use — deliberately opinionated with a fixed stack.

## Approach

**Root-level template (no subdirectory move).** Project files stay where they are. `copier.yml` is added at the root. Template-only files are excluded from generated output via `_exclude`. Files needing variable substitution gain `.jinja` suffixes.

The reference repo is no longer directly runnable — it requires a "self-build" step to generate a working project. This is acceptable because the self-build step *is* the validation mechanism.

## Template Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `project_name` | string | `"piper-reference"` | Kebab-case project identifier |
| `project_description` | string | `"Piper Reference Project"` | Human-readable description |
| `python_package_name` | string | (derived from `project_name`) | Snake_case, auto-derived but overridable |
| `author_name` | string | `"Anoni Mouse"` | Author full name |
| `author_email` | string | `"nixprivacy@pm.me"` | Author email |
| `include_examples` | bool | `true` | Include todo/user feature modules |

## Files Gaining `.jinja` Suffix

These files contain project-specific values that need substitution:

| File | What gets substituted |
|---|---|
| `backend/pyproject.toml.jinja` | `project_name`, `project_description`, `author_name`, `author_email` |
| `backend/slumber.yml.jinja` | `project_name` in name field |
| `backend/api/main.py.jinja` | `{% if include_examples %}` for todo route wiring |
| `ui/package.json.jinja` | `project_name` in name field |
| `ui/index.html.jinja` | `project_name` in `<title>` |
| `ui/src/routes/index.tsx.jinja` | `project_name` in heading; conditional todo UI vs welcome page |
| `ui/src/routes/__root.tsx.jinja` | Only if it imports example-specific things (verify during implementation) |
| `docs/system-guide.md.jinja` | `project_name` references throughout |
| `docs/api-architecture.md.jinja` | Only if project-name-specific (verify during implementation) |
| `docs/ui-architecture.md.jinja` | Only if project-name-specific (verify during implementation) |
| `CLAUDE.md.jinja` | Project layout references if project-name-specific |
| `README.md.jinja` | Project name and description |
| `devenv.nix.jinja` | `uv.sync.enable` and `pnpm.install.enable` set to `true` in generated projects, `false` in template repo |

## Files Unchanged (No Templatization Needed)

- `docker-compose.yml` — ports and service names are part of the opinionated stack
- `backend/Dockerfile`, `ui/Dockerfile` — no project names
- `ui/vite.config.ts` — proxy config is generic
- `.github/workflows/*` — already use `${{ github.repository }}`
- All source code files not listed above
- `devenv.yaml`, `devenv.lock`, `.envrc`, `.dockerignore`, `.gitignore`

## Conditional Example Features

When `include_examples` is `false`, the following are excluded from the generated project:

- `backend/api/todo/`
- `backend/api/user/`
- `backend/tests/todo/`
- `backend/tests/user/`
- `ui/src/features/`
- `ui/tests/components/`
- `ui/tests/mocks/`
- `ui/tests/e2e/todo.spec.ts`

Files with conditional content:

- `backend/api/main.py.jinja` — composition root wraps todo registration in `{% if include_examples %}`
- `ui/src/routes/index.tsx.jinja` — renders welcome page instead of todo UI when examples excluded

## Excluded from Generated Projects

Via `_exclude` in `copier.yml`:

- `copier.yml`
- `build/`
- `tasks/ideas/*.md` (except `README.md`)
- `tasks/plans/*.md` (except `README.md`)
- `tasks/designs/*.md` (except `README.md`)

## Tasks Directories

The `tasks/` directory structure carries over with README.md files preserved in each subdirectory (`tasks/designs/README.md`, `tasks/plans/README.md`, `tasks/ideas/README.md`). Content files (ideas, plans, designs specific to the reference project) are excluded. `tasks/README.md` and `tasks/TODO.md` carry over.

## Documentation

`docs/` carries over with templatized project names. Architecture guides (`api-architecture.md`, `ui-architecture.md`, `system-guide.md`) are valuable onboarding material for generated projects.

## Development Environment

`devenv.nix` becomes `devenv.nix.jinja`:

- In the template repo: `uv.sync.enable = false`, `pnpm.install.enable = false` (no `pyproject.toml` or `package.json` at expected paths due to `.jinja` suffixes)
- In generated projects: both set to `true` (normal development experience)

## Validation Strategy

### Local self-build

```bash
copier copy --defaults --vcs-ref HEAD ./ ./build
cd build && docker compose up
```

- `build/` is gitignored
- Default values must produce a working project

### CI pipeline

New workflow `.github/workflows/validate-template.yml`:

1. Check out the repo
2. Install copier
3. Run `copier copy --defaults --vcs-ref HEAD ./ ./build`
4. Inside `./build`:
   - Run backend linting and tests
   - Run frontend linting and tests
5. Triggers on push to `main` and on PRs

This ensures every change to the template still produces a valid, passing project.

## New Files

| File | Purpose |
|---|---|
| `copier.yml` | Template configuration, questions, exclusions |
| `.github/workflows/validate-template.yml` | CI validation of template output |
| `.gitignore` update | Add `build/` entry |
