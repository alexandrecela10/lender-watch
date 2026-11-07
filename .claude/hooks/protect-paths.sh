#!/usr/bin/env bash
# PreToolUse hook on Edit and Write. Blocks edits to evidence Claude must not change.
# Always blocked: data/raw/ (SEC cache), data/eval/answer_key.csv, data/eval/judge_results.csv.
# Blocked when ERM_FIX_TASK=1: tests/ (a fix task changes the code, never the test).
# Exit 2 tells Claude Code to refuse the tool call and show the reason to Claude.

file=$(jq -r '.tool_input.file_path // empty')
[ -z "$file" ] && exit 0

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
rel="${file#"$root"/}"

case "$rel" in
  data/raw/*)
    echo "Blocked: $rel is the cached SEC download. It is evidence, not code. To change it, ask Alexandre to delete the cache file and re-run the download." >&2
    exit 2 ;;
  data/eval/answer_key.csv | data/eval/judge_results.csv)
    echo "Blocked: $rel is what the eval gate scores against. Editing it would hide a quality drop. Ask Alexandre to approve the change; it is made outside Claude Code." >&2
    exit 2 ;;
  tests/*)
    if [ "${ERM_FIX_TASK:-}" = "1" ]; then
      echo "Blocked: ERM_FIX_TASK=1 is set, so tests/ is read-only. Fix the code, not the test. To change a test, ask Alexandre and re-run without ERM_FIX_TASK." >&2
      exit 2
    fi ;;
esac
exit 0
