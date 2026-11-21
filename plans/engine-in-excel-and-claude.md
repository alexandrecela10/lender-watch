# Plan: Lender Watch inside real Excel and real Claude

Date: 2026-11-21. Owner: Alexandre. Build: one step per commit, on branch `claude/entity-reconciliation-productionize-e5ebcf`.
Source: `specs/engine-in-excel-and-claude.md` (approved 2026-11-21, commit `a054a07`), from `intent/engine-in-excel-and-claude.md` (commit `ce9220e`).
Evidence: the repo's code, and Claude's connector docs read on 2026-11-20. Nothing has run inside real Excel or real Claude. No analyst has been interviewed. The pain is inferred.

## Summary

- 10 steps. Steps 1 to 7 are mine, and each ends with tests passing and a commit.
- Step 0 tests the riskiest part first: signing in from Excel. It needs Alexandre for 20 minutes, and runs alongside the rest.
- Steps 1 and 2 change the engine underneath: choosing a quarter, and answers kept per person. Analysts see nothing new yet.
- Step 3 gives the product one name and two tools.
- Step 4 builds the hosted service with sign-in. Step 5 updates the Excel add-in.
- Step 6 adds the tool-choice eval.
- Step 7 prepares the deploy. Step 8 is Alexandre's: accounts, deploy, and the runs in real Excel and Claude.
- Step 9: the verifier checks everything, then a pull request.
- Matching results must not change. `make evals` runs at every step.

## Final review, 2026-11-21

Done before building, at Alexandre's request. Each change is applied in the steps below.

| # | Finding | Kind | Change |
|---|---|---|---|
| 1 | The panel must know whether sign-in is needed, and which provider and client to use, before anyone has signed in. The spec makes `/api/status` require sign-in. | Missing | `/api/status` is public. It returns only: sign-in on or off, the issuer, the add-in's public client id, the quarters held, and the data version. No user data. Departure from spec section 6, recorded here. |
| 2 | Excel loads add-ins over HTTPS only, even locally. The plan moved the add-in to the service but gave the service no local HTTPS. | Missing | `make excel` runs the service in local mode on port 3000 with the Office development certificate, reusing the desk's certificate code. Local mode: no sign-in, panel skips it. |
| 3 | Silent token refresh when the panel opens is in the spec but in no step. | Missing | Added to S5. |
| 4 | Hosted calls weren't counted in the run records, so the pilot would leave no usage trace. | Missing | S4 wraps each `/mcp` and `/api/check` call in `telemetry.run`, with sources `service_mcp` and `service_api`. Counts only. |
| 5 | `CLAUDE.md` and the README list commands this build changes. | Missing | S7 updates both: `make service`, `make excel`, `make tool-choice`, `make host-deploy`; `make mcp-web` removed. |
| 6 | The add-in needs a public client id from WorkOS, set per environment. | Missing | Setting `LW_EXCEL_CLIENT_ID`, served by `/api/status`. |
| 7 | S0 as a separate spike would build sign-in code twice, once in the old panel and again in S5. | Not needed as planned | S0 builds `auth.js` as the final module, used unchanged by S5. Its manual check waits for the WorkOS account, so S1 to S4 don't wait for it. |
| 8 | Keeping `erm/mcp_remote.py` alongside the new service would leave two hosted connectors. | Not needed | Removed in S4, as planned. Its only other users are `make mcp-web` and `tests/test_excel_addin.py`, both changed in S4. |
| 9 | The desk's `/api/ask` and Claude switch stay useful locally. | Keep | Local desk unchanged apart from the quarter and the new core function. |

## Providers

Sign-in: WorkOS AuthKit, $0. Host: Fly.io, about $7 a month. Details and what's still unconfirmed in "Sign-in provider and host" at the end.

## What Alexandre does, and when

| When | What | Time |
|---|---|---|
| Any time from now | Create a WorkOS account (free), switch on the settings listed at the end, invite your own personal email, and send me the AuthKit issuer address. Never a secret | 15 min |
| After step 0 is committed | Run step 0's check in Excel on the web, and send a screenshot | 20 min |
| After step 7 | Create the host account, set the secrets on the host, run `make approve-prod`, then `make host-deploy` | 30 min |
| After step 7 | Apply the gate patch: `git apply outputs/patches/production-gate-host.patch` | 2 min |
| After deploy | Checks 22 to 27, recorded under `outputs/test-evidence/excel-claude/` | 45 min |
| Before the pull request | Name the pilot analyst | |

