## Project layout

├── api/
├── docs/
├── schema/
│   └── openapi.json
├── tasks/
│   ├── designs/
│   │   └── task-one-design.md
│   ├── ideas/
│   │   ├── idea.md 
│   ├── plans/
│   │   └── task-one-plan.md
│   └── TODO.md
├── ui/
├── pyprojectject.toml
└── uv.lock

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

### Linting

```shell
piper check fast        # light linting checks for fast iteration
piper check strict      # full linting checks - run at end of a feature
```

