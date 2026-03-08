# Claude Code Lint Hooks — Design

**Date:** 2026-03-08
**Goal:** Enforce coding standards during agentic coding sessions using Claude Code hooks and the piper-py/piper-ts linting tools, with a circuit breaker to prevent infinite loops.

## Problem

When Claude Code hooks gate the agent's Stop event on lint checks, a non-zero exit code prevents the agent from stopping. The agent fixes the issues, tries to stop again, the hook fires again — potentially finding new issues introduced by the fix — creating an infinite loop.

## Approach

**Stateful wrapper scripts with a retry counter (circuit breaker).**

Two shell scripts wrap the piper linting commands:

1. **`lint-on-edit.sh`** — PostToolUse hook (Edit/Write matcher). Runs the relevant fast linter based on the edited file's extension. Resets the Stop retry counter.
2. **`lint-on-stop.sh`** — Stop hook. Runs strict/full checks for both languages. Enforces a maximum of 3 attempts before allowing the agent to stop with a warning.

## Architecture

```
.claude/
├── hooks/
│   ├── lint-on-edit.sh          # PostToolUse: fast, language-scoped check
│   └── lint-on-stop.sh          # Stop: strict check with circuit breaker
├── settings.local.json          # template repo config (no hooks)
└── settings.local.json.jinja    # generated project config (with hooks)
```

**State file:** `/tmp/piper-lint-stop-count` — stores the current Stop attempt count as a single integer.

## Hook Flow

### PostToolUse (Edit/Write)

```
Agent edits/writes a file
  -> lint-on-edit.sh fires
  -> Reads stdin JSON, extracts tool_input.file_path
  -> Resets /tmp/piper-lint-stop-count to 0
  -> Routes by file extension:
       *.py          -> piper-py -d ./backend check fast
       *.ts/tsx/js   -> piper-ts -d ./ui check fast
       other         -> exit 0 (skip)
  -> Exits with linter's exit code
```

### Stop

```
Agent tries to stop
  -> lint-on-stop.sh fires
  -> Reads counter from state file (default 0)
  -> Increments counter, writes back
  -> Runs piper-py -d ./backend check strict
  -> Runs piper-ts -d ./ui check full
  -> If both pass: reset counter, exit 0
  -> If either fails AND counter < 3:
       Output errors with "attempt N/3" message
       exit 1 (agent must fix and retry)
  -> If either fails AND counter >= 3:
       Output errors with "allowing completion" message
       Reset counter, exit 0 (agent may stop)
```

## Messaging

The scripts output structured messages so the agent knows exactly what to do:

**Fast check failure (PostToolUse):**
```
⚡ Lint check (fast) found issues in Python code:
[linter output]
Fix these issues before continuing.
```

**Strict check failure, attempts remaining (Stop):**
```
🚫 Pre-completion lint check FAILED (attempt 1/3)
[linter output]
You must fix these issues before completing. 2 attempt(s) remaining.
```

**Circuit breaker trips (Stop, attempt 3+):**
```
⚠️ Lint issues remain after 3 attempts. Allowing completion.
[linter output]
Please note these unresolved issues for the user.
```

## Copier Integration

These hooks are for **generated projects**, not the template repo itself.

- The template repo keeps its existing `.claude/settings.local.json` (permissions only, no hooks).
- A new `.claude/settings.local.json.jinja` generates the settings file with hooks in copied projects.
- `copier.yml` gets an `_exclude` entry for `.claude/settings.local.json` so the template repo's own config doesn't overwrite the generated one.
- Hooks are always included (not opt-in) — enforcing standards is part of the template's value.

## File Changes

| Action | File |
|---|---|
| Create | `.claude/hooks/lint-on-edit.sh` |
| Create | `.claude/hooks/lint-on-stop.sh` |
| Create | `.claude/settings.local.json.jinja` |
| Modify | `copier.yml` (add exclude for `.claude/settings.local.json`) |

## lint-on-edit.sh

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

## lint-on-stop.sh

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
PY_EXIT=0
PY_OUTPUT=$(piper-py -d ./backend check strict 2>&1) || PY_EXIT=$?
TS_EXIT=0
TS_OUTPUT=$(piper-ts -d ./ui check full 2>&1) || TS_EXIT=$?

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

## settings.local.json.jinja

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