Agents can't edit the production gate, so step 7 writes the gate change as a patch for Alexandre to apply.

## Order

### S0. Excel sign-in spike (risk first)

Files: `app/desk/excel/signin.html` (new), `app/desk/excel/signin-callback.html` (new), `app/desk/excel/auth.js` (new), `app/desk/excel/taskpane.js`, `app/desk/excel/taskpane.html`, `tests/excel_addin_check.cjs`.
The panel gets a "Sign in" button. It opens the provider's sign-in in an Office dialog, using PKCE, and keeps the access token in memory in the shared runtime. Nothing else uses the token yet.

Exit criteria
- `node tests/excel_addin_check.cjs` passes, with a stand-in dialog: the PKCE code challenge is S256, the state is checked, the token never reaches `localStorage` or `OfficeRuntime.storage`.
- `make test` and `make lint` green.
- Commit: `feat(excel): sign-in through an Office dialog, token kept in memory`.
- Then Alexandre, with `make excel`: add the manifest in Excel on the web, click "Sign in", sign in with a personal email, and see "Signed in". The panel shows the token's audience and expiry, never the token. Also try an address that wasn't invited: it must be refused. If any of this fails, stop and revise the spec's section 4 before step 5.

### S1. Choosing the quarter

Files: `erm/api.py`, `erm/retrieve.py`, `app/desk/server.py`, `app/review.py`, `tests/test_api.py`.
- Drop `LATEST, PRIOR`. Add `Engine.periods()`, `Engine.latest()`, `Engine.previous(as_of)`.
- One index per quarter, built on first use, cached as `<cache stem>-<fingerprint12>-<quarter>.pkl`. Word counts per quarter.
- `resolve_entity` and `gather_facts` take `as_of`. `gather_facts` uses it for facts, `excluded` and `n_positions_used`.
- Desk and review app call `engine.latest()`.

Exit criteria
- Tests for spec checks 3 and 8: both quarters work, an unknown date names the quarters held, a changed holdings file builds a new index, and the 30 June word counts equal `eval/offline.py`'s table.
- `make evals` prints `precision 1.000`, `recall 0.936`, `PASS`.
- `make test` and `make lint` green.
- Commit: `feat(engine): choose the quarter; one index per quarter keyed by data version`.

### S2. Saved answers, per person

Files: `erm/store.py`, `erm/api.py`, `erm/cli.py`, `scripts/upgrade_store.py` (new), `data/public/decisions.sqlite`, `tests/test_store.py` (new), `tests/test_api.py`.
- `owner` column, key `(owner, pair_id)`, rebuild in one transaction for an old store. WAL mode, one write lock.
- `owner` on `Store.get/save/review/pending` and `Engine.resolve_entity/gather_facts/answer/review`, default `"local"`.
- Lookup order: this owner's answer, exact-name rule, shared automated answer, to confirm.
- `Engine(save_automated=False)` writes no automated rows.
- `scripts/upgrade_store.py` rebuilds the committed seed once. The seed is committed already rebuilt.

Exit criteria
- Tests for spec checks 5, 6, 7, 9 and 10.
- `make evals` unchanged. `make test` and `make lint` green.
- Commit: `feat(store): answers kept per person; hosted mode keeps no list`.

### S3. One name, two tools

Files: `erm/assist.py`, `erm/assist_profile.py`, `erm/connectors/bdc.py`, `erm/mcp_server.py`, `app/desk/server.py`, `.claude/skills/reconcile-companies/` (removed), `.claude/skills/lender-watch/SKILL.md` (new), `README.md`, `tests/test_assist.py`, `tests/test_names.py` (new).
- `check_list(engine, items, as_of, owner, profile)` replaces `reconcile_list`. Rows gain `as_of`, `compared_with`, `data_version`, `rule_version`. `rule_version` comes from the source profile.
- Local MCP server: name `lender-watch`, tools `check_lenders`, `confirm_match`, `check_lenders_in_file`. `inspect_sheets` and `how_to_reconcile` leave the tool list; their functions stay in `assist`.
- Skill renamed `lender-watch`, naming only those tools, with the failed-lookup guidance from `inspect_sheets`.

Exit criteria
- Tests for spec checks 2, 11 (local part) and 12. Check 13 for the skill, tool descriptions and README.
- Existing assist tests moved to `check_list`, same assertions.
- `make test` and `make lint` green.
- Commit: `feat(tools): Lender Watch as one name with two tools`.

