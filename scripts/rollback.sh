#!/usr/bin/env bash
# Returns prod to the previous good image. Run with `make rollback`. Real prod needs approval.
# If the earlier image fails its health check, the current one is put back and the list is unchanged.
set -euo pipefail
source "$(dirname "$0")/prod-lib.sh"

guard_rehearsal_port
require_approval
require_committed_compose

current=$(stack_top)
previous=$(stack_previous)
[ -n "$current" ] || die "Nothing to roll back: no deploy is on record."
[ -n "$previous" ] || die "Nothing to roll back to: commit $current is the only good image on record."
image_exists "$previous" || die "Cannot roll back: image $ERM_IMAGE:$previous is not on this machine."
image_is_recorded "$previous" || die "Refused: image $ERM_IMAGE:$previous is not the image that was deployed."

if switch_to "$previous"; then
  stack_pop
  consume_approval
  audit "rolled-back from=$current to=$previous project=$ERM_PROD_PROJECT"
else
  audit "rollback-failed from=$current to=$previous project=$ERM_PROD_PROJECT"
  restore "$current"
  die "Rollback failed: commit $previous did not pass its health check."
fi
