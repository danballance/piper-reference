# copier-upstream

Selectively upstream changes from a downstream copier project back to this template.

## Problem

When you fix or improve files in a project generated from this copier template, those changes need to be manually backported to the template. This involves reverse-substituting template variables (`piper-reference` back to `{{ project_name }}`), renaming `.jinja` extensions, and placing files in the correct `_template/` subdirectory. `copier-upstream` automates this.

## Usage

Run from the template repo root, pointing at the downstream project:

```shell
uv run scripts/upstream.py ~/Code/python/make-me-a-playlist
```

The script will:

1. Read `copier.yml` and the downstream project's `.copier-answers.yml`
2. Compare all template files against their downstream counterparts
3. Present an interactive checkbox list of changed files
4. For selected files: reverse-substitute expanded values back to Jinja tags, then write to `_template/`

### Interactive selection

Use arrow keys to navigate, space to toggle files, and enter to confirm:

```
? Select files to upstream:
> [ ] backend/pyproject.toml        (modified)
  [x] docker-compose.yml            (modified)
  [x] .pi/skills/litestar/SKILL.md  (modified)
  [ ] ui/package.json               (modified)
```

## How re-templating works

The script reads `.copier-answers.yml` to build a substitution map. For example, if the answers contain:

```yaml
project_name: make-me-a-playlist
python_package_name: make_me_a_playlist
author_name: Anoni Mouse
```

Then when upstreaming a file, every occurrence of `make-me-a-playlist` is replaced with `{{ project_name }}`, `make_me_a_playlist` with `{{ python_package_name }}`, etc.

Substitutions are applied longest-first to prevent partial matches (e.g., `make_me_a_playlist` is replaced before `make`).

### `.jinja` files

Files that have a `.jinja` extension in the template (like `README.md.jinja`) are mapped to their extension-stripped counterpart in the downstream project (`README.md`). When upstreamed, the content is re-templated and written back to the `.jinja` path.

### Binary files

Binary files (detected via null-byte heuristic) are copied as-is without re-templating.

## Requirements

- [uv](https://docs.astral.sh/uv/) (handles dependencies automatically via PEP 723 inline metadata)
- `git` (used to enumerate template files while respecting `.gitignore`)
- No manual `pip install` needed -- `uv run` resolves `pyyaml` and `questionary` automatically

## Limitations

- **False substitutions possible.** If a downstream file happens to contain a string matching an answer value in an unintended location (e.g., the project name appears in a comment), it will be re-templated. Review the diff after upstreaming.

## Running tests

```shell
uv run --with pytest --with pyyaml --with questionary pytest scripts/tests/ -v
```