### S4. The hosted service

Files: `erm/service.py` (new), `erm/auth.py` (new), `erm/mcp_remote.py` (removed), `Makefile`, `tests/test_service.py` (new), `tests/fake_provider.py` (new), `tests/test_excel_addin.py`, `app/desk/server.py` (certificate code shared).
- One Starlette app: `/mcp`, `/api/check`, `/api/confirm`, `/api/inspect`, `/api/status`, `/excel/*`, `/.well-known/oauth-protected-resource`, `/health`.
- `erm/auth.py`: checks a JWT against the provider's public keys (PyJWT, already installed): signature, issuer, audience, expiry. Subject must be in `LW_INVITED`. `401` with `WWW-Authenticate: Bearer resource_metadata=...`, or `403`.
- Engine built with `save_automated=False`, no judge, owner from the token.
- Access log off. One JSON line per request: route, status, milliseconds.
- `/mcp` and `/api/check` calls run inside `telemetry.run`, sources `service_mcp` and `service_api`.
- `/api/status` is public: sign-in on or off, issuer, `LW_EXCEL_CLIENT_ID`, quarters held, data version.
- `make excel` runs the service locally on port 3000 over HTTPS with the Office development certificate.
- Local mode: no sign-in, and refuses to start on any address but `127.0.0.1`.
- `make service` runs it locally. `make mcp-web` is removed.
- Tests use a stand-in provider with its own keys, served in the test.

Exit criteria
- Tests for spec checks 1, 4, 11 (hosted part), 14 and 15.
- `make test` and `make lint` green.
- Commit: `feat(service): one hosted address with sign-in for Excel and Claude`.

### S5. The Excel add-in

Files: `app/desk/excel/manifest.template.xml` (new), `app/desk/excel/manifest.xml` (generated, local), `scripts/make_manifest.py` (new), `app/desk/excel/functions.json`, `app/desk/excel/functions.js`, `app/desk/excel/core.js`, `app/desk/excel/taskpane.js`, `app/desk/excel/taskpane.html`, `tests/excel_addin_check.cjs`, `tests/test_excel_addin.py`.
- Namespace `LW`, function `CHECK(names, [as_of])`. Calls `/api/check` with the in-memory token, in batches of 50.
- No token: returns "Sign in from the Lender Watch panel". After sign-in: full recalculation.
- The panel reads `/api/status`, which needs no sign-in. Hosted: no Claude switch, no `/api/ask`. Local: no sign-in.
- When the panel opens, it refreshes the token silently. If that fails, it shows "Sign in".
- `scripts/make_manifest.py --base-url <url>` writes the manifest from the template.

Exit criteria
- Tests for spec checks 13 (add-in files), 17 and 18.
- `make test` and `make lint` green.
- Commit: `feat(excel): =LW.CHECK on the hosted service, signed in`.

### S6. Tool-choice eval

Files: `evals/tool_choice.yaml` (new), `eval/tool_choice.py` (new), `.github/workflows/tool-choice.yml` (new), `.claude/skills/data-handling/SKILL.md`, `tests/test_tool_choice.py` (new), `Makefile`.
- 30 prompts: 8 naming the job, 6 describing the need, 6 failed lookups, 10 must not call. Public demo companies only.
- Sends the skill text and the tool definitions read from the local server. 3 runs. Stops at $2.
- Workflow modelled on `live-eval.yml`: runs on pull requests that change the service, the MCP server, the skill or the eval files, and by hand. Skips without a key.
- `data-handling` check 3 names this as the second approved exception.
- `make tool-choice` runs it locally.

Exit criteria
- Tests for spec checks 19 and 20.
- One local run with Alexandre's key, result saved to `outputs/test-evidence/excel-claude/tool-choice-run1.txt`, with cost and time.
- `make test` and `make lint` green.
- Commit: `feat(eval): tool-choice eval with must-not-call cases`.

### S7. Deploy files

