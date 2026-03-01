# Clean Architecture Todo Reference App — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reference Litestar todo API demonstrating clean architecture with domain-scoped vertical modules, Protocol-per-layer interfaces, in-memory persistence, and Import Linter enforcement.

**Architecture:** Four layers per domain module (domain -> application -> infrastructure -> presentation) with Protocols at each boundary. Dependency Inversion Principle: inner layers define Protocols, outer layers implement them. A single composition root in `main.py` wires concrete implementations via Litestar DI.

**Tech Stack:** Python 3.12+, Litestar 2.15+, Pydantic BaseModel, pytest, import-linter

---

### Task 1: Project scaffolding — directories and dev dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: all `__init__.py` files for the package tree
- Create: `src/app/__init__.py`, `src/app/main.py` (empty placeholder)

**Step 1: Add dev dependencies to pyproject.toml**

Add `pytest`, `import-linter`, and `httpx` (for Litestar test client) to dev dependencies:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
    "import-linter>=2.7,<3.0",
    "httpx>=0.27,<1.0",
]
```

**Step 2: Create the full directory tree**

Run:
```bash
mkdir -p src/app/todo/domain src/app/todo/application src/app/todo/infrastructure src/app/todo/presentation
mkdir -p src/app/user/domain
mkdir -p src/app/shared
mkdir -p tests/todo/domain tests/todo/application tests/todo/infrastructure tests/todo/presentation
mkdir -p tests/user/domain
```

**Step 3: Create all `__init__.py` files**

Create empty `__init__.py` in every package directory:
- `src/app/__init__.py`
- `src/app/todo/__init__.py`
- `src/app/todo/domain/__init__.py`
- `src/app/todo/application/__init__.py`
- `src/app/todo/infrastructure/__init__.py`
- `src/app/todo/presentation/__init__.py`
- `src/app/user/__init__.py`
- `src/app/user/domain/__init__.py`
- `src/app/shared/__init__.py`
- `tests/__init__.py`
- `tests/todo/__init__.py`
- `tests/todo/domain/__init__.py`
- `tests/todo/application/__init__.py`
- `tests/todo/infrastructure/__init__.py`
- `tests/todo/presentation/__init__.py`
- `tests/user/__init__.py`
- `tests/user/domain/__init__.py`

**Step 4: Install dev dependencies**

Run: `uv sync --extra dev`

**Step 5: Verify pytest runs**

Run: `pytest --co -q`
Expected: "no tests ran" (no errors)

**Step 6: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "scaffold: add directory structure and dev dependencies"
```

---

### Task 2: Todo domain model — TodoItem

**Files:**
- Create: `src/app/todo/domain/models.py`
- Create: `tests/todo/domain/test_models.py`

**Step 1: Write the failing tests**

```python
# tests/todo/domain/test_models.py
from app.todo.domain.models import TodoItem


def test_todo_item_creation() -> None:
    item = TodoItem(title="Buy milk", done=False)
    assert item.title == "Buy milk"
    assert item.done is False


def test_todo_item_done_flag() -> None:
    item = TodoItem(title="Walk dog", done=True)
    assert item.done is True


def test_todo_item_is_immutable() -> None:
    """TodoItem should be a frozen Pydantic model."""
    import pytest

    item = TodoItem(title="Test", done=False)
    with pytest.raises(Exception):
        item.title = "Changed"  # type: ignore[misc]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/todo/domain/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.todo.domain.models'`

**Step 3: Write minimal implementation**

```python
# src/app/todo/domain/models.py
from pydantic import BaseModel


class TodoItem(BaseModel, frozen=True):
    title: str
    done: bool
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/todo/domain/test_models.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/app/todo/domain/models.py tests/todo/domain/test_models.py
git commit -m "feat(todo): add TodoItem domain model"
```

---

### Task 3: Todo domain protocol — TodoRepository

**Files:**
- Create: `src/app/todo/domain/protocols.py`

This is a Protocol definition only — no tests needed for the interface itself. It will be tested through its implementations.

**Step 1: Write the Protocol**

