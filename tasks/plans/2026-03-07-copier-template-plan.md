# Copier Template Conversion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the piper-reference project into a copier template that scaffolds new full-stack projects with variable substitution and optional example features.

**Architecture:** Root-level template — `copier.yml` at the repo root, files needing substitution gain `.jinja` suffix, copier's `_exclude` prevents template-only files from being copied. The repo is no longer directly runnable; a self-build step (`copier copy --defaults`) generates a working project into `build/`.

**Tech Stack:** Copier 9.x, Jinja2 templating, GitHub Actions for CI validation.

**Design doc:** `tasks/plans/2026-03-07-copier-template-design.md`

---

## Task 1: Create `copier.yml` and answers template

The foundation — defines all template variables, exclusions, and generates the answers file in target projects.

**Files:**
- Create: `copier.yml`
- Create: `{{ _copier_conf.answers_file }}.jinja`

**Step 1: Create `copier.yml`**

```yaml
# copier.yml
_min_copier_version: "9.0.0"

_exclude:
  - "copier.yml"
  - "{{ _copier_conf.answers_file }}.jinja"
  - "build/"
  - ".copier-answers.yml"
  - "tasks/plans/2026-*-copier-*"
  - "{% if not include_examples %}backend/api/todo{% endif %}"
  - "{% if not include_examples %}backend/api/user{% endif %}"
  - "{% if not include_examples %}backend/tests/todo{% endif %}"
  - "{% if not include_examples %}backend/tests/user{% endif %}"
  - "{% if not include_examples %}ui/src/features{% endif %}"
  - "{% if not include_examples %}ui/tests/components{% endif %}"
  - "{% if not include_examples %}ui/tests/mocks{% endif %}"
  - "{% if not include_examples %}ui/tests/e2e/todo.spec.ts{% endif %}"

project_name:
  type: str
  help: "Project name (kebab-case, e.g. my-web-app)"
  default: "piper-reference"
  validator: "{% if not project_name | regex_search('^[a-z][a-z0-9-]*$') %}Must be kebab-case (lowercase letters, numbers, hyphens){% endif %}"

project_description:
  type: str
  help: "Short project description"
  default: "A full-stack web application"

python_package_name:
  type: str
  help: "Python package name (snake_case, derived from project name)"
  default: "{{ project_name | replace('-', '_') }}"
  validator: "{% if not python_package_name | regex_search('^[a-z][a-z0-9_]*$') %}Must be snake_case{% endif %}"

author_name:
  type: str
  help: "Author full name"
  default: "Anoni Mouse"

author_email:
  type: str
  help: "Author email"
  default: "nixprivacy@pm.me"

include_examples:
  type: bool
  help: "Include example todo/user feature modules?"
  default: true
```

**Step 2: Create answers file template**

Create a file literally named `{{ _copier_conf.answers_file }}.jinja` at the repo root:

```yaml
# Changes here will be overwritten by Copier; DO NOT EDIT
{{ _copier_conf.answers_file_content }}
```

**Step 3: Commit**

```bash
git add copier.yml "{{ _copier_conf.answers_file }}.jinja"
git commit -m "feat: add copier.yml template config and answers template"
```

---

## Task 2: Update `.gitignore` and `devenv.nix`

Add `build/` to `.gitignore` and convert `devenv.nix` to a template that enables sync in generated projects but not in the template repo.

**Files:**
- Modify: `.gitignore`
- Rename + modify: `devenv.nix` -> `devenv.nix.jinja`

**Step 1: Add `build/` to `.gitignore`**

Add this line to `.gitignore` (after the "Worktrees" section):

```
# Copier build output
build/
```

**Step 2: Rename `devenv.nix` to `devenv.nix.jinja`**

```bash
git mv devenv.nix devenv.nix.jinja
```

**Step 3: Edit `devenv.nix.jinja`**

Replace the sync/install enable lines with Jinja conditionals. The template repo has `.jinja`-suffixed config files so uv/pnpm sync would fail. Generated projects have normal filenames so sync should be enabled.

