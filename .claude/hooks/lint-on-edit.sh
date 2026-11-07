#!/usr/bin/env bash
# PostToolUse hook on Edit and Write. Formats and lints the Python file just changed.
# Exit 2 shows the lint errors to Claude so it fixes them before moving on.

file=$(jq -r '.tool_input.file_path // empty')
case "$file" in *.py) ;; *) exit 0 ;; esac
[ -f "$file" ] || exit 0

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || exit 0
uv run ruff format --quiet "$file" >&2
if ! out=$(uv run ruff check --quiet "$file" 2>&1); then
  echo "Lint errors in $file after the edit. Fix them:" >&2
  echo "$out" >&2
  exit 2
fi
exit 0