```python
# src/app/todo/domain/protocols.py
from typing import Protocol

from app.todo.domain.models import TodoItem


class TodoRepository(Protocol):
    def get_all(self, done: bool | None = None) -> list[TodoItem]: ...

    def add(self, item: TodoItem) -> list[TodoItem]: ...

    def update(self, item_title: str, item: TodoItem) -> list[TodoItem]: ...
```

**Step 2: Verify imports work**

Run: `python -c "from app.todo.domain.protocols import TodoRepository; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/app/todo/domain/protocols.py
git commit -m "feat(todo): add TodoRepository domain protocol"
```

---

### Task 4: Todo infrastructure — InMemoryTodoRepository

**Files:**
- Create: `src/app/todo/infrastructure/memory_repo.py`
- Create: `tests/todo/infrastructure/test_memory_repo.py`

**Step 1: Write the failing tests**

```python
# tests/todo/infrastructure/test_memory_repo.py
from app.todo.domain.models import TodoItem
from app.todo.infrastructure.memory_repo import InMemoryTodoRepository


def test_get_all_empty() -> None:
    repo = InMemoryTodoRepository()
    assert repo.get_all() == []


def test_add_item() -> None:
    repo = InMemoryTodoRepository()
    result = repo.add(TodoItem(title="Buy milk", done=False))
    assert len(result) == 1
    assert result[0].title == "Buy milk"
    assert result[0].done is False


def test_add_multiple_items() -> None:
    repo = InMemoryTodoRepository()
    repo.add(TodoItem(title="First", done=False))
    result = repo.add(TodoItem(title="Second", done=True))
    assert len(result) == 2


def test_get_all_filter_done() -> None:
    repo = InMemoryTodoRepository()
    repo.add(TodoItem(title="Done task", done=True))
    repo.add(TodoItem(title="Pending task", done=False))
    done_items = repo.get_all(done=True)
    assert len(done_items) == 1
    assert done_items[0].title == "Done task"


def test_get_all_filter_not_done() -> None:
    repo = InMemoryTodoRepository()
    repo.add(TodoItem(title="Done task", done=True))
    repo.add(TodoItem(title="Pending task", done=False))
    pending_items = repo.get_all(done=False)
    assert len(pending_items) == 1
    assert pending_items[0].title == "Pending task"


def test_get_all_no_filter_returns_all() -> None:
    repo = InMemoryTodoRepository()
    repo.add(TodoItem(title="One", done=True))
    repo.add(TodoItem(title="Two", done=False))
    assert len(repo.get_all()) == 2


def test_update_item() -> None:
    repo = InMemoryTodoRepository()
    repo.add(TodoItem(title="Buy milk", done=False))
    result = repo.update("Buy milk", TodoItem(title="Buy milk", done=True))
    assert len(result) == 1
    assert result[0].done is True


def test_update_item_title() -> None:
    repo = InMemoryTodoRepository()
    repo.add(TodoItem(title="Old title", done=False))
    result = repo.update("Old title", TodoItem(title="New title", done=False))
    assert len(result) == 1
    assert result[0].title == "New title"


def test_update_nonexistent_item_raises() -> None:
    import pytest

    repo = InMemoryTodoRepository()
    with pytest.raises(KeyError):
        repo.update("Nonexistent", TodoItem(title="X", done=False))


def test_returned_list_is_a_copy() -> None:
    """Mutating the returned list should not affect internal state."""
    repo = InMemoryTodoRepository()
    repo.add(TodoItem(title="Item", done=False))
    result = repo.get_all()
    result.clear()
    assert len(repo.get_all()) == 1
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/todo/infrastructure/test_memory_repo.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/app/todo/infrastructure/memory_repo.py
from app.todo.domain.models import TodoItem


class InMemoryTodoRepository:
    def __init__(self) -> None:
        self._items: list[TodoItem] = []

    def get_all(self, done: bool | None = None) -> list[TodoItem]:
        if done is None:
            return list(self._items)
        return [item for item in self._items if item.done is done]

    def add(self, item: TodoItem) -> list[TodoItem]:
        self._items.append(item)
        return list(self._items)

    def update(self, item_title: str, item: TodoItem) -> list[TodoItem]:
        for i, existing in enumerate(self._items):
            if existing.title == item_title:
                self._items[i] = item
                return list(self._items)
        raise KeyError(f"Todo item '{item_title}' not found")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/todo/infrastructure/test_memory_repo.py -v`
