#!/usr/bin/env bash
# Shared by the deploy and rollback scripts and the production gate hook. Source it, don't run it.
#
# Good images are a stack in $ERM_DEPLOY_DIR/good-images, one commit per line. The last line runs now.
# A rehearsal sets ERM_PROD_PROJECT to another name, so it cannot touch real prod (project "erm").

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
: "${ERM_DEPLOY_DIR:=$HOME/.erm/deploy}"
: "${ERM_PROD_PROJECT:=erm}"
: "${ERM_PROD_PORT:=8501}"
: "${ERM_HEALTH_TRIES:=60}"
: "${ERM_HEALTH_DELAY:=2}"
export ERM_PROD_PORT

STACK="$ERM_DEPLOY_DIR/good-images"
AUDIT="$ERM_DEPLOY_DIR/audit.log"
APPROVAL="$ERM_DEPLOY_DIR/prod-approval"
mkdir -p "$ERM_DEPLOY_DIR"

die() {
  echo "$*" >&2
  exit 1
}

audit() {
  echo "$(date -u +%FT%TZ) $*" >>"$AUDIT"
  echo "$*"
}

is_real_prod() { [ "$ERM_PROD_PROJECT" = "erm" ]; }

# Prints why there is no valid approval. Prints nothing when there is one.
approval_problem() {
  [ -f "$APPROVAL" ] || {
    echo "no approval on file"
    return 0
  }
  local commit expires head
  commit=$(sed -n 's/^commit=//p' "$APPROVAL")
  expires=$(sed -n 's/^expires=//p' "$APPROVAL")
  case "$expires" in
    '' | *[!0-9]*)
      echo "the approval file cannot be read"
      return 0
      ;;
  esac
  head=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null) || {
    echo "the current commit cannot be read"
    return 0
  }
  if [ "$commit" != "$head" ]; then
    echo "the approval is for a different commit"
  elif [ "$(date +%s)" -ge "$expires" ]; then
    echo "the approval has expired"
  fi
  return 0
}

require_approval() {
  is_real_prod || return 0
  local problem
  problem=$(approval_problem)
  [ -z "$problem" ] || die "Blocked: $problem. A person must run \`make approve-prod\` in a terminal first."
}

consume_approval() {
  if is_real_prod; then rm -f "$APPROVAL"; fi
}

guard_rehearsal_port() {
  if ! is_real_prod && [ "$ERM_PROD_PORT" = "8501" ]; then
    die "Refused: a rehearsal must not use port 8501, the real prod port."
  fi
}

# The image comes from the commit, but the container's settings come from compose.yaml in this folder.
# Refuse if that file differs from the commit, so an uncommitted edit can't reach prod (for example, adding .env).
require_committed_compose() {
  git -C "$ROOT" diff --quiet HEAD -- compose.yaml ||
    die "Refused: compose.yaml differs from the current commit. Commit or undo the change, then get a new approval."
}

compose() {
  docker compose -p "$ERM_PROD_PROJECT" -f "$ROOT/compose.yaml" --profile prod "$@"
}

stack_top() {
  if [ -f "$STACK" ]; then tail -n 1 "$STACK"; fi
}

# The commit under the top line, or nothing when there are fewer than two lines.
stack_previous() {
  if [ -f "$STACK" ] && [ "$(wc -l <"$STACK")" -ge 2 ]; then
    tail -n 2 "$STACK" | head -n 1
  fi
}

stack_push() {
  if [ "$(stack_top)" != "$1" ]; then echo "$1" >>"$STACK"; fi
}

stack_pop() {
  sed '$d' "$STACK" >"$STACK.tmp"
  mv "$STACK.tmp" "$STACK"
}

image_exists() { docker image inspect "erm-review:$1" >/dev/null 2>&1; }

# A tag can be moved, so each deploy records the exact image it ran. A rollback runs only that image.
image_id() { docker image inspect -f '{{.Id}}' "erm-review:$1" 2>/dev/null; }

record_image() { echo "$1 $(image_id "$1")" >>"$ERM_DEPLOY_DIR/image-ids"; }

image_is_recorded() {
  local want
  want=$(sed -n "s/^$1 //p" "$ERM_DEPLOY_DIR/image-ids" 2>/dev/null | tail -n 1)
  [ -n "$want" ] && [ "$want" = "$(image_id "$1")" ]
}

running_image() {
  local id
  id=$(compose ps -q prod)
  [ -n "$id" ] || return 0
  docker inspect -f '{{.Config.Image}}' "$id"
}

wait_healthy() {
  local i
  for ((i = 0; i < ERM_HEALTH_TRIES; i++)); do
    if curl -fsS -m 3 "http://localhost:$ERM_PROD_PORT/_stcore/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$ERM_HEALTH_DELAY"
  done
  return 1
}

# Runs one commit's image. Succeeds only if it answers and is the image we asked for.
switch_to() {
  ERM_PROD_TAG="$1" compose up -d --no-build --pull never prod >/dev/null 2>&1 || return 1
  wait_healthy || return 1
  [ "$(running_image)" = "erm-review:$1" ]
}

# After a failed change: put back what was running, or stop if nothing was.
restore() {
  if [ -n "$1" ]; then
    if switch_to "$1"; then
      audit "restored commit=$1"
    else
      audit "restore-failed commit=$1"
    fi
  else
    compose down >/dev/null 2>&1 || true
    audit "stopped: no earlier image to restore"
  fi
}
