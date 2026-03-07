## Project layout

├── backend/
│   ├── api/
│   ├── tests/
│   ├── pyproject.toml
│   ├── uv.lock
│   └── Dockerfile
├── ui/
│   ├── src/
│   ├── biome.json
│   ├── package.json
│   └── Dockerfile
├── schema/
│   └── openapi.json
├── tasks/
│   ├── designs/
│   ├── ideas/
│   ├── plans/
│   └── TODO.md
├── docs/
└── docker-compose.yml

Note: Be sure to create all design and planning documents in the
`/tasks/plans` and `/tasks/designs` directories, not `/docs`.

## Coding Standards

### Python

- All code must be covered by unit tests.
- Unit tests are written with pytest in the function-style (not TestClass style).
- Interfaces are critically important in software development.
- Remember SOLID.
- Implemement interfaces using Protocol classes.
- Avoid bare functions - instead think of methods attached to Protocols
- Interfaces using Protocols means we get plugins, i.e. Open for extension, closed for modification.
- Every parameter, field and retuen type must be fully typed using the typing module.
- Avoid vague types like dict and prefer TypedDict or dedicated classes.
- Use Pydantic BaseModel classes instead of dataclasses.
- Aim for elegant, composable, orthogonal, pluggable BaseModeligns.
- Avoid complexity - complexity is the software killer.
- Never use the `global` keyword.
- Never re-export as "all" from `__init__.py`.
- Import from package submodules and never `from {package} import *`.
- Only import from the top of the module - never inline within a code block.

### Linting

You can't run individual linters - they are wrapped behind the `piper` tool. Use these commands instead:

```shell
# Python (backend)
uvx piper-py -d ./backend check fast        # light linting checks for fast iteration
uvx piper-py -d ./backend check strict      # full linting checks - run at end of a feature
uvx piper-py -d ./backend check type        # check typing (with ty)
uvx piper-py -d ./backend check complexity  # check cognitive complexity (with complexipy)
uvx piper-py -d ./backend format            # format code (with ruff)

# TypeScript (frontend)
npx piper-ts -d ./ui check fast             # light linting checks
```