Expected: 11 passed

**Step 5: Commit**

```bash
git add src/app/todo/infrastructure/memory_repo.py tests/todo/infrastructure/test_memory_repo.py
git commit -m "feat(todo): add InMemoryTodoRepository"
```

---

### Task 5: Todo application protocol — TodoService

**Files:**
- Create: `src/app/todo/application/protocols.py`

Protocol definition only — tested through its implementation.

**Step 1: Write the Protocol**

```python
# src/app/todo/application/protocols.py
from typing import Protocol

from app.todo.domain.models import TodoItem


class TodoService(Protocol):
    def get_all(self, done: bool | None = None) -> list[TodoItem]: ...

    def add(self, item: TodoItem) -> list[TodoItem]: ...

    def update(self, item_title: str, item: TodoItem) -> list[TodoItem]: ...
```

**Step 2: Verify imports work**

Run: `python -c "from app.todo.application.protocols import TodoService; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/app/todo/application/protocols.py
git commit -m "feat(todo): add TodoService application protocol"
```

---

### Task 6: Todo application service — TodoServiceImpl

**Files:**
- Create: `src/app/todo/application/services.py`
- Create: `tests/todo/application/test_services.py`

**Step 1: Write the failing tests**

Tests use a mock repository (a simple class satisfying the Protocol) to test the service in isolation.

```python
# tests/todo/application/test_services.py
from app.todo.domain.models import TodoItem
from app.todo.application.services import TodoServiceImpl


class FakeRepository:
    """Minimal fake satisfying TodoRepository Protocol."""

    def __init__(self) -> None:
        self._items: list[TodoItem] = []

    def get_all(self, done: bool | None = None) -> list[TodoItem]:
        if done is None:
            return list(self._items)
        return [i for i in self._items if i.done is done]

    def add(self, item: TodoItem) -> list[TodoItem]:
        self._items.append(item)
        return list(self._items)

    def update(self, item_title: str, item: TodoItem) -> list[TodoItem]:
        for idx, existing in enumerate(self._items):
            if existing.title == item_title:
                self._items[idx] = item
                return list(self._items)
        raise KeyError(f"Todo item '{item_title}' not found")


def test_service_get_all_delegates_to_repository() -> None:
    repo = FakeRepository()
    repo.add(TodoItem(title="Task", done=False))
    service = TodoServiceImpl(repository=repo)
    result = service.get_all()
    assert len(result) == 1
    assert result[0].title == "Task"


def test_service_get_all_with_filter() -> None:
    repo = FakeRepository()
    repo.add(TodoItem(title="Done", done=True))
    repo.add(TodoItem(title="Pending", done=False))
    service = TodoServiceImpl(repository=repo)
    assert len(service.get_all(done=True)) == 1


def test_service_add_delegates_to_repository() -> None:
    repo = FakeRepository()
    service = TodoServiceImpl(repository=repo)
    result = service.add(TodoItem(title="New", done=False))
    assert len(result) == 1
    assert result[0].title == "New"


def test_service_update_delegates_to_repository() -> None:
    repo = FakeRepository()
    repo.add(TodoItem(title="Old", done=False))
    service = TodoServiceImpl(repository=repo)
    result = service.update("Old", TodoItem(title="Old", done=True))
    assert result[0].done is True
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/todo/application/test_services.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/app/todo/application/services.py
from app.todo.domain.models import TodoItem
from app.todo.domain.protocols import TodoRepository


class TodoServiceImpl:
    def __init__(self, repository: TodoRepository) -> None:
        self._repository: TodoRepository = repository

    def get_all(self, done: bool | None = None) -> list[TodoItem]:
        return self._repository.get_all(done)

    def add(self, item: TodoItem) -> list[TodoItem]:
        return self._repository.add(item)

    def update(self, item_title: str, item: TodoItem) -> list[TodoItem]:
        return self._repository.update(item_title, item)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/todo/application/test_services.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add src/app/todo/application/services.py tests/todo/application/test_services.py
git commit -m "feat(todo): add TodoServiceImpl application service"
```

