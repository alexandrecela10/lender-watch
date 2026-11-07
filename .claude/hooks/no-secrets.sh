#!/usr/bin/env bash
# PreToolUse hook on Bash. When the command is a git commit, scan the lines it would add for keys.
# Uses scripts/scan-secrets.sh, the same scan as the git pre-commit hook.
# Exit 2 tells Claude Code to refuse the commit. The key value is never printed.

input=$(cat)

# Fail closed for commits: without jq the command can't be parsed, so block anything that
# looks like a commit. Other commands still run, so `brew install jq` remains possible.
if ! command -v jq >/dev/null 2>&1; then
  if echo "$input" | grep -q 'commit'; then
    echo "Blocked: jq is not installed, so this safety check cannot run. Install it with \`brew install jq\`." >&2
    exit 2
  fi
  exit 0
fi

cmd=$(echo "$input" | jq -r '.tool_input.command // empty')
echo "$cmd" | grep -qE 'git( -C [^ ]+)? commit' || exit 0

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || exit 0

# Lines added by the staged change. With -a or --all, tracked unstaged changes are committed too.
# The patterns live in scripts/scan-secrets.sh, shared with the git pre-commit hook.
diff=$(git diff --cached -U0 --no-color)
if echo "$cmd" | grep -qE 'commit[^|;&]* (-a|--all|-[a-zA-Z]*a[a-zA-Z]*)( |$)'; then
  diff="$diff
$(git diff -U0 --no-color)"
fi

hits=$(echo "$diff" | ./scripts/scan-secrets.sh)
if [ "${hits:-0}" -gt 0 ]; then
  files=$(git diff --cached --name-only | tr '\n' ' ')
  echo "Blocked: the commit adds $hits line(s) that look like a key or a filled-in .env value (staged files: $files). Keys live only in .env, which is git-ignored. Unstage the file, remove the value, and commit again." >&2
  exit 2
fi
exit 0
