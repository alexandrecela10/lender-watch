#!/usr/bin/env bash
# Rehearses a rollback with the real deploy and rollback scripts, in a separate Docker project.
# Real prod is not touched: other project name, other port, temporary record of good images.
# Usage: scripts/rehearse-rollback.sh <good-commit> <new-commit>
set -euo pipefail

good="${1:?usage: rehearse-rollback.sh <good-commit> <new-commit>}"
new="${2:?usage: rehearse-rollback.sh <good-commit> <new-commit>}"

ERM_DEPLOY_DIR=$(mktemp -d)
export ERM_DEPLOY_DIR ERM_PROD_PROJECT=erm-rehearsal ERM_PROD_PORT=18501
here=$(dirname "$0")
source "$here/prod-lib.sh"

cleanup() {
  compose down >/dev/null 2>&1 || true
  rm -rf "$ERM_DEPLOY_DIR"
}
trap cleanup EXIT

short() { git -C "$ROOT" rev-parse --short=12 "$1"; }

show() {
  local image revision
  image=$(running_image)
  revision=$(docker inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image")
  echo "running: $image, built from commit $revision"
}

echo "== Rehearsal $(date -u +%FT%TZ): project $ERM_PROD_PROJECT, port $ERM_PROD_PORT"
echo "== Step 1: deploy the good commit"
"$here/prod-deploy.sh" "$good"
show

echo "== Step 2: deploy the new commit"
"$here/prod-deploy.sh" "$new"
show

echo "== Step 3: roll back"
start=$(date +%s)
"$here/rollback.sh"
echo "rollback took $(($(date +%s) - start)) seconds"
show
[ "$(running_image)" = "$ERM_IMAGE:$(short "$good")" ] || die "FAIL: the good image is not running."

echo "== Step 4: a second rollback has nowhere to go and must refuse"
if "$here/rollback.sh"; then die "FAIL: the second rollback should have refused."; fi

echo "== Step 5: the app answers after the rollback"
docker exec -i "$(compose ps -q prod)" /app/.venv/bin/python - <"$here/smoke-app.py"

echo "== Audit log"
cat "$AUDIT"
echo "== PASS"
