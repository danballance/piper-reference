# Clean Architecture Todo Reference App

## Purpose

A reference Litestar application demonstrating clean architecture with domain-scoped vertical modules, Protocol-based interfaces, and Import Linter enforcement. The domain is a simple todo app defined by an existing OpenAPI schema (`schema/openapi.json`).

## Decisions

- **Persistence**: In-memory storage via repository Protocol (swappable later)
- **Architecture**: Full Protocol-per-layer with 4 layers per domain module
- **Domains**: `todo` (fully implemented), `user` (stub only for multi-domain demonstration)
- **Enforcement**: Import Linter contracts enforce layer boundaries and domain independence
- **Models**: Pydantic BaseModel, full typing, pytest function-style tests

## Project Structure

```
src/
└── app/
    ├── __init__.py
    ├── main.py                        # App factory, DI composition root
    ├── todo/
    │   ├── __init__.py
    │   ├── domain/
    │   │   ├── __init__.py
    │   │   ├── models.py              # TodoItem (Pydantic BaseModel)
    │   │   └── protocols.py           # TodoRepository Protocol
    │   ├── application/
    │   │   ├── __init__.py
    │   │   ├── protocols.py           # TodoService Protocol
    │   │   └── services.py            # TodoServiceImpl
    │   ├── infrastructure/
    │   │   ├── __init__.py
    │   │   └── memory_repo.py         # InMemoryTodoRepository
    │   └── presentation/
    │       ├── __init__.py
    │       └── controllers.py         # TodoController (Litestar)
    ├── user/
    │   ├── __init__.py
    │   └── domain/
    │       ├── __init__.py
    │       └── models.py              # User stub model
    └── shared/
        ├── __init__.py
        └── types.py                   # Common types if needed
tests/
├── __init__.py
├── todo/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   └── test_models.py
│   ├── application/
│   │   ├── __init__.py
│   │   └── test_services.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   └── test_memory_repo.py
│   └── presentation/
│       ├── __init__.py
│       └── test_controllers.py
└── user/
    ├── __init__.py
    └── domain/
        ├── __init__.py
        └── test_models.py
```

## Architecture

### Layer Rules

Dependencies flow inward only: presentation -> application -> domain. Infrastructure depends on domain only. The composition root (`main.py`) is the single place that knows about all concrete implementations.

### Domain Layer (`todo/domain/`)

Defines the core model and the repository port.

**`models.py`** - TodoItem with `title: str` and `done: bool` as a Pydantic BaseModel.

**`protocols.py`** - TodoRepository Protocol:
- `get_all(done: bool | None = None) -> list[TodoItem]`
- `add(item: TodoItem) -> list[TodoItem]`
- `update(item_title: str, item: TodoItem) -> list[TodoItem]`

The repository Protocol lives in domain because inner layers define what they need (Dependency Inversion Principle). This allows application to reference the interface without importing infrastructure.

### Application Layer (`todo/application/`)

**`protocols.py`** - TodoService Protocol with the same method signatures as the repository. Exists so presentation depends on an abstraction.

**`services.py`** - TodoServiceImpl takes a TodoRepository via constructor injection. For this reference app, it delegates directly to the repository. In a real app, business logic and cross-repository orchestration would live here.

### Infrastructure Layer (`todo/infrastructure/`)

**`memory_repo.py`** - InMemoryTodoRepository stores items in a `list[TodoItem]`. Implements TodoRepository Protocol structurally. Returns copies of the internal list to prevent external mutation.

### Presentation Layer (`todo/presentation/`)

**`controllers.py`** - TodoController extends Litestar's Controller. Maps HTTP endpoints to service calls:
- `GET /` with optional `?done=` filter -> `service.get_all(done)`
- `POST /` with TodoItem body -> `service.add(item)`
- `PUT /{item_title}` with TodoItem body -> `service.update(item_title, item)`

Litestar DI injects the TodoService Protocol by parameter name.

### Composition Root (`main.py`)

App factory function `create_app()` wires concrete implementations:
1. Creates `InMemoryTodoRepository`
2. Creates `TodoServiceImpl(repository=...)`
3. Registers as Litestar dependency provider
4. Returns configured Litestar app with TodoController

### User Domain (`user/`)

Stub only: a `User` Pydantic model with basic fields. Demonstrates that the architecture supports multiple domain modules without implementing full CRUD.

## Import Linter Contracts

- **Layer contract per domain**: `presentation -> application -> domain` (no skipping, no reversals)
- **Infrastructure isolation**: `infrastructure` can only import from `domain`
- **Domain independence**: `todo.domain` cannot import `user.domain` and vice versa
- **Framework confinement**: `litestar` imports only in `presentation` and `main.py`

## API Surface (from OpenAPI schema)

| Method | Path | Request Body | Response | Description |
|--------|------|-------------|----------|-------------|
| GET | `/` | - | `TodoItem[]` | List todos, optional `?done=bool` filter |
| POST | `/` | `TodoItem` | `TodoItem[]` | Add todo, returns full list |
| PUT | `/{item_title}` | `TodoItem` | `TodoItem[]` | Update todo by title, returns full list |

## Testing Strategy

- **Domain tests**: Validate model construction and constraints
- **Application tests**: Test services with mock repositories (using Protocol)
- **Infrastructure tests**: Test InMemoryTodoRepository behavior directly
- **Presentation tests**: Use Litestar test client for HTTP-level integration tests
- All tests use pytest function-style, no TestClass
