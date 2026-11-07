#!/usr/bin/env bash
# Shared key scan. Reads a git diff on stdin and prints how many added lines look like a key
# or a filled-in .env value. Used by scripts/pre-commit and .claude/hooks/no-secrets.sh.
# Patterns are split in two so this file never matches itself. Values are never printed.

p_ant='sk-an''t-'
p_lf='sk-l''f-'
v='[^[:space:]"$<{]'   # a real value, not empty, a $VAR or a <placeholder>
keys="ANTHROPIC_API""_KEY|LANGFUSE_SECRET""_KEY|SEC_USER""_AGENT"

grep -E '^\+[^+]' | grep -cE "$p_ant|$p_lf|($keys)=$v"
exit 0