```nix
{ pkgs, ... }: {
  dotenv.enable = true;
  enterShell = ''
    export NPM_CONFIG_PREFIX="$HOME/.npm-global"
    export PATH="$NPM_CONFIG_PREFIX/bin:$PATH"
  '';
  languages.python = {
    enable = true;
    directory = "./backend";
    version = "3.12";
    uv = {
      enable = true;
      sync.enable = true;
    };
  };
  languages.javascript = {
    enable = true;
    pnpm = {
      enable = true;
      install.enable = true;
    };
  };
}
```

Note: The file content stays the same — `sync.enable = true` and `install.enable = true`. In the template repo, these `.jinja` files won't have their normal names (`pyproject.toml`, `package.json`), so devenv's sync will simply find nothing to sync. In generated projects, the files will have their correct names and sync will work normally.

Wait — actually, uv will error if `pyproject.toml` doesn't exist in `./backend`. We need the Jinja conditional after all:

```nix
{ pkgs, ... }: {
  dotenv.enable = true;
  enterShell = ''
    export NPM_CONFIG_PREFIX="$HOME/.npm-global"
    export PATH="$NPM_CONFIG_PREFIX/bin:$PATH"
  '';
  languages.python = {
    enable = true;
    directory = "./backend";
    version = "3.12";
    uv = {
      enable = true;
      sync.enable = {{ "true" if _copier_conf else "false" }};
    };
  };
  languages.javascript = {
    enable = true;
    pnpm = {
      enable = true;
      install.enable = {{ "true" if _copier_conf else "false" }};
    };
  };
}
```

Hmm, this doesn't work — the `.jinja` file in the template repo won't be processed by Jinja (only copier processes it during copy). In the template repo it's just a raw `.jinja` file that devenv won't load.

**Revised approach:** Since `devenv.nix.jinja` won't be loaded by devenv at all (devenv looks for `devenv.nix`), the template repo simply won't have a working devenv. That's fine — the template repo isn't meant to be developed in directly. The generated project gets `devenv.nix` (copier strips the `.jinja` suffix) with `sync.enable = true`, which works because `pyproject.toml` exists there.

So the file content is exactly the original `devenv.nix` — no Jinja expressions needed. The `.jinja` suffix alone solves the problem:
- Template repo: `devenv.nix.jinja` exists → devenv ignores it (not `devenv.nix`) → no sync errors
- Generated project: `devenv.nix` exists → devenv loads it → sync works

```nix
{ pkgs, ... }: {
  dotenv.enable = true;
  enterShell = ''
    export NPM_CONFIG_PREFIX="$HOME/.npm-global"
    export PATH="$NPM_CONFIG_PREFIX/bin:$PATH"
  '';
  languages.python = {
    enable = true;
    directory = "./backend";
    version = "3.12";
    uv = {
      enable = true;
      sync.enable = true;
    };
  };
  languages.javascript = {
    enable = true;
    pnpm = {
      enable = true;
      install.enable = true;
    };
  };
}
```

**Step 4: Commit**

```bash
git add .gitignore devenv.nix.jinja
git commit -m "feat: convert devenv.nix to template and add build/ to gitignore"
```

---

## Task 3: Templatize `backend/pyproject.toml`

Replace hardcoded project metadata and conditionally include import-linter contracts for example features.

**Files:**
- Rename + modify: `backend/pyproject.toml` -> `backend/pyproject.toml.jinja`

**Step 1: Rename file**

```bash
git mv backend/pyproject.toml backend/pyproject.toml.jinja
```

**Step 2: Edit `backend/pyproject.toml.jinja`**

Replace the `[project]` section metadata with Jinja variables. Wrap example-specific import-linter contracts in conditionals.

