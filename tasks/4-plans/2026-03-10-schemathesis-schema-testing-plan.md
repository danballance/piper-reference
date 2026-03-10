# Schemathesis Schema Testing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add property-based API schema testing using Schemathesis to validate responses conform to the OpenAPI spec.

**Architecture:** Single pytest test file uses `schemathesis.openapi.from_asgi()` to test the Litestar app in-process. A `@pytest.mark.schemathesis` marker enables CI to run schema tests as a separate step from deterministic unit tests. The test file is always included in generated projects (not template-conditional).

**Tech Stack:** Schemathesis 4.10+, Hypothesis (transitive), pytest markers

---

### Task 1: Add schemathesis dependency

**Files:**
- Modify: `backend/pyproject.toml.jinja:112-116`

**Step 1: Add schemathesis to dev dependency group**

In `backend/pyproject.toml.jinja`, add `schemathesis` to `[dependency-groups] dev`:

```toml
[dependency-groups]
dev = [
    "pytest>=8.4.2",
    "pytest-cov>=7.0.0",
    "schemathesis>=4.10,<5.0",
]
```

**Step 2: Register the pytest mark**

In the same file, add the `markers` key to `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
markers = [
    "schemathesis: property-based API schema tests",
]
```

**Step 3: Sync dependencies**

Run: `cd backend && uv sync`
Expected: schemathesis and its dependencies install successfully.

**Step 4: Commit**

```bash
git add backend/pyproject.toml.jinja backend/uv.lock
git commit -m "feat: add schemathesis dev dependency and pytest mark"
```

---

### Task 2: Create schema test file

**Files:**
- Create: `backend/tests/test_schema.py`

**Step 1: Write the test file**

Create `backend/tests/test_schema.py`:

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

Notes:
- Uses `create_app()` factory (not module-level `app`) for a fresh instance.
- `/schema/openapi.json` is Litestar's default OpenAPI schema endpoint.
- `call_and_validate()` checks all 5 default properties: no 5xx, status code conformance, content type conformance, response schema conformance, header conformance.
- No `.jinja` suffix — this file ships with every generated project unchanged.

**Step 2: Run only schemathesis tests to verify they pass**

Run: `cd backend && uv run pytest -m schemathesis -v`
Expected: Tests are collected for each endpoint (GET `/`, POST `/`, PUT `/{item_title}`) and all pass.

**Step 3: Run full test suite to verify no regressions**

Run: `cd backend && uv run pytest -v`
Expected: All existing tests plus new schema tests pass. No pytest marker warnings.

**Step 4: Commit**

```bash
git add backend/tests/test_schema.py
git commit -m "feat: add schemathesis property-based schema tests"
```

---

### Task 3: Split CI test steps

**Files:**
- Modify: `.github/workflows/validate-template.yml:42-43`

**Step 1: Replace the single test step with two steps**

In `.github/workflows/validate-template.yml`, replace:

```yaml
      - name: Run backend tests
        run: cd build/backend && uv run pytest -v
```

with:

```yaml
      - name: Run backend tests
        run: cd build/backend && uv run pytest -m "not schemathesis" -v

      - name: Run backend schema tests
        run: cd build/backend && uv run pytest -m schemathesis -v
```

**Step 2: Commit**

```bash
git add .github/workflows/validate-template.yml
git commit -m "feat: separate deterministic and schema tests in CI"
```

---

### Task 4: Verify end-to-end

**Step 1: Run the full linting pipeline locally**

Run: `uvx piper-py -d ./backend check fast`
Expected: All checks pass (includes pytest).

**Step 2: Verify copier template generation still works**

Run: `copier copy --defaults --trust --vcs-ref HEAD ./ /tmp/piper-test && cd /tmp/piper-test/backend && uv sync && uv run pytest -v`
Expected: Generated project includes `tests/test_schema.py`, dependencies install, all tests pass.

**Step 3: Clean up**

Run: `rm -rf /tmp/piper-test`
