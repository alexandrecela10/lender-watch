#!/usr/bin/env bash
# A person approves one production change. Run `make approve-prod` in your own terminal.
# Refuses without a terminal and inside Claude Code. The production gate also blocks agents from this script.
set -euo pipefail
source "$(dirname "$0")/prod-lib.sh"

if [ -n "${CLAUDECODE:-}" ] || ! [ -t 0 ]; then
  die "Refused: a person must run this in their own terminal, outside Claude Code."
fi

commit=$(git -C "$ROOT" rev-parse HEAD)
code=$(od -An -N3 -tx1 /dev/urandom | tr -d ' \n')

echo "You are approving one production change, valid for 15 minutes:"
echo "  commit: $commit"
echo "  title:  $(git -C "$ROOT" log -1 --format=%s)"
printf 'Type %s to approve: ' "$code"
read -r answer
[ "$answer" = "$code" ] || die "Not approved: the code did not match."

umask 077
{
  echo "commit=$commit"
  echo "expires=$(($(date +%s) + 900))"
  echo "by=${USER:-unknown}"
} >"$APPROVAL"
audit "approved commit=$commit by=${USER:-unknown}"
