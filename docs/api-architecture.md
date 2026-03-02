# API Architecture Guide

## Overview

The backend is a **Litestar** ASGI application using **Clean Architecture** with SOLID principles. Code is organized into feature modules (bounded contexts), each with four layers that enforce a strict inward dependency rule.

## Module Structure

```
api/
├── main.py                          # Composition root
├── shared/                          # Cross-cutting utilities
├── <feature>/                       # One directory per bounded context
│   ├── domain/
│   │   ├── models.py                # Pydantic entities
│   │   └── protocols.py             # Repository interfaces
│   ├── application/
│   │   ├── protocols.py             # Service interfaces
│   │   └── services.py              # Use-case orchestration
│   ├── infrastructure/
│   │   └── <impl>_repo.py           # Concrete repository
│   └── presentation/
│       └── controllers.py           # HTTP endpoints
```

Each feature (e.g. `todo/`, `user/`) is self-contained. Add new features by copying this structure.

## Layer Responsibilities and Dependency Flow

```
Presentation ──▶ Application Protocol ──▶ Domain Protocol
                                                ▲
Infrastructure ─────────────────────────────────┘
```

| Layer | Owns | Depends on |
|---|---|---|
| **Domain** | Models, repository protocols | Nothing |
| **Application** | Service protocols, service implementations | Domain |
| **Infrastructure** | Concrete repositories | Domain |
| **Presentation** | Controllers, HTTP routing | Application protocols, Domain models |

All cross-layer references point **inward** toward the domain. Infrastructure implements domain protocols but never imports application or presentation.

## Protocol-First Interfaces

Every boundary is defined by a `@runtime_checkable` Protocol class. Implementations declare conformance by inheriting the protocol:

```python
# domain/protocols.py
@runtime_checkable
class TodoRepositoryProtocol(Protocol):
    def get_all(self, done: bool | None = None) -> list[TodoItem]: ...
    def add(self, todo: TodoItem) -> list[TodoItem]: ...

# infrastructure/memory_repo.py
class InMemoryTodoRepository(TodoRepositoryProtocol):
    ...
```

Each layer has its own protocol file. The application layer protocol mirrors the domain layer protocol but exists as a separate abstraction so the presentation layer depends only on the application boundary.

## Models

Domain entities are **immutable Pydantic BaseModels**:

```python
class TodoItem(BaseModel, frozen=True):
    title: str
    done: bool
```

- `frozen=True` enforces immutability.
- Use `BaseModel` (not dataclasses).
- Use `TypedDict` or dedicated classes instead of bare `dict`.

## Composition Root

`api/main.py` wires all concrete implementations and registers them with Litestar's DI:

```python
def create_app() -> Litestar:
    repository = InMemoryTodoRepository()
    service = TodoService(repository=repository)

    return Litestar(
        route_handlers=[TodoController],
        dependencies={"service": Provide(lambda: service, sync_to_thread=False)},
    )
```

Controllers receive dependencies by declaring protocol-typed parameters. Litestar resolves them automatically.

## Controllers

Controllers extend Litestar's `Controller` and declare async handlers. Dependencies are injected as method parameters typed to their protocol:

```python
class TodoController(Controller):
    path = "/"

    @get()
    async def get_list(self, service: TodoServiceProtocol,
                       done: bool | None = None) -> list[TodoItem]:
        return service.get_all(done)
```

## Testing Conventions

Test structure mirrors source structure:

```
tests/
├── todo/
│   ├── domain/test_models.py
│   ├── application/test_services.py
│   ├── infrastructure/test_memory_repo.py
│   └── presentation/test_controllers.py
```

Rules:
- **Function-style pytest** only (no `TestClass`).
- **Fakes over mocks** — write minimal classes that satisfy the protocol.
- **Each layer tested in isolation** — services get a `FakeRepository`, controllers get a `FakeService`.
- Controller tests use Litestar's `TestClient` with fake dependencies injected via `Provide`.

## Coding Style

- Every parameter, field, and return type is fully typed.
- No bare `dict` — use `TypedDict` or a model.
- No `global` keyword.
- No `Any` types.
- Methods belong to Protocol-backed classes, not bare functions.
- Repositories return copies of internal collections to prevent external mutation.