```toml
[project]
name = "{{ project_name }}"
version = "0.1.0"
description = "{{ project_description }}"
authors = [
    {name = "{{ author_name }}",email = "{{ author_email }}"}
]
requires-python = ">=3.12,<4.0"
dependencies = [
    "litestar[standard] (>=2.15,<3.0.0)",
    "pydantic (>=2.0,<3.0)",
    "python-dotenv (>=1.0,<2.0)",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
    "import-linter>=2.7,<3.0",
    "httpx>=0.27,<1.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["api"]

[tool.pytest.ini_options]
pythonpath = ["."]

[tool.importlinter]
root_package = "api"
include_external_packages = true
{% if include_examples %}

# Contract 1: Layer architecture within todo domain
[[tool.importlinter.contracts]]
id = "todo-layers"
name = "Todo domain follows layered architecture"
type = "layers"
containers = ["api.todo"]
layers = [
    "presentation",
    "application",
    "infrastructure",
    "domain",
]

# Contract 2: Infrastructure only imports domain
[[tool.importlinter.contracts]]
id = "todo-infra-isolation"
name = "Todo infrastructure only imports from domain"
type = "forbidden"
source_modules = ["api.todo.infrastructure"]
forbidden_modules = [
    "api.todo.application",
    "api.todo.presentation",
]

# Contract 3: Domain independence between modules
[[tool.importlinter.contracts]]
id = "domain-independence"
name = "Domain modules are independent of each other"
type = "independence"
modules = [
    "api.todo",
    "api.user",
]

# Contract 4: Domain layer must not import Litestar
[[tool.importlinter.contracts]]
id = "domain-no-framework"
name = "Domain layers must not import framework code"
type = "forbidden"
source_modules = [
    "api.todo.domain",
    "api.user.domain",
]
forbidden_modules = ["litestar"]

# Contract 5: Application layer must not import Litestar
[[tool.importlinter.contracts]]
id = "application-no-framework"
name = "Application layers must not import framework code"
type = "forbidden"
source_modules = ["api.todo.application"]
forbidden_modules = ["litestar"]

# Contract 6: Infrastructure must not import Litestar
[[tool.importlinter.contracts]]
id = "infrastructure-no-framework"
name = "Infrastructure must not import framework code"
type = "forbidden"
source_modules = ["api.todo.infrastructure"]
forbidden_modules = ["litestar"]
{% endif %}

# Shared lib must not import domain-specific code
[[tool.importlinter.contracts]]
id = "shared-independence"
name = "Shared cannot import domain-specific code"
type = "forbidden"
source_modules = ["api.shared"]
forbidden_modules = [
{% if include_examples %}
    "api.todo",
    "api.user",
{% endif %}
]

[tool.ty.environment]
python = "../.devenv/state/venv"

[dependency-groups]
dev = [
    "pytest>=8.4.2",
    "pytest-cov>=7.0.0",
]
```

Note: The `shared-independence` contract is kept unconditionally as it's a useful architectural guard. When examples are excluded, the `forbidden_modules` list is empty — import-linter will accept this as a valid (vacuous) contract.

**Step 3: Commit**

```bash
git add backend/pyproject.toml.jinja
git commit -m "feat: templatize backend pyproject.toml with project metadata and conditional contracts"
```

---

## Task 4: Templatize `backend/api/main.py`

Make the composition root conditionally wire up example features.

**Files:**
- Rename + modify: `backend/api/main.py` -> `backend/api/main.py.jinja`

**Step 1: Rename file**

```bash
git mv backend/api/main.py backend/api/main.py.jinja
```

**Step 2: Edit `backend/api/main.py.jinja`**

```python
from litestar import Litestar
from litestar.di import Provide
from litestar.logging import LoggingConfig
{% if include_examples %}

from api.todo.application.services import TodoService
from api.todo.infrastructure.memory_repo import InMemoryTodoRepository
from api.todo.presentation.controllers import TodoController
{% endif %}


def create_app() -> Litestar:
{% if include_examples %}
    repository = InMemoryTodoRepository()
    service = TodoService(repository=repository)

{% endif %}
    logging_config = LoggingConfig(
        root={"level": "DEBUG", "handlers": ["queue_listener"]},
        formatters={
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        },
        log_exceptions="always",
    )

    return Litestar(
{% if include_examples %}
        route_handlers=[TodoController],
        dependencies={"service": Provide(lambda: service, sync_to_thread=False)},
{% else %}
        route_handlers=[],
{% endif %}
        logging_config=logging_config,
    )


app = create_app()
```

**Step 3: Commit**

```bash
git add backend/api/main.py.jinja
git commit -m "feat: templatize backend main.py with conditional example features"
```

