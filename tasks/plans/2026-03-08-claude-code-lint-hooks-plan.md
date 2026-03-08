# Claude Code Lint Hooks — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Claude Code hooks to generated (copier) projects that enforce piper-py/piper-ts coding standards with a circuit breaker to prevent infinite loops.

**Architecture:** Two shell scripts (PostToolUse fast check + Stop strict check with retry counter) wired via `.claude/settings.local.json`. Scripts and settings are part of the copier template so they appear in generated projects but not in the template repo itself.

**Tech Stack:** Bash, jq, Claude Code hooks API (stdin JSON), copier (Jinja templating).

**Design doc:** `tasks/designs/2026-03-08-claude-code-lint-hooks-design.md`

---

## Task 1: Create `lint-on-edit.sh`

The PostToolUse hook script. Reads stdin JSON to detect the edited file's language, runs the relevant fast linter, and resets the Stop retry counter.

**Files:**
- Create: `.claude/hooks/lint-on-edit.sh`

**Step 1: Create the hooks directory**

```bash
mkdir -p .claude/hooks
```

**Step 2: Create `lint-on-edit.sh`**

Create `.claude/hooks/lint-on-edit.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="/tmp/piper-lint-stop-count"

# Reset stop counter — agent is actively editing, so next Stop gets fresh attempts
echo "0" > "$STATE_FILE"

# Read hook context from stdin
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# If we can't determine the file, skip silently
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Route to the relevant linter based on file extension
case "$FILE_PATH" in
  *.py)
    echo "⚡ Running fast Python lint check..."
    OUTPUT=$(piper-py -d ./backend check fast 2>&1) || {
      echo "⚡ Lint check (fast) found issues in Python code:"
      echo ""
      echo "$OUTPUT"
      echo ""
      echo "Fix these issues before continuing."
      exit 1
    }
    ;;
  *.ts|*.tsx|*.js|*.jsx)
    echo "⚡ Running fast TypeScript lint check..."
    OUTPUT=$(piper-ts -d ./ui check fast 2>&1) || {
      echo "⚡ Lint check (fast) found issues in TypeScript code:"
      echo ""
      echo "$OUTPUT"
      echo ""
      echo "Fix these issues before continuing."
      exit 1
    }
    ;;
  *)
    # Not a lintable file — skip silently
    exit 0
    ;;
esac
```

**Step 3: Make it executable**

```bash
chmod +x .claude/hooks/lint-on-edit.sh
```

**Step 4: Commit**

```bash
git add .claude/hooks/lint-on-edit.sh
git commit -m "feat: add PostToolUse lint hook with language detection"
```

---

## Task 2: Create `lint-on-stop.sh`

The Stop hook script. Runs strict/full linters for both languages with a retry counter that acts as a circuit breaker after 3 failed attempts.

**Files:**
- Create: `.claude/hooks/lint-on-stop.sh`

**Step 1: Create `lint-on-stop.sh`**

Create `.claude/hooks/lint-on-stop.sh` with this exact content:

```bash
#!/usr/bin/env bash
set -uo pipefail

STATE_FILE="/tmp/piper-lint-stop-count"
MAX_ATTEMPTS=3

# Read and increment counter
COUNT=$(cat "$STATE_FILE" 2>/dev/null || echo "0")
COUNT=$((COUNT + 1))
echo "$COUNT" > "$STATE_FILE"

# Run both linters, capture output and exit codes
PY_OUTPUT=$(piper-py -d ./backend check strict 2>&1) || true
PY_EXIT=$?
TS_OUTPUT=$(piper-ts -d ./ui check full 2>&1) || true
TS_EXIT=$?

# If both pass, reset counter and exit cleanly
if [ $PY_EXIT -eq 0 ] && [ $TS_EXIT -eq 0 ]; then
  echo "0" > "$STATE_FILE"
  echo "✅ All lint checks passed."
  exit 0
fi

# Build combined output
COMBINED=""
if [ $PY_EXIT -ne 0 ]; then
  COMBINED="${COMBINED}--- Python (piper-py check strict) ---\n${PY_OUTPUT}\n\n"
fi
if [ $TS_EXIT -ne 0 ]; then
  COMBINED="${COMBINED}--- TypeScript (piper-ts check full) ---\n${TS_OUTPUT}\n\n"
fi

# Circuit breaker
if [ "$COUNT" -ge "$MAX_ATTEMPTS" ]; then
  echo "⚠️ Lint issues remain after ${MAX_ATTEMPTS} attempts. Allowing completion."
  echo ""
  echo -e "$COMBINED"
  echo "Please note these unresolved issues for the user."
  echo "0" > "$STATE_FILE"
  exit 0
else
  REMAINING=$((MAX_ATTEMPTS - COUNT))
  echo "🚫 Pre-completion lint check FAILED (attempt ${COUNT}/${MAX_ATTEMPTS})"
  echo ""
  echo -e "$COMBINED"
  echo "You must fix these issues before completing. ${REMAINING} attempt(s) remaining."
  exit 1
fi
```