---

### Task 7: Todo presentation — TodoController

**Files:**
- Create: `src/app/todo/presentation/controllers.py`
- Create: `tests/todo/presentation/test_controllers.py`

**Step 1: Write the failing tests**

Tests use Litestar's test client with a fake service injected via DI.

```python
# tests/todo/presentation/test_controllers.py
from litestar import Litestar
from litestar.di import Provide
from litestar.testing import TestClient

from app.todo.domain.models import TodoItem
from app.todo.presentation.controllers import TodoController


class FakeService:
    """Minimal fake satisfying TodoService Protocol."""

    def __init__(self) -> None:
        self._items: list[TodoItem] = []

    def get_all(self, done: bool | None = None) -> list[TodoItem]:
        if done is None:
            return list(self._items)
        return [i for i in self._items if i.done is done]

    def add(self, item: TodoItem) -> list[TodoItem]:
        self._items.append(item)
        return list(self._items)

    def update(self, item_title: str, item: TodoItem) -> list[TodoItem]:
        for idx, existing in enumerate(self._items):
            if existing.title == item_title:
                self._items[idx] = item
                return list(self._items)
        raise KeyError(f"Todo item '{item_title}' not found")


def _create_test_client() -> TestClient[Litestar]:
    fake_service = FakeService()
    app = Litestar(
        route_handlers=[TodoController],
        dependencies={"service": Provide(lambda: fake_service, sync_to_thread=False)},
    )
    return TestClient(app)


def test_get_list_empty() -> None:
    with _create_test_client() as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == []


def test_add_item() -> None:
    with _create_test_client() as client:
        response = client.post("/", json={"title": "Buy milk", "done": False})
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Buy milk"
        assert data[0]["done"] is False


def test_get_list_after_add() -> None:
    with _create_test_client() as client:
        client.post("/", json={"title": "Task 1", "done": False})
        client.post("/", json={"title": "Task 2", "done": True})
        response = client.get("/")
        assert response.status_code == 200
        assert len(response.json()) == 2


def test_get_list_filter_done() -> None:
    with _create_test_client() as client:
        client.post("/", json={"title": "Done", "done": True})
        client.post("/", json={"title": "Pending", "done": False})
        response = client.get("/", params={"done": True})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Done"


def test_update_item() -> None:
    with _create_test_client() as client:
        client.post("/", json={"title": "Buy milk", "done": False})
        response = client.put("/Buy milk", json={"title": "Buy milk", "done": True})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["done"] is True
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/todo/presentation/test_controllers.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/app/todo/presentation/controllers.py
from litestar import Controller, get, post, put

from app.todo.application.protocols import TodoService
from app.todo.domain.models import TodoItem


class TodoController(Controller):
    path = "/"

    @get()
    async def get_list(
        self,
        service: TodoService,
        done: bool | None = None,
    ) -> list[TodoItem]:
        return service.get_all(done)

    @post(status_code=201)
    async def add_item(
        self,
        service: TodoService,
        data: TodoItem,
    ) -> list[TodoItem]:
        return service.add(data)

    @put("/{item_title:str}")
    async def update_item(
        self,
        service: TodoService,
        item_title: str,
        data: TodoItem,
    ) -> list[TodoItem]:
        return service.update(item_title, data)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/todo/presentation/test_controllers.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add src/app/todo/presentation/controllers.py tests/todo/presentation/test_controllers.py
git commit -m "feat(todo): add TodoController presentation layer"
```

---

### Task 8: Composition root — app factory

**Files:**
- Create: `src/app/main.py`

**Step 1: Write the app factory**