---

## Task 5: Templatize `backend/slumber.yml`

Replace the project name and protect slumber's own `{{ host }}` template expressions from Jinja processing.

**Files:**
- Rename + modify: `backend/slumber.yml` -> `backend/slumber.yml.jinja`

**Step 1: Rename file**

```bash
git mv backend/slumber.yml backend/slumber.yml.jinja
```

**Step 2: Edit `backend/slumber.yml.jinja`**

Use `{% raw %}` blocks to protect slumber's own template syntax. Conditionally include example requests.

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/LucasPickering/slumber/refs/tags/v4.3.1/schemas/collection.json
# ^ This enables schema validation and autocomplete in your editor
# https://github.com/redhat-developer/yaml-language-server

# For basic usage info, see:
# https://slumber.lucaspickering.me/getting_started.html
# For all collection options, see:
# https://slumber.lucaspickering.me/api/request_collection/index.html

name: {{ project_name }}

# Profiles are groups of data you can easily switch between. A common usage is
# to define profiles for various environments of a REST service
profiles:
  local:
    name: Local
    data:
      host: http://localhost:8080
{% if include_examples %}

{% raw %}
requests:
  todo_list:
    name: List items
    method: GET
    url: "{{ host }}/"
  todo_create:
    name: Create item
    method: POST
    url: "{{ host }}/"
    body:
      type: json
      data: { "title": "Item One", "done": false }
{% endraw %}
{% endif %}
```

**Step 3: Commit**

```bash
git add backend/slumber.yml.jinja
git commit -m "feat: templatize slumber.yml with project name and conditional examples"
```

---

## Task 6: Templatize `ui/package.json` and `ui/index.html`

Replace project name in the frontend package config and HTML title.

**Files:**
- Rename + modify: `ui/package.json` -> `ui/package.json.jinja`
- Rename + modify: `ui/index.html` -> `ui/index.html.jinja`

**Step 1: Rename files**

```bash
git mv ui/package.json ui/package.json.jinja
git mv ui/index.html ui/index.html.jinja
```

**Step 2: Edit `ui/package.json.jinja`**

Only the `"name"` field changes:

```json
{
  "name": "{{ project_name }}-ui",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "codegen": "openapi-ts",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "@hookform/resolvers": "^5.2.2",
    "@tailwindcss/vite": "^4.2.1",
    "@tanstack/react-query": "^5.90.21",
    "@tanstack/react-query-devtools": "^5.91.3",
    "@tanstack/react-router": "^1.163.3",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.576.0",
    "radix-ui": "^1.4.3",
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "react-hook-form": "^7.71.2",
    "tailwind-merge": "^3.5.0",
    "tailwindcss": "^4.2.1",
    "zod": "^4.3.6",
    "zustand": "^5.0.11"
  },
  "pnpm": {
    "onlyBuiltDependencies": [
      "esbuild"
    ]
  },
  "devDependencies": {
    "@eslint/js": "^9.39.1",
    "@hey-api/openapi-ts": "^0.93.1",
    "@playwright/test": "^1.58.2",
    "@tanstack/router-devtools": "^1.163.3",
    "@tanstack/router-plugin": "^1.164.0",
    "@types/node": "^24.10.1",
    "@types/react": "^19.2.7",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^5.1.1",
    "@vitest/browser-playwright": "^4.0.18",
    "eslint": "^9.39.1",
    "eslint-plugin-react-hooks": "^7.0.1",
    "eslint-plugin-react-refresh": "^0.4.24",
    "globals": "^16.5.0",
    "playwright": "^1.58.2",
    "shadcn": "^3.8.5",
    "tw-animate-css": "^1.4.0",
    "typescript": "~5.9.3",
    "typescript-eslint": "^8.48.0",
    "vite": "^7.3.1",
    "vite-tsconfig-paths": "^6.1.1",
    "vitest": "^4.0.18",
    "vitest-browser-react": "^2.0.5"
  }
}
```

**Step 3: Edit `ui/index.html.jinja`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{{ project_name }}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**Step 4: Commit**

```bash
git add ui/package.json.jinja ui/index.html.jinja
git commit -m "feat: templatize ui package.json and index.html with project name"
```

---

## Task 7: Templatize `ui/src/routes/index.tsx`

Replace the heading text with the project name. When examples are excluded, show a welcome page instead of the todo UI.

**Files:**
- Rename + modify: `ui/src/routes/index.tsx` -> `ui/src/routes/index.tsx.jinja`

**Step 1: Rename file**

```bash
git mv ui/src/routes/index.tsx ui/src/routes/index.tsx.jinja
```

**Step 2: Edit `ui/src/routes/index.tsx.jinja`**

When `include_examples` is true, the file is essentially the same as the original with the title swapped. When false, it renders a minimal welcome page.

```tsx
{% if include_examples %}
import { createFileRoute } from "@tanstack/react-router";
import {
  useSuspenseQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { Suspense } from "react";
import {
  todoListOptions,
  addItemMutation,
  itemTitleUpdateItemMutation,
} from "@/features/todo/queries";
import { TodoList } from "@/features/todo/components/todo-list";
import { TodoForm } from "@/features/todo/components/todo-form";
import { useTodoFilterStore } from "@/features/todo/store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const Route = createFileRoute("/")({
  loader: ({ context }) =>
    context.queryClient.ensureQueryData(todoListOptions()),
  component: IndexPage,
});

