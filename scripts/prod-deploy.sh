#!/usr/bin/env bash
# Builds the image for a commit, checks it holds no key, runs it, and records it as good.
# Usage: scripts/prod-deploy.sh, or `make prod`. Real prod always deploys HEAD and needs approval.
# A rehearsal may name a commit: scripts/prod-deploy.sh <commit>.
set -euo pipefail
source "$(dirname "$0")/prod-lib.sh"

guard_rehearsal_port
require_approval
require_committed_compose
if is_real_prod && [ $# -gt 0 ]; then die "Refused: real prod deploys the approved commit only."; fi

commit=$(git -C "$ROOT" rev-parse --short=12 "${1:-HEAD}")
image="erm-review:$commit"
current=$(stack_top)

# Built from the commit, not the folder, so uncommitted files such as .env can't enter.
if ! image_exists "$commit"; then
  git -C "$ROOT" archive "$commit" | docker build -q -t "$image" --build-arg "GIT_COMMIT=$commit" - >/dev/null
fi
"$ROOT/scripts/check-image.sh" "$image"

if switch_to "$commit"; then
  stack_push "$commit"
  consume_approval
  audit "deployed commit=$commit project=$ERM_PROD_PROJECT"
else
  audit "deploy-failed commit=$commit project=$ERM_PROD_PROJECT"
  restore "$current"
  die "Deploy failed: commit $commit did not pass its health check."
fi
