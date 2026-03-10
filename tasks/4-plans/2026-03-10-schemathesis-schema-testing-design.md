# Schemathesis Schema Testing Design

Date: 2026-03-10

## Goal

Add property-based API schema testing using Schemathesis to automatically
validate that API responses conform to the OpenAPI specification.

## Decisions

### Testing mode: ASGI in-process

Use `schemathesis.openapi.from_asgi()` to test the app directly without
starting a server. The `create_app()` factory pattern supports this cleanly.
This is the fastest approach and avoids server lifecycle complexity.

### Integration: Part of pytest with a mark

Schemathesis tests live in `backend/tests/test_schema.py` as a regular pytest
file using `@pytest.mark.schemathesis`. This allows selective execution:
- Locally (Stop hook): all tests run together, including Schemathesis
- CI: unit tests and schema tests run as separate steps for clear triage

### Example count: 100 per endpoint everywhere

The default ~100 Hypothesis examples per endpoint runs in under a second with
an in-memory ASGI app. No need for different counts between local and CI.

### Copier template: Always included

The test file is a regular `.py` file (no `.jinja` suffix) that ships with
every generated project. Since Schemathesis dynamically reads the OpenAPI
schema at runtime, it works regardless of which features are included. With
no endpoints, it trivially passes (zero parametrized cases).

### CI pipeline: Separate step

Deterministic unit tests and non-deterministic schema tests run as separate
CI steps for clear failure attribution:
- `uv run pytest -m "not schemathesis" -v`
- `uv run pytest -m schemathesis -v`

## Components

### 1. Test file — `backend/tests/test_schema.py`

```python
import pytest
import schemathesis

from api.main import create_app

schema = schemathesis.openapi.from_asgi("/schema/openapi.json", create_app())

@pytest.mark.schemathesis
@schema.parametrize()
def test_api(case):
    case.call_and_validate()
```

Validates 5 properties per endpoint by default:
- No server errors (5xx)
- Status code conformance
- Content type conformance
- Response schema conformance
- Response header conformance

### 2. Dependencies — `backend/pyproject.toml.jinja`

Add `schemathesis>=4.10,<5.0` to the `[dependency-groups] dev` section.

Register the pytest mark:
```toml
[tool.pytest.ini_options]
markers = ["schemathesis: property-based API schema tests"]
```

### 3. CI — `.github/workflows/validate-template.yml`

Split existing `Run backend tests` step into two:
- "Run backend tests" with `-m "not schemathesis"`
- "Run backend schema tests" with `-m schemathesis`

### 4. Stop hook — No changes

The existing Stop hook runs `piper-py check strict` which includes pytest.
Schemathesis tests run alongside everything else locally.

## Discoveries during implementation

Three issues were found and fixed during Schemathesis integration:

### Unhandled KeyError in PUT endpoint

`InMemoryTodoRepository.update()` raises `KeyError` for nonexistent items,
which propagated as a 500 Internal Server Error. Fixed by catching `KeyError`
in the controller and raising `NotFoundException` (404). Added
`raises=[NotFoundException]` to the `@put` decorator to document the 404 in
the OpenAPI schema.

### Pydantic lax validation accepts schema-violating input

Pydantic's default lax mode coerces type-incorrect inputs (e.g., integer `0`
for a boolean field) instead of rejecting them. Schemathesis flagged this as
"API accepted schema-violating request." Fixed by configuring
`PydanticInitPlugin(validate_strict=True)` in `main.py.jinja`.

### Template repo import guard

`api/main.py` only exists in rendered projects (it's `main.py.jinja` in the
template repo). Added `pytest.importorskip("api.main")` so schema tests skip
gracefully in the template repo but run in generated projects and CI.
