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
