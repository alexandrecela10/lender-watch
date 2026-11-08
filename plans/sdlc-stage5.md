# Plan: SDLC Stage 5, deploy

Date: 2026-11-08. Owner: Alexandre. Source: Anthropic AI Native SDLC playbook, Stage 5, "Hooks as approval gates".
CI, AI review and branch protection exist. This adds the three missing parts.

## Summary

- The review app runs in Docker, with a `dev` and a `prod` profile.
- Each prod image is tagged with its git commit, so an earlier one can run again.
- `make rollback` returns prod to the previous good image.
- A Claude Code hook stops agents from starting or changing prod until a person approves.
- The gate is built last, so the scripts it protects are finished first.

## Decisions

- **Image source:** prod images build from `git archive <commit>`, so uncommitted files such as `.env` can't enter. `.dockerignore` is an allowlist for the dev build.
- **Image contents:** public sample data only. The app runs in public mode, which has no AI judge and needs no key.
- **Good image list:** a stack in `~/.erm/deploy/`, outside the repo so every worktree sees the same prod. A deploy pushes after its health check passes. A rollback pops.
- **Approval:** `make approve-prod`, a person at a terminal typing a random code. It is valid for 15 minutes, for one commit, for one prod change. The gate uses the approval up for anything except the deploy and rollback scripts, which use it up themselves on success. Deploy and rollback refuse if `compose.yaml` differs from the commit (AI review of #15).
- **Agents never approve:** the gate blocks the approval command, the approval file and edits to the gate, with no approval route.
- **Rehearsal:** an agent may not change real prod, so the rehearsal runs the same scripts in a separate project (`erm-rehearsal`, port 18501, temporary state).

## Limits

- The gate reads command text. A script written by an agent can hide a command from it, so the deploy and rollback scripts check the approval again.
- A hook in `.claude/settings.json` can be removed by anyone who can edit the repo. The playbook puts non-negotiable hooks in managed settings, which this repo does not have.

## Order

### S1. Docker

Files: `Dockerfile`, `.dockerignore`, `compose.yaml`, `scripts/check-image.sh`, `Makefile`.
Add the image, both profiles and a check that an image holds no key, `.env` or `data/raw`.

Exit criteria
- `docker compose --profile dev config` and `--profile prod config` succeed.
- An image builds and `scripts/check-image.sh` passes on it.
- Commit: `feat(deploy): Docker image and dev and prod compose profiles`.

### S2. Deploy and rollback scripts

Files: `scripts/prod-lib.sh`, `scripts/prod-deploy.sh`, `scripts/rollback.sh`, `scripts/rehearse-rollback.sh`, `scripts/smoke-app.py`, `tests/test_deploy_scripts.py`, `Makefile`.
Tests use a fake `docker` and `curl` on the PATH.

Exit criteria
- Tests show: rollback picks the previous good image, refuses with no earlier image, restores the current image if the target fails its health check, and refuses real prod without approval.
- `make test` and `make lint` pass.
- Commit: `feat(deploy): prod deploy and one-command rollback`.

### S2b. Smaller image

Files: `Dockerfile`.
Added after the first rehearsal. The rollback worked, but the app check failed: Docker's 59 GB disk had 495 MB free and the image held a 626 MB installer cache.

Exit criteria
- The image holds no `/root/.cache`.
- Commit: `fix(deploy): leave the installer cache out of the image`.

### S2c. Temporary files in memory

Files: `compose.yaml`.
Added after the second rehearsal, which failed the same way: Docker's disk was still full. The disk holds other projects' images, which this work must not delete. Prod now keeps `/tmp` in memory.

Exit criteria
- `docker compose --profile prod config` shows the `/tmp` memory mount.
- Commit: `fix(deploy): keep prod temporary files in memory`.

### S3. Rehearse

Runs after S4 (departure): it needs two commits that hold the fixed Dockerfile.

Files: `outputs/test-evidence/stage5/rehearsal.log`, `outputs/test-evidence/stage5/image-check.log`.
Deploy the S2b commit, deploy the S4 commit, roll back, then check the app answers.

Exit criteria
- The log shows the running image change from the S4 commit to the S2b commit, and a typed list returning KnowBe4 as flagged.
- The image check log shows a planted `.env` staying out of the image, and an image with a key failing the check.
- Commit: `test(deploy): rollback rehearsal evidence`.

### S4. Production gate

Files: `.claude/hooks/production-gate.sh`, `.claude/settings.json`, `scripts/approve-prod.sh`, `tests/test_production_gate.py`, `Makefile`.
Same fail-closed style as the other hooks. Each decision is logged with a time. A block says why and how to get approval.

Exit criteria
- Tests show the gate blocks `make prod`, `make rollback` and direct compose commands without approval, allows them with one, and blocks expired or wrong-commit approvals.
- Tests show the gate always blocks an agent running the approval step, and that the approval step refuses without a terminal.
- Commit: `feat(deploy): production gate hook and human approval step`.

### S5. Docs

Files: `README.md`, `CLAUDE.md`.

Exit criteria
- README has a short deploy section. The healthy test count in `CLAUDE.md` matches `make test`.
- Commit: `docs(deploy): how to run, approve and roll back prod`.
