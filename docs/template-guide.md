# Template Guide

How to use and maintain this copier template.

## Creating a New Project

```bash
copier copy https://github.com/your-org/piper-reference.git ./my-project
```

Copier will prompt for:

| Variable | Description | Default |
|---|---|---|
| `project_name` | Kebab-case identifier (e.g. `my-web-app`) | `piper-reference` |
| `project_description` | Short description | `A full-stack web application` |
| `python_package_name` | Snake_case Python package name (auto-derived) | `my_web_app` |
| `author_name` | Author full name | `Anoni Mouse` |
| `author_email` | Author email | `nixprivacy@pm.me` |
| `include_examples` | Include todo/user feature modules | `true` |

To skip prompts and use all defaults:

```bash
copier copy --defaults https://github.com/your-org/piper-reference.git ./my-project
```

To override specific values:

```bash
copier copy --data project_name=my-app --data include_examples=false https://github.com/your-org/piper-reference.git ./my-project
```

## Updating an Existing Project

When the template evolves (new dependencies, improved CI, architectural changes), pull those changes into an existing project:

```bash
cd my-project
copier update
```

Copier uses a 3-way merge:

1. Renders the template at the **old version** (from `.copier-answers.yml`) with old answers
2. Renders the template at the **new version** (latest git tag) with current answers
3. Computes the diff and applies it to your project files

Your project-specific changes (new features, custom routes, modified configs) survive the merge. Where both the template and your project changed the same lines, standard git conflict markers appear — resolve them as you would any merge conflict.

The `.copier-answers.yml` file in generated projects tracks the template source and version. Never edit it manually.

### Version tags

Copier update requires git tags on the template repo. Tag releases with semver:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Validating the Template

The template repo is not directly runnable (config files have `.jinja` suffixes). Validate it by generating a project and testing the output.

### Local validation

```bash
# Generate with defaults (include_examples=true)
copier copy --defaults --trust --vcs-ref HEAD ./ ./build
cd build/backend && uv sync && uv run pytest -v
cd ../..

# Generate without examples
rm -rf build
copier copy --defaults --data include_examples=false --trust --vcs-ref HEAD ./ ./build
cd build/backend && uv sync && uv run pytest -v
cd ../..

# Clean up
rm -rf build
```

### CI validation

The `.github/workflows/validate-template.yml` workflow runs automatically on pushes to `main` and on PRs. It generates a project from defaults and runs backend tests and linting.

## Template Architecture

### How it works

- `copier.yml` at the repo root defines template variables and file exclusions
- Files with `.jinja` suffix are processed through Jinja2 during `copier copy` — the suffix is stripped in the output
- Files without `.jinja` suffix are copied verbatim
- `_exclude` patterns in `copier.yml` prevent template-only files from appearing in generated projects

### Templatized files

These files contain `{{ variable }}` expressions or `{% if %}` conditionals:

| Template file | What's substituted |
|---|---|
| `backend/pyproject.toml.jinja` | Project name, description, author; conditional import-linter contracts |
| `backend/api/main.py.jinja` | Conditional example feature wiring |
| `backend/slumber.yml.jinja` | Project name; conditional example requests |
| `ui/package.json.jinja` | Project name |
| `ui/index.html.jinja` | Project name in title |
| `ui/src/routes/index.tsx.jinja` | Project name in heading; conditional todo UI vs welcome page |
| `docs/system-guide.md.jinja` | Project name |
| `README.md.jinja` | Project name, description |
| `devenv.nix.jinja` | Copied as-is (the `.jinja` suffix prevents devenv from loading it in the template repo) |

### Files excluded from generated projects

| Pattern | Reason |
|---|---|
| `copier.yml` | Template config — not needed in projects |
| `build/` | Local validation output |
| `tasks/plans/2026-*-copier-*` | Template design/plan docs |
| `.github/workflows/validate-template.yml` | Template CI — not needed in projects |
| `backend/api/todo/`, `backend/api/user/`, etc. | Conditionally excluded when `include_examples` is false |

### The `include_examples` flag

When `true` (default): generated projects include the todo and user feature modules with full tests — useful for learning the architecture patterns.

When `false`: generates a clean skeleton with an empty Litestar app and a welcome page. The architecture scaffolding (`api/shared/`, `docs/`, testing infrastructure) is still present.

## Making Template Changes

1. Edit the `.jinja` files or add new files
2. If adding a new templatized file, rename it with `.jinja` suffix
3. If adding template-only files, add them to `_exclude` in `copier.yml`
4. Validate locally (see above)
5. Commit and tag a new version