**Step 2: Make it executable**

```bash
chmod +x .claude/hooks/lint-on-stop.sh
```

**Step 3: Commit**

```bash
git add .claude/hooks/lint-on-stop.sh
git commit -m "feat: add Stop lint hook with circuit breaker (max 3 attempts)"
```

---

## Task 3: Create `settings.local.json.jinja`

The copier template that generates the Claude Code settings file (with hooks) in generated projects.

**Files:**
- Create: `.claude/settings.local.json.jinja`

**Step 1: Create the Jinja template**

Create `.claude/settings.local.json.jinja` with this exact content:

```json
{
  "permissions": {
    "allow": [
      "Bash(cat:*)",
      "Bash(grep:*)",
      "Bash(wc:*)",
      "Bash(ls:*)",
      "Bash(npx piper-ts:*)",
      "Bash(uvx piper-py:*)",
      "Bash(piper-py:*)",
      "Bash(piper-ts:*)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/lint-on-edit.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/lint-on-stop.sh"
          }
        ]
      }
    ]
  }
}
```

Note: This file has no Jinja expressions — the `.jinja` suffix is only needed so copier processes it and strips the suffix, producing `settings.local.json` in the generated project.

**Step 2: Commit**

```bash
git add .claude/settings.local.json.jinja
git commit -m "feat: add copier template for Claude Code settings with lint hooks"
```

---

## Task 4: Update `copier.yml` to exclude the template repo's own settings

Prevent the template repo's `.claude/settings.local.json` (no hooks) from being copied to generated projects — they should get the `.jinja` version instead.

**Files:**
- Modify: `copier.yml:3-16` (the `_exclude` list)

**Step 1: Add the exclude entry**

Add this line to the `_exclude` list in `copier.yml`, after the existing entries:

```yaml
  - ".claude/settings.local.json"
```

The full `_exclude` section should look like:

```yaml
_exclude:
  - "copier.yml"
  - "build/"
  - "tasks/plans/2026-*-copier-*"
  - ".github/workflows/validate-template.yml"
  - "docs/template-guide.md"
  - ".claude/settings.local.json"
  - "{% if not include_examples %}backend/api/todo{% endif %}"
  - "{% if not include_examples %}backend/api/user{% endif %}"
  - "{% if not include_examples %}backend/tests/todo{% endif %}"
  - "{% if not include_examples %}backend/tests/user{% endif %}"
  - "{% if not include_examples %}ui/src/features{% endif %}"
  - "{% if not include_examples %}ui/tests/components{% endif %}"
  - "{% if not include_examples %}ui/tests/mocks{% endif %}"
  - "{% if not include_examples %}ui/tests/e2e/todo.spec.ts{% endif %}"
```

**Step 2: Commit**

```bash
git add copier.yml
git commit -m "feat: exclude template repo's settings.local.json from copier output"
```

---

## Task 5: Validate with copier

Generate a project and verify the hooks are correctly wired.

**Step 1: Generate a project from the template**

```bash
copier copy --defaults --trust --vcs-ref HEAD ./ ./build
```

**Step 2: Verify the generated settings file has hooks**

```bash
cat build/.claude/settings.local.json
```

Expected: The file should contain the `"hooks"` section with both `PostToolUse` and `Stop` entries. It should NOT have a `.jinja` suffix.

**Step 3: Verify the hook scripts are present and executable**

```bash
ls -la build/.claude/hooks/lint-on-edit.sh
ls -la build/.claude/hooks/lint-on-stop.sh
```

Expected: Both files exist and have execute permissions.

**Step 4: Verify the template repo's own settings.local.json was NOT copied**

The generated `settings.local.json` should have the hooks config (from the `.jinja` template), not the template repo's plain permissions-only version. Check:

```bash
grep -c '"hooks"' build/.claude/settings.local.json
```

Expected: `1` (the hooks key is present).

**Step 5: Clean up**

```bash
rm -rf build
```

**Step 6: Commit (only if fixes were needed)**

If any issues were found and fixed in earlier tasks, commit those fixes:

```bash
git add -A
git commit -m "fix: address issues found during lint hooks validation"
```
