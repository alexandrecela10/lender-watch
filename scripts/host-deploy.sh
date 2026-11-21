#!/usr/bin/env bash
# Deploys the current commit of the Lender Watch service to Fly.io. Needs a person's approval first, like `make prod`.
# Usage: make host-deploy
# Fly builds from the folder it's given, so this deploys a clean copy of the commit: no .env, no data/raw, nothing
# uncommitted. It checks the address answers afterwards, then uses up the approval.
set -euo pipefail
source "$(dirname "$0")/prod-lib.sh"

command -v fly >/dev/null 2>&1 || die "Install the Fly.io command line first (brew install flyctl), then run fly auth login."
require_approval
git -C "$ROOT" diff --quiet HEAD -- deploy/ scripts/host-deploy.sh ||
  die "Refused: deploy/ or scripts/host-deploy.sh differs from the current commit. Commit first, then get a new approval."

commit=$(git -C "$ROOT" rev-parse --short=12 HEAD)
base_url=$(sed -n 's/^ *LW_BASE_URL = "\(.*\)"/\1/p' "$ROOT/deploy/fly.toml")
copy=$(mktemp -d)
trap 'rm -rf "$copy"' EXIT
git -C "$ROOT" archive "$commit" | tar -x -C "$copy"
if find "$copy" \( -name ".env" -o -name ".env.*" -o -path "*/data/raw" \) | grep -q .; then
  die "Refused: the commit holds a .env file or data/raw."
fi

# The build context is the clean copy's root, so the Dockerfile's COPY lines see erm/, app/ and data/public/.
(cd "$copy" && fly deploy . --config deploy/fly.toml --dockerfile deploy/service.Dockerfile \
  --build-arg "GIT_COMMIT=$commit" --image-label "$commit" --remote-only --wait-timeout 300)

for _ in $(seq 1 30); do
  if curl -fsS -m 5 "$base_url/health" >/dev/null 2>&1; then
    consume_approval
    audit "host-deployed commit=$commit url=$base_url"
    exit 0
  fi
  sleep 5
done
audit "host-deploy-unhealthy commit=$commit url=$base_url"
die "Deployed $commit, but $base_url/health didn't answer. To roll back: fly releases, then fly deploy --image <the previous image>."