```python
# src/app/main.py
from litestar import Litestar
from litestar.di import Provide

from app.todo.application.services import TodoServiceImpl
from app.todo.infrastructure.memory_repo import InMemoryTodoRepository
from app.todo.presentation.controllers import TodoController


def create_app() -> Litestar:
    repository = InMemoryTodoRepository()
    service = TodoServiceImpl(repository=repository)

    return Litestar(
        route_handlers=[TodoController],
        dependencies={"service": Provide(lambda: service, sync_to_thread=False)},
    )


app = create_app()
```

**Step 2: Verify the app starts**

Run: `python -c "from app.main import app; print(f'Routes: {len(app.routes)}')" `
Expected: prints route count without errors

**Step 3: Commit**

```bash
git add src/app/main.py
git commit -m "feat: add app factory composition root"
```

---

### Task 9: User domain stub

**Files:**
- Create: `src/app/user/domain/models.py`
- Create: `tests/user/domain/test_models.py`

**Step 1: Write the failing test**

```python
# tests/user/domain/test_models.py
from app.user.domain.models import User


def test_user_creation() -> None:
    user = User(username="alice", email="alice@example.com")
    assert user.username == "alice"
    assert user.email == "alice@example.com"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/user/domain/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/app/user/domain/models.py
from pydantic import BaseModel


class User(BaseModel, frozen=True):
    username: str
    email: str
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/user/domain/test_models.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add src/app/user/domain/models.py tests/user/domain/test_models.py
git commit -m "feat(user): add stub User domain model"
```

---

### Task 10: Import Linter configuration

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add Import Linter configuration to pyproject.toml**

Append the following to `pyproject.toml`:

```toml
[tool.importlinter]
root_package = "app"
include_external_packages = true

# Contract 1: Layer architecture within todo domain
[[tool.importlinter.contracts]]
id = "todo-layers"
name = "Todo domain follows layered architecture"
type = "layers"
containers = ["app.todo"]
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
source_modules = ["app.todo.infrastructure"]
forbidden_modules = [
    "app.todo.application",
    "app.todo.presentation",
]

# Contract 3: Domain independence between modules
[[tool.importlinter.contracts]]
id = "domain-independence"
name = "Domain modules are independent of each other"
type = "independence"
modules = [
    "app.todo",
    "app.user",
]

# Contract 4: Domain layer must not import Litestar
[[tool.importlinter.contracts]]
id = "domain-no-framework"
name = "Domain layers must not import framework code"
type = "forbidden"
source_modules = [
    "app.todo.domain",
    "app.user.domain",
]
forbidden_modules = ["litestar"]

# Contract 5: Application layer must not import Litestar
[[tool.importlinter.contracts]]
id = "application-no-framework"
name = "Application layers must not import framework code"
type = "forbidden"
source_modules = ["app.todo.application"]
forbidden_modules = ["litestar"]

# Contract 6: Infrastructure must not import Litestar
[[tool.importlinter.contracts]]
id = "infrastructure-no-framework"
name = "Infrastructure must not import framework code"
type = "forbidden"
source_modules = ["app.todo.infrastructure"]
forbidden_modules = ["litestar"]

# Contract 7: Shared lib must not import domain-specific code
[[tool.importlinter.contracts]]
id = "shared-independence"
name = "Shared cannot import domain-specific code"
type = "forbidden"
source_modules = ["app.shared"]
forbidden_modules = [
    "app.todo",
    "app.user",
]
```

**Step 2: Run Import Linter to verify all contracts pass**

Run: `lint-imports`
Expected: all contracts pass (green checkmarks)

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add Import Linter architecture enforcement"
```

---

### Task 11: Full test suite verification

**Step 1: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass (24 total: 3 model + 11 repo + 4 service + 5 controller + 1 user)

**Step 2: Run Import Linter**

Run: `lint-imports`
Expected: all 7 contracts pass

**Step 3: Verify the app serves requests**

Run:
```bash
litestar --app app.main:app run --port 8080 &
sleep 2
curl -s http://localhost:8080/ | python -m json.tool
curl -s -X POST http://localhost:8080/ -H "Content-Type: application/json" -d '{"title":"Test","done":false}' | python -m json.tool
kill %1
```
Expected: GET returns `[]`, POST returns `[{"title": "Test", "done": false}]`

**Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address issues found during verification"
```
