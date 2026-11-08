#!/usr/bin/env bash
# Fails if an image holds a .env file, data/raw, or a key. Prints counts and paths, never a value.
# Usage: scripts/check-image.sh <image>

image="${1:?usage: check-image.sh <image>}"

# Split so this file never matches itself, as in scripts/scan-secrets.sh.
p_ant='sk-an''t-'
p_lf='sk-l''f-'
v='[^[:space:]"$<{]'
keys="ANTHROPIC_API""_KEY|LANGFUSE_SECRET""_KEY|SEC_USER""_AGENT"
pattern="$p_ant|$p_lf|($keys)=$v"

fail=0

# Our own files only: installed packages hold example strings and no user data.
found=$(docker run --rm --user 0 --entrypoint sh -e "P=$pattern" "$image" -c '
  find / -xdev \( -path /proc -o -path /sys -o -path /app/.venv -o -path /usr \) -prune \
    -o -type f \( -name ".env" -o -name ".env.*" \) -print
  [ -e /app/data/raw ] && echo /app/data/raw
  grep -rlE "$P" /app --exclude-dir=.venv 2>/dev/null
  true
') || {
  echo "FAIL: could not look inside $image" >&2
  exit 1
}
if [ -n "$found" ]; then
  echo "FAIL: $image holds a .env file, data/raw or a key at:" >&2
  echo "$found" >&2
  fail=1
fi

# Build history and image settings are stored with the image too.
meta=$({
  docker history --no-trunc "$image"
  docker inspect "$image"
} | grep -cE "$pattern")
if [ "${meta:-0}" -gt 0 ]; then
  echo "FAIL: $image has $meta line(s) in its history or settings that look like a key." >&2
  fail=1
fi

[ "$fail" -eq 0 ] && echo "PASS: no .env, data/raw or key in $image"
exit "$fail"