Files: `deploy/service.Dockerfile` (new), `deploy/fly.toml` (new), `scripts/host-deploy.sh` (new), `Makefile`, `outputs/patches/production-gate-host.patch` (new), `README.md`, `CLAUDE.md`.
- An image with the service, public data and the seed answers. No key, no `.env`, checked by `scripts/check-image.sh`.
- `make host-deploy` checks the approval like `make prod`, builds from the commit, deploys, and waits for `/health`.
- `scripts/host-deploy.sh` runs `fly deploy` from a clean `git archive` of the commit.
- The patch adds to the gate: `fly deploy` and other `fly` commands that change the app, `make host-deploy`, and edits to `deploy/*` and `scripts/host-deploy.sh` all need approval. It adds the test for spec check 16.

Exit criteria
- The image builds and `scripts/check-image.sh` passes on it.
- `make test` and `make lint` green.
- After Alexandre applies the patch: spec check 16 passes.
- Commit: `feat(deploy): hosted service image and person-only deploy`.

### S8. Alexandre: accounts, deploy, real runs

- Fly.io account, a 1 GB volume, secrets set with `fly secrets set`: `LW_AUTH_ISSUER`, `LW_AUTH_AUDIENCE`, `LW_INVITED`.
- `make approve-prod`, then `make host-deploy`.
- Register the two callbacks with the provider.
- Checks 22 to 27. I prepare the 5-name test workbook and a checklist page beforehand.
- I record the measurements: time for 50 names, index build time, monthly cost.

### S9. Verify and open the pull request

- The verifier agent runs every check in a fresh context and reports pass or fail. It fixes nothing.
- `uv run python -m eval.plan_drift plans/engine-in-excel-and-claude.md S<n>` after each step's commit, with the log amended in. Rows go to `plans/engine-in-excel-and-claude-drift.md`.
- Pull request against `main`, with the AI review. Alexandre merges.

## Risks

| Risk | Step it shows up | If it happens |
|---|---|---|
| The provider's sign-in page won't load in an Office dialog, or can't hand the token back | S0 | Stop. Revise spec section 4 before S5. Fallback: the panel shows a one-time code the analyst types into the provider's page |
| The provider gives Claude-registered clients a token we can't check | S4, then S8 | Caught in S8 at the latest. Pick a provider from the research that states JWT audience support |
| Two indexes double memory and start-up time | S1 | Measure. If over the host's memory, build the older quarter's index on first request only |
| A change to the engine moves matching results | S1, S2 | `make evals` at every step. Any change stops the step |
| Claude in Excel behaves differently from Claude on the web | S8 | Record it. Checks 24 and 25 are separate for this reason |
| The September 2026 data appears mid-build and invites scope creep | Any | Out of scope. Logged as a follow-up |

## Sign-in provider and host

Research of 2026-11-21. Prices and capabilities from each provider's own pages, read that day. No account was created and no token was tested.

| Choice | Pick | Why | Monthly cost |
|---|---|---|---|
| Sign-in | **WorkOS AuthKit** | Only provider whose docs say the token's audience equals the `resource` Claude sends. Supports automatic client registration, Claude's published client identity, PKCE, JWT checked with public keys, and invite-only sign-up | $0 (free up to 1 million monthly users) |
| Host | **Fly.io** | Persistent volume that survives restarts and deploys, HTTPS on a `fly.dev` address, one deploy command: `fly deploy` | About $7: 1 GB machine $6.70, volume $0.15 per GB |

Runners-up: Auth0, which needs its "Resource Parameter Compatibility Profile" switched on or Claude's clients fail. Hetzner at about €6, but we'd patch the server and set up HTTPS ourselves.

Settings to switch on in WorkOS: automatic client registration, Claude's published client identity (CIMD), resource indicators (otherwise the audience is the client id), sign-up off with invitations on.

Things to confirm, each with the step that confirms it:

| To confirm | How | Step |
|---|---|---|
| The token's audience for the Excel add-in matches our address | Decode a real token from step 0's sign-in | S0 |
| A personal email can sign in. The docs say tokens may need the email's domain verified on an organization | Alexandre invites a personal address | S0 |
| Turning off sign-up blocks strangers, even through the callback. Some users report it doesn't | Try signing up with an address not invited. The invite list in our server is the second barrier either way | S0 |
| The token's audience for Claude's registered client matches `/mcp` | Decode the token Claude receives, from our own log of the audience claim only | S8 |
| Daily volume snapshots and their cost | Fly's dashboard | S8 |

**Fly builds from the files it's given.** `fly deploy` uploads its working folder to Fly's builder. So `scripts/host-deploy.sh` runs it from a clean `git archive` of the commit, the same way `make prod` does, so `.env` and `data/raw` can't be uploaded.
