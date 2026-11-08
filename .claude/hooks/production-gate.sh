#!/usr/bin/env bash
# PreToolUse hook on Bash, Edit and Write. Keeps agents from starting or changing production.
#
# Needs a person's approval (`make approve-prod`, valid 15 minutes, one commit):
#   make prod, make prod-down, make rollback, compose commands on the prod profile,
#   docker commands on the prod container or its images, edits to the files that define prod.
# Never allowed for an agent, approved or not:
#   the approval step, the approval file, edits to this gate.
#
# Exit 2 tells Claude Code to refuse the tool call and show the reason to Claude.
# Each decision is logged with its time to ~/.erm/deploy/gate.log, without the command text.
# Limit: this reads command text. A script file can hide a command, so scripts/prod-lib.sh checks again.

input=$(cat)
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"

log_decision() {
  local dir="${ERM_DEPLOY_DIR:-$HOME/.erm/deploy}"
  mkdir -p "$dir" 2>/dev/null
  echo "$(date -u +%FT%TZ) $1" >>"$dir/gate.log" 2>/dev/null
}

block() {
  log_decision "block ${tool:-unknown}: $1"
  echo "Blocked: $1" >&2
  exit 2
}

never() {
  block "agents can't run the production approval step or change this gate. Route: ask Alexandre to do it in his own terminal, outside Claude Code."
}

# Allows the action if a person has approved it, else blocks it and says how to get approval.
needs_approval() {
  local problem
  # shellcheck source=scripts/prod-lib.sh
  source "$root/scripts/prod-lib.sh" 2>/dev/null || block "the approval check could not load, so production stays closed."
  problem=$(approval_problem)
  if [ -n "$problem" ]; then
    block "this starts or changes production, and $problem. Route: ask a person to run \`make approve-prod\` in their own terminal, then try again. Agents can't approve."
  fi
  log_decision "allow $tool: approved production change"
  exit 0
}

# Fail closed: without jq the input can't be read. Other commands still run, so `brew install jq` remains possible.
if ! command -v jq >/dev/null 2>&1; then
  if printf '%s' "$input" | grep -qE 'prod|rollback|compose|docker'; then
    block "jq is not installed, so this safety check cannot run. Install it with \`brew install jq\`."
  fi
  exit 0
fi

tool=$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null) || block "the hook input could not be read, so production stays closed."

# --- File edits ---
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
if [ -n "$file" ]; then
  case "/$file" in
    */.claude/hooks/production-gate.sh | */.claude/settings.json | */.claude/settings.local.json | \
      */scripts/approve-prod.sh | */scripts/prod-lib.sh | */.erm/deploy/*)
      never
      ;;
    */compose.yaml | */Dockerfile | */.dockerignore | */scripts/prod-deploy.sh | */scripts/rollback.sh)
      needs_approval
      ;;
  esac
  exit 0
fi

# --- Shell commands ---
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

S='[[:space:]]'

# Quoted text is usually a message or a search term, so it is blanked before matching.
stripped=$(printf '%s' "$cmd" | jq -Rrs 'gsub("\\\\."; "") | gsub("\"[^\"]*\"|'"'"'[^'"'"']*'"'"'"; "_")')

# Unless the command runs a nested shell or interpreter: then quoted text may be code, so match the raw text.
text="$stripped"
if printf '%s' "$stripped" | grep -qE "(^|$S|[;&|(/])(bash|sh|zsh|eval|xargs|script|python3?|perl|ruby|node|osascript)($S|\$)"; then
  text="$cmd"
fi
case "$cmd" in
  git$' '*) ;;
  *'$('* | *'`'*) text="$cmd" ;;
esac

touches_prod() {
  has "(^|$S|/)g?make($S.*)?$S(prod|prod-down|rollback)($S|\$)" && return 0
  has 'prod-deploy\.sh|scripts/rollback\.sh' && return 0
  has 'COMPOSE_PROFILES=[^[:space:]]*prod' && return 0
  if has 'docker[- ]compose'; then
    has "$S(config|ps|logs|ls|images|version)($S|\$)" && return 1
    has "$S(--profile$S+|--profile=)prod($S|\$)" && return 0
    has "$S(-p|--project-name)[= ]*erm($S|\$)" && return 0
    has "${S}prod($S|\$)" && return 0
    return 1
  fi
  has "docker($S+[^[:space:]]+)*$S+(stop|start|restart|kill|rm|pause|unpause|rename|update|exec|cp|commit)$S.*erm-prod" && return 0
  has "docker$S+(container$S+)?(run|create)$S.*erm-review:" && ! has 'erm-review:dev' && return 0
  has "docker$S+(rmi|image$S+rm)$S.*erm-review" && return 0
  has "docker$S+(system|image)$S+prune" && return 0
  return 1
}

has() { printf '%s' "$seg" | grep -qE "$1"; }

found_prod=0
while IFS= read -r seg; do
  # Reading or committing text about production changes nothing.
  first=$(printf '%s' "$seg" | sed -E 's/^[[:space:]]+//; s/^([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)+//')
  first="${first%%[[:space:]]*}"
  case "$first" in
    git | grep | egrep | rg | ls | cat | head | tail | wc | diff) continue ;;
  esac
  has 'approve-prod|prod-approval|\.erm/deploy' && never
  touches_prod && found_prod=1
done < <(printf '%s\n' "$text" | tr ';|&()`"'"'" '\n\n\n\n\n\n\n\n')

[ "$found_prod" -eq 1 ] && needs_approval
exit 0