function IndexPage() {
  return (
    <div className="container mx-auto max-w-2xl p-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">{{ project_name }} — Todos</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <Suspense fallback={<div>Loading...</div>}>
            <TodoContent />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}

function TodoContent() {
  const queryClient = useQueryClient();
  const { data: todos = [] } = useSuspenseQuery(todoListOptions());
  const { filter, setFilter } = useTodoFilterStore();

  const addMutation = useMutation({
    ...addItemMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: todoListOptions().queryKey });
    },
  });

  const toggleMutation = useMutation({
    ...itemTitleUpdateItemMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: todoListOptions().queryKey });
    },
  });

  const handleAdd = (title: string) => {
    addMutation.mutate({
      body: { title, done: false },
    });
  };

  const handleToggle = (title: string) => {
    const todo = todos.find((t) => t.title === title);
    if (!todo) return;
    toggleMutation.mutate({
      path: { item_title: title },
      body: { title, done: !todo.done },
    });
  };

  return (
    <>
      <TodoForm onSubmit={handleAdd} />

      <div className="flex gap-2">
        <FilterButton
          label="All"
          value="all"
          current={filter}
          onClick={setFilter}
        />
        <FilterButton
          label="Done"
          value="done"
          current={filter}
          onClick={setFilter}
        />
        <FilterButton
          label="Not Done"
          value="not-done"
          current={filter}
          onClick={setFilter}
        />
      </div>

      <TodoList todos={todos} filter={filter} onToggle={handleToggle} />

      {addMutation.isError && (
        <p className="text-sm text-destructive">Failed to add todo</p>
      )}
      {toggleMutation.isError && (
        <p className="text-sm text-destructive">Failed to update todo</p>
      )}
    </>
  );
}

function FilterButton({
  label,
  value,
  current,
  onClick,
}: {
  label: string;
  value: "all" | "done" | "not-done";
  current: string;
  onClick: (filter: "all" | "done" | "not-done") => void;
}) {
  return (
    <Button
      variant={current === value ? "default" : "outline"}
      size="sm"
      onClick={() => onClick(value)}
    >
      {label}
    </Button>
  );
}
{% else %}
import { createFileRoute } from "@tanstack/react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const Route = createFileRoute("/")({
  component: IndexPage,
});

