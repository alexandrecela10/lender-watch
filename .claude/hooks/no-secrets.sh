#!/usr/bin/env bash
# PreToolUse hook on Bash. When the command is a git commit, scan the lines it would add for keys.
# Patterns are split in two so this file never matches itself.
# Exit 2 tells Claude Code to refuse the commit. The key value is never printed.

cmd=$(jq -r '.tool_input.command // empty')
echo "$cmd" | grep -qE 'git( -C [^ ]+)? commit' || exit 0

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || exit 0

# Lines added by the staged change. With -a or --all, tracked unstaged changes are committed too.
added=$(git diff --cached -U0 --no-color | grep -E '^\+[^+]')
if echo "$cmd" | grep -qE 'commit[^|;&]* (-a|--all|-[a-zA-Z]*a[a-zA-Z]*)( |$)'; then
  added="$added
$(git diff -U0 --no-color | grep -E '^\+[^+]')"
fi

p_ant='sk-an''t-'
p_lf='sk-l''f-'
v='[^[:space:]"$<{]'   # a real value, not empty, a $VAR or a <placeholder>
keys="ANTHROPIC_API""_KEY|LANGFUSE_SECRET""_KEY|SEC_USER""_AGENT"

hits=$(echo "$added" | grep -cE "$p_ant|$p_lf|($keys)=$v")
if [ "$hits" -gt 0 ]; then
  files=$(git diff --cached --name-only | tr '\n' ' ')
  echo "Blocked: the commit adds $hits line(s) that look like a key or a filled-in .env value (staged files: $files). Keys live only in .env, which is git-ignored. Unstage the file, remove the value, and commit again." >&2
  exit 2
fi
exit 0