function IndexPage() {
  return (
    <div className="container mx-auto max-w-2xl p-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">{{ project_name }}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Welcome to your new project. Start building!
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
{% endif %}
```

**Step 3: Commit**

```bash
git add ui/src/routes/index.tsx.jinja
git commit -m "feat: templatize index route with project name and conditional todo UI"
```

---

## Task 8: Templatize `docs/system-guide.md` and `README.md`

Replace project name references in documentation.

**Files:**
- Rename + modify: `docs/system-guide.md` -> `docs/system-guide.md.jinja`
- Rename + modify: `README.md` -> `README.md.jinja`

**Step 1: Rename files**

```bash
git mv docs/system-guide.md docs/system-guide.md.jinja
git mv README.md README.md.jinja
```

**Step 2: Edit `docs/system-guide.md.jinja`**

The only project-specific reference is `cd piper-reference` on line 58. Replace it:

Find: `cd piper-reference`
Replace with: `cd {{ project_name }}`

Keep everything else identical. This file also uses backtick-wrapped `{repo}` placeholders in the Railway section — those are documentation placeholders, not Jinja, so they're fine.

**Step 3: Edit `README.md.jinja`**

The current README is empty. Create a useful starter:

```markdown
# {{ project_name }}

{{ project_description }}

## Getting Started

This project uses [devenv](https://devenv.sh/) for reproducible development environments.

```bash
cd {{ project_name }}
direnv allow   # first time only
```

See [docs/system-guide.md](docs/system-guide.md) for full setup instructions.
```

**Step 4: Commit**

```bash
git add docs/system-guide.md.jinja README.md.jinja
git commit -m "feat: templatize system guide and README with project name"
```

---

## Task 9: Local validation — defaults (include_examples=true)

Test that `copier copy` with default answers produces a working project.

**Step 1: Install copier (if not already available)**

```bash
uvx copier --version
```

If not installed via uvx, use: `pip install copier` or `nix shell nixpkgs#copier`.

**Step 2: Run copier copy with defaults**

```bash
copier copy --defaults --vcs-ref HEAD ./ ./build
```

**Step 3: Verify generated files exist with correct names**

```bash
ls build/devenv.nix              # should exist (no .jinja suffix)
ls build/backend/pyproject.toml  # should exist
ls build/ui/package.json         # should exist
ls build/ui/index.html           # should exist
ls build/.copier-answers.yml     # should exist
```

**Step 4: Verify variable substitution worked**

```bash
grep 'name = "piper-reference"' build/backend/pyproject.toml    # should match (default value)
grep '"name": "piper-reference-ui"' build/ui/package.json        # should match
grep '<title>piper-reference</title>' build/ui/index.html        # should match
grep 'Anoni Mouse' build/backend/pyproject.toml                  # should match
```

**Step 5: Verify excluded files are NOT present**

```bash
test ! -f build/copier.yml                                       # should not exist
test ! -f build/tasks/plans/2026-03-07-copier-template-design.md # should not exist
```

**Step 6: Verify example features ARE present (default is true)**

```bash
ls build/backend/api/todo/domain/models.py      # should exist
ls build/ui/src/features/todo/queries.ts         # should exist
```

**Step 7: Run backend tests in the generated project**

```bash
cd build/backend && uv sync && uv run pytest -v
```

Expected: All tests pass.

**Step 8: Clean up**

```bash
rm -rf build
```

---

## Task 10: Local validation — no examples (include_examples=false)

Test that copier correctly excludes example features.

**Step 1: Run copier with examples disabled**

```bash
copier copy --defaults --data include_examples=false --vcs-ref HEAD ./ ./build
```

**Step 2: Verify example files are excluded**

```bash
test ! -d build/backend/api/todo       # should not exist
test ! -d build/backend/api/user       # should not exist
test ! -d build/backend/tests/todo     # should not exist
test ! -d build/ui/src/features        # should not exist
test ! -d build/ui/tests/components    # should not exist
```

**Step 3: Verify main.py has empty route handlers**

```bash
grep 'route_handlers=\[\]' build/backend/api/main.py   # should match
```

**Step 4: Verify index.tsx has welcome page**

```bash
grep 'Welcome to your new project' build/ui/src/routes/index.tsx   # should match
```

**Step 5: Verify pyproject.toml has no todo contracts**

```bash
grep -c 'todo-layers' build/backend/pyproject.toml   # should be 0
```

**Step 6: Verify shared-independence contract exists but with empty forbidden_modules**

```bash
grep 'shared-independence' build/backend/pyproject.toml   # should match
```

**Step 7: Clean up**

```bash
rm -rf build
```

---

## Task 11: Create CI validation workflow

Add a GitHub Actions workflow that builds from defaults and runs tests.

**Files:**
- Create: `.github/workflows/validate-template.yml`

**Step 1: Create the workflow**

```yaml
name: Validate Template

on:
  push:
    branches:
      - main
  pull_request:

jobs:
  validate:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install copier
        run: pip install copier

      - name: Generate project from template
        run: copier copy --defaults --trust --vcs-ref HEAD ./ ./build

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install backend dependencies
        run: cd build/backend && uv sync

      - name: Run backend tests
        run: cd build/backend && uv run pytest -v

      - name: Run backend linting
        run: uvx piper-py -d ./build/backend check fast

      - name: Install pnpm
        uses: pnpm/action-setup@v4
        with:
          version: latest

      - name: Install Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: build/ui/pnpm-lock.yaml

      - name: Install frontend dependencies
        run: cd build/ui && pnpm install --frozen-lockfile

      - name: Run frontend linting
        run: npx piper-ts -d ./build/ui check fast
```

Note: The existing `publish-image.yml` and `publish-ui-image.yml` workflows need their `_exclude` entry in `copier.yml` reviewed — they should be included in generated projects. The `validate-template.yml` should be excluded (it's only for the template repo). Add to `copier.yml` `_exclude`:

```yaml
  - ".github/workflows/validate-template.yml"
```

**Step 2: Update `copier.yml` to exclude the validation workflow**

Add this line to the `_exclude` list in `copier.yml`:

```yaml
  - ".github/workflows/validate-template.yml"
```

**Step 3: Commit**

```bash
git add .github/workflows/validate-template.yml copier.yml
git commit -m "feat: add CI workflow to validate template generates a working project"
```

---

## Task 12: Final validation and commit

Run the full validation locally one more time, ensure everything works end-to-end.

**Step 1: Generate with defaults**

```bash
copier copy --defaults --trust --vcs-ref HEAD ./ ./build
```

**Step 2: Run Docker Compose in the generated project**

```bash
cd build && docker compose up --build -d
```

Wait for services to start, then:

```bash
curl http://localhost:3000        # should return the frontend HTML
curl http://localhost:3000/api/   # should return the API response (empty todo list)
```

**Step 3: Tear down**

```bash
docker compose down -v
cd .. && rm -rf build
```

**Step 4: Generate without examples and verify**

```bash
copier copy --defaults --data include_examples=false --trust --vcs-ref HEAD ./ ./build
cd build/backend && uv sync && uv run pytest -v
cd ../.. && rm -rf build
```

**Step 5: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: address issues found during final template validation"
```

---

## Summary of all file changes

| Action | File |
|---|---|
| Create | `copier.yml` |
| Create | `{{ _copier_conf.answers_file }}.jinja` |
| Create | `.github/workflows/validate-template.yml` |
| Modify | `.gitignore` (add `build/`) |
| Rename | `devenv.nix` -> `devenv.nix.jinja` |
| Rename | `backend/pyproject.toml` -> `backend/pyproject.toml.jinja` |
| Rename | `backend/api/main.py` -> `backend/api/main.py.jinja` |
| Rename | `backend/slumber.yml` -> `backend/slumber.yml.jinja` |
| Rename | `ui/package.json` -> `ui/package.json.jinja` |
| Rename | `ui/index.html` -> `ui/index.html.jinja` |
| Rename | `ui/src/routes/index.tsx` -> `ui/src/routes/index.tsx.jinja` |
| Rename | `docs/system-guide.md` -> `docs/system-guide.md.jinja` |
| Rename | `README.md` -> `README.md.jinja` |

**Files NOT templatized** (confirmed no project-specific content):
- `CLAUDE.md` — coding standards are generic
- `docs/api-architecture.md` — architecture patterns are generic
- `docs/ui-architecture.md` — architecture patterns are generic
- `ui/src/routes/__root.tsx` — no example-specific imports
- `docker-compose.yml` — ports/services are part of the opinionated stack
- `.github/workflows/publish-image.yml` — uses `${{ github.repository }}` already
- `.github/workflows/publish-ui-image.yml` — uses `${{ github.repository }}` already
