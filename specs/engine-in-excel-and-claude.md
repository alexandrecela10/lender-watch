# Spec: Lender Watch inside real Excel and real Claude

Source: `intent/engine-in-excel-and-claude.md` (commit `ce9220e`, approved 2026-11-20). Status: draft, 2026-11-20. Fresh pass done and its 12 concerns resolved below, pending Alexandre's review.
Evidence: the repo's code, its measured results on public filings, and Claude's connector docs read on 2026-11-20. Nothing has run inside real Excel or real Claude. No LP or GP analyst has been interviewed. The pain is inferred.

## Bottom line

- Lender Watch gets one web address, with sign-in, that an invited analyst can use from Excel and from Claude.
- Excel and Claude ask the same question of the same code, so they get the same numbers.
- The analyst sees one product name and one tool: check a list of companies. The only other action is confirming a match.
- Every row says which quarter it uses. The analyst can ask for either of the two quarters held today.
- A confirmed match is saved under the analyst's own sign-in, survives a restart, and is never asked again.
- The hosted version takes public or non-confidential lists only, makes no AI calls, and keeps no list after answering it.
- Two steps need Alexandre at the keyboard: creating the sign-in and hosting accounts, and the first runs in real Excel and real Claude.

## Problems this solves

| Problem | Today | Hypothesis (if/then/because) | Success metric (target) | Expected impact |
|---|---|---|---|---|
| Never run inside real Excel | 0 recorded runs | If the add-in is served from a public HTTPS address with its own sign-in, then it loads in Excel on the web, because Excel only needs a trusted HTTPS manifest | Recorded runs of `=LW.CHECK` in real Excel: 1 or more, with the failed-lookup offer shown | Proves the formula path. Analyst use stays unobserved |
| Never run inside real Claude | 0 recorded runs | If the connector speaks the OAuth flow Claude's connector docs describe, then Claude can add and call it, because that is the documented path | Recorded calls: 1 or more in Claude, 1 or more in Claude in Excel | Proves the chat path |
| Excel and Claude could disagree | Unobserved. Two code paths shape the result | If both call one function, then results match, because there is only one function | Same list, same quarter, the data returned to Excel against the data returned to Claude: 5 of 5 names identical | Analysts can switch front end without doubting the numbers |
| Anyone with the address can call it | All calls answered without sign-in | If every call needs a token from an invited account, then strangers get nothing, because the server checks each token | Calls without a valid invited token answered, on any route: 0 | Safe to share the address |
| Saved answers vanish | 0 survive a restart of the hosted connector | If answers sit on a persistent disk, then they survive, because nothing writes them to a temp folder any more | Confirmed answers present after a restart: all | Analysts never answer the same question twice |
| The quarter is fixed in code | 1 quarter, hard-coded | If the quarter is a request input with a default, then the analyst can choose, because nothing else depends on the constant | Quarters an analyst can ask for: 2 | "As of" works |
| Results can't be reproduced | Unobserved | If every row carries the quarter, data version and rule version, and nothing else varies, then a repeat call matches, because the inputs are pinned | Same request twice: identical rows | A number shown last week can be shown again |
| Too many names and tools | 5 product names; 7 local and 4 hosted tools; 2 tools in the skill that don't exist hosted | If both servers share one name and the same 2 tools, and the skill names only those, then Claude can't be sent to a missing tool | Old names left in the manifest, panel, skill and tool descriptions: 0. Tools: 2 hosted, 3 local. Tools named in the skill but missing: 0 | Easier to find and to trust |

**Must not get worse:** precision 1.000 and recall 0.936 on the answer key, as measured 2026-11-02, with the 30 June index giving the same word counts as the eval's table. 0 values shown without a filing link and row. AI judge off by default, and no AI call at all from the hosted version. No number shown from a match nobody confirmed. A person's answer beats every automated answer. 0 company names, emails, sign-in codes or tokens in logs. `make test`, `make lint` and `make evals` green. The committed seed file `data/public/decisions.sqlite` unchanged by any run.

**Not tackled:**
- Installing the add-in for a group. Missing: Microsoft 365 admin rights, and a team to install it for.
- Confidential lists. Missing: the private route, a copy running inside a client's own systems.
- Answers shared across a team. Missing: a decision on who may overrule whom.
- Quarters beyond the two held today. Missing: a scheduled SEC download. The September 2026 data is probably out; adding it is a data task, not part of this build.
- Claude's tool choice on a larger prompt set, including requests where the tool must stay silent. Missing: the prompt set. Planned as a separate eval.
- Matching two of the analyst's own lists. Out of scope by decision.
- The panel's chat with Claude in the hosted add-in. Removed there; analysts who want chat use Claude in Excel.

## Concerns and resolutions

One row per concern. "Spec" means raised while writing this spec. "Fresh pass" means a separate review with no access to this conversation, on 2026-11-20. Decisions by the spec session, pending Alexandre's review.

| # | Concern | Raised by | Decision | Why |
|---|---|---|---|---|
| 1 | Claude's connectors accept OAuth with automatic client registration or a published client identity. A plain API key is in limited beta only. Building an OAuth server ourselves is the riskiest code in the build. | Spec | Use a hosted sign-in provider. Our server only checks tokens. The provider's must-haves are in section 4. The plan picks it and cites its price. | The MCP SDK in the repo (2.3.0) checks tokens. A provider handles passwords, resets and registration. |
| 2 | Excel needs the same sign-in. Custom functions can't open a sign-in page themselves. | Spec | The panel opens the provider's sign-in in an Office dialog. Details in section 4. | One provider and one account for both front ends. Riskiest Excel step, so it's tested first in the plan. |
| 3 | Claude's servers call from `160.79.104.0/21`. A firewall that allows only that range would block Excel. | Spec | No IP allowlist. Every call needs a valid token instead. | Excel calls from the analyst's browser, from any address. |
| 4 | A list sent to the hosted version reaches the host, and through Claude reaches Anthropic. | Spec | Sign-in page and docs say "public or non-confidential lists only". The hosted image has no AI judge and no key. | Matches the intent's decision. |
| 5 | Per-person answers change the decision store. Existing answers have no owner. | Spec | Add an `owner` column. Full rules in section 3. | Keeps "a person's answer wins", per person. |
| 6 | The search index cache loads whatever file exists, even after the data changes. | Spec | The cache name includes a fingerprint of the holdings file. | Otherwise a data refresh could match on last quarter's names. |
| 7 | One index over all quarters doubles word counts. The exact-name rule and the rare-word search depend on those counts, so matching would change while `make evals`, which hard-codes the 30 June counts, stays green. | Fresh pass (replaces the spec's first answer) | One index per quarter, cached under data fingerprint and quarter. Each request uses its quarter's index. A test checks that the 30 June index gives the same word counts as the eval's table. | Matching on 30 June stays exactly what was measured. |
| 8 | An invited analyst's sign-in is personal data. | Spec | Store the provider's opaque user id only, never an email. Logs carry no user id. The invite list is an environment setting, not in git. | `api-and-logging` rule 2 and the names policy. |
| 9 | Deploying to a host is a production change. Today the gate covers local Docker only. | Spec | The production gate also blocks the host's deploy command for agents, with a test. A person deploys. | `CLAUDE.md`: agents never start or change prod. |
| 10 | Excel lists can exceed 50 names, the per-call limit. | Spec | The add-in sends batches of 50 and joins the results. | Claude's tool calls time out at 240 seconds. |
| 11 | With an owner in the key, the shared "unsure" row stays after a person answers, so `pending()` would list it forever. `Store.get` and `Store.review` take no owner. | Fresh pass | Every store and engine call that reads or writes answers takes `owner`. `pending(owner)` leaves out pairs that owner answered. Section 3 lists each call. | No caller is left guessing which person's answers apply. |
| 12 | With the judge off, every unclear name is saved as a shared "not checked" row with the raw company name. On a persistent disk, every list any analyst sends would be kept and shown to others. | Fresh pass | The hosted version saves no automated rows at all. Only a person's confirmation is stored, under that person. A list is not kept after the answer. | "Not checked" rows change no result. Keeping them would leak one analyst's list to another. |
| 13 | The review app opens the committed seed file directly. Changing a SQLite key means rebuilding the table, which would rewrite that file. | Fresh pass | Ship the seed already upgraded, in the same commit. The upgrade code runs only on copies and on local stores, in one transaction. A test checks the seed's hash is unchanged after a run. | The committed file changes once, on purpose, and never by accident. |
| 14 | The Excel panel calls 5 routes, not 2. One of them, `/api/ask`, sends names to Anthropic when the Claude switch is on. | Fresh pass | Hosted routes listed in full in section 6. `/api/ask` and the Claude switch are left out of the hosted panel. | Keeps "no AI call from the hosted version" and keeps the failed-lookup offer working. |
| 15 | Excel sign-in lacked expiry, refresh, token storage and the domain rule for Office dialogs. A formula won't recalculate after sign-in on its own. | Fresh pass | Section 4: short-lived token in memory, silent refresh when the panel opens, no long-lived token in Office storage, dialog pages on the add-in's own domain, full recalculation after sign-in. | Otherwise the builder guesses, and Office storage isn't encrypted. |
| 16 | Claude registers its own client and asks for the `/mcp` address as the audience. Some providers then issue tokens our server can't check. The invite list needs ids that exist only after sign-up. | Fresh pass | Provider must-haves and the invite steps are in section 4. | A provider that fails these blocks the Claude path entirely. |
| 17 | The add-in's sign-in callback address carries a one-time code, and the web server's access log records full addresses. | Fresh pass | The service turns off the default access log and writes its own, with route and status only. A test drives the callback and checks the log. | Codes and tokens must never reach a log. |
| 18 | One SQLite connection shared across simultaneous requests can fail when Excel recalculates many cells at once. | Fresh pass | WAL mode and one write lock in the store. A test runs simultaneous confirmations. | Concurrent writes must not lose an answer. |
| 19 | Naming the core function after lenders puts lender terms into the source-agnostic layer. | Fresh pass | The core function is `check_list(engine, items, as_of, owner, profile)`. The name `check_lenders` lives only in the server layer. The flag rule's version comes from the source profile. | `api-and-logging` rule 5. |
| 20 | `LATEST` is used by the desk, the review app and two lines of `gather_facts` that the spec didn't name. | Fresh pass | Section 2 lists each caller and its replacement. | A missed caller would silently keep the old quarter. |
| 21 | Acceptance checks missed some metrics and compared Claude's wording instead of its data. | Fresh pass | Checks rewritten below: old-names search, local tool list, deploy gate, every route checked for sign-in, a confirmation before the restart check, and data compared rather than wording. | Every metric now has a binary check. |

## 1. One function behind every front end

**What it is.** A new function, `check_list(engine, items, as_of=None, owner="local", profile=PROFILE)`, in `erm/assist.py`. It replaces `reconcile_list`. The MCP tool, the Excel API, the local desk and the command line all call it. The servers expose it as `check_lenders`.

**Goes in.** Up to 50 items, each `{name, sector?, sponsor?}`. An optional quarter-end date. The owner id, set by the server from the token, never by the caller.

**Comes out.** Today's `company_row` shape, plus on every company row:

| Field | Meaning |
|---|---|
| `as_of` | The quarter-end date the values describe |
| `compared_with` | The earlier quarter used for the change, or null |
| `data_version` | First 12 characters of the holdings file's fingerprint |
| `rule_version` | Version of the flag rule, from the source profile, starting at `flag-v1` |

Each loan keeps `filing_url`, `filing_row` and `filed`. A company with no confirmed match returns no numbers, only `to_confirm` items.

**Same output twice.** The same items, quarter, owner, data version and saved answers give identical rows. The request id is in the log, not the result.

## 2. Choosing the quarter

- `erm/api.py` drops the `LATEST, PRIOR` constants. `Engine.periods()` lists the quarter-ends held. `Engine.latest()` returns the newest.
- `as_of` defaults to the latest. `compared_with` is the quarter before it, or null.
- An `as_of` not held returns an error naming the quarters held. It never falls back silently.
- Asking for 31 March 2026 today gives values with no change, since no earlier quarter is held.
- One index per quarter, built on first use and cached under data fingerprint and quarter (concern 7).
- `Engine.doc_freq` and `total_docs` become per quarter, read from that quarter's index.

Callers of the old constant and their replacement:

| Caller | Today | After |
|---|---|---|
| `erm/api.py` `_load_index` | Builds from `LATEST` | Builds per quarter |
| `erm/api.py` `gather_facts` | `facts_for(rows, LATEST, PRIOR)`, plus `excluded` and `n_positions_used` filtered on `LATEST` | Takes `as_of`; all three use it and its `compared_with` |
| `app/desk/server.py` demo workbook | Filters on `LATEST` | Uses `engine.latest()` |
| `app/review.py` header text | Names `LATEST` | Names `engine.latest()`. The review app keeps showing the latest quarter only |

## 3. Saved answers, per person

**Store.**
- `decisions` gains `owner TEXT NOT NULL DEFAULT ''`. The key becomes `(owner, pair_id)`.
- Person answers carry the analyst's owner id. Automated answers carry `""`.
- A store without the column is rebuilt in one transaction on first open. Existing person answers get `owner = "local"`. Automated answers keep `""`.
- The committed seed `data/public/decisions.sqlite` ships already rebuilt (concern 13).
- WAL mode, one write lock (concern 18).

**Calls that gain `owner`:** `Store.get`, `Store.save`, `Store.review`, `Store.pending`, `Engine.resolve_entity`, `Engine.gather_facts`, `Engine.answer`, `Engine.review`. Default `"local"`, so the command line, the review app and the evals keep working unchanged.

**Lookup order** for a candidate: this owner's person answer, then the exact-name rule, then a shared automated answer, then "to confirm".

**`pending(owner)`** returns open pairs, minus pairs this owner has answered.

**Hosted mode** (concern 12): `Engine(save_automated=False)`. No automated row is written. Only a person's confirmation is stored. Nothing else from the list is kept.

**Isolation:** `confirm_match` writes for the caller's owner only. No call reads another owner's answers.

## 4. Sign-in

**Provider must-haves** (concern 16). The plan picks a provider that meets all of these, and cites its price:
- Automatic client registration, or Claude's published client identity. PKCE.
- Signed JWT access tokens that our server checks with the provider's public keys.
- Audience set to the `/mcp` address for clients Claude registers, and an audience our server accepts for the add-in.
- Reachable from Anthropic's addresses.

**Server, hosted.**
- Serves protected resource metadata. An unsigned call to any protected route gets `401` with a `WWW-Authenticate` header pointing at it.
- The provider is the only authorization server listed.
- Each token is checked: signature, issuer, audience, expiry.
- The token's subject must be on the invite list, `LW_INVITED`. Otherwise `403`.
- Callbacks registered with the provider: `https://claude.ai/api/mcp/auth_callback` and the add-in's own callback page.
- The default access log is off. The service logs route, status and timing only (concern 17).

**Invite steps.**
1. Alexandre invites the analyst in the provider's dashboard.
2. The analyst signs up and gets a `403` page showing their user id.
3. Alexandre adds that id to `LW_INVITED` and redeploys.

**Excel** (concern 15):
- The panel opens the provider's sign-in with `Office.context.ui.displayDialogAsync`. The dialog's first page and its callback page are on the add-in's own address, so the callback can return the result to the panel.
- The access token stays in memory in the add-in's shared runtime. It is never written to Office storage.
- When the panel opens, it refreshes the token silently through the provider. If that fails, it shows "Sign in".
- After sign-in, the add-in recalculates the workbook in full, so `=LW.CHECK` cells update.
- A formula with no valid token returns "Sign in from the Lender Watch panel".

**Local.** No sign-in. The server listens on `127.0.0.1` only, and the owner is `"local"`. Told to listen on any other address without sign-in settings, it refuses to start.

## 5. One name, two tools

| Where | Today | After |
|---|---|---|
| Product name | Lender Watch, Entity Reconciliation Machine, Analyst Desk, ERM, reconcile-companies | Lender Watch |
| MCP server name | `entity-reconciliation` locally, `lender-watch` hosted | `lender-watch` in both |
| Hosted tools | 4 | `check_lenders`, `confirm_match` |
| Local tools | 7 | The same two, plus `check_lenders_in_file` |
| Excel formula | `=ERM.RECONCILE(A2:A6)` | `=LW.CHECK(A2:A6, [as_of])` |
| Claude skill | `reconcile-companies`, naming 6 tools | `lender-watch`, naming only the tools above |

- `check_lenders` takes `companies` and an optional `as_of`. Its description says when to use it, including after a failed name lookup, and that it takes 50 names at a time.
- `confirm_match` takes `name`, `mention_key`, `same` (yes or no) and an optional `reason`.
- `inspect_sheets` and `how_to_reconcile` leave the tool list. Their guidance moves into the skill. The Excel panel keeps the inspect code through `/api/inspect`.
- `resolve_entity`, `gather_facts`, `enrich_table` and `review` stay as Python functions for tests, evals and the command line.
- The engine's internal name stays in code and docs for developers. Nothing an analyst sees uses it.

## 6. One hosted service

A new entry point, `erm/service.py`, serves on one port:

| Route | Sign-in | What it does |
|---|---|---|
| `/mcp` | Required | The connector |
| `/api/check` | Required | `check_list`, for the formula and the panel |
| `/api/confirm` | Required | A person's answer |
| `/api/inspect` | Required | Whether the workbook's name columns line up, for the failed-lookup offer |
| `/api/status` | Required | Data quarter and version, signed-in state |
| `/excel/*` | None | The add-in's files and its sign-in pages |
| `/.well-known/oauth-protected-resource` | None | Sign-in metadata |
| `/health` | None | Health check |

- `/api/ask`, `/api/reconcile` and `/api/answer` are not served hosted. The local desk keeps them.
- A second Dockerfile target, `service`, runs it. The review-app image doesn't change.
- Settings: `LW_BASE_URL`, `LW_AUTH_ISSUER`, `LW_AUTH_AUDIENCE`, `LW_INVITED`, `LW_DATA_DIR`.
- Saved answers and run records live in `LW_DATA_DIR`, on the host's persistent disk.
- The add-in manifest is generated for one base address by a script, from one template.
- The same image runs on a private machine with different settings. This build doesn't test that.
- Hosting: a container host with a persistent disk and HTTPS. The plan picks one and cites its price. Alexandre creates the account and runs each deploy.

## Acceptance checks

**Automated, in `make test`:**
1. Through the MCP tool and through `/api/check`, the 5 demo names return identical rows.
2. Two identical calls return identical rows.
3. Each held quarter works as `as_of`. An unknown date returns an error naming the held quarters.
4. On `/mcp`, `/api/check`, `/api/confirm`, `/api/inspect` and `/api/status`: no token gives `401` with the metadata header; a valid token for someone not invited gives `403`; a bad signature, wrong audience or expired token gives `401`. Tested with a stand-in provider and its own keys.
5. Owner A's confirmation changes A's result and not B's. `pending("A")` drops the pair A answered. Answers survive closing and reopening the store.
6. Rebuilding an old store keeps every person answer, now with `owner = "local"`.
7. The seed file's hash is unchanged after a full test run.
8. A changed holdings file builds a new index. The 30 June index gives the same word counts as `eval/offline.py`'s table.
9. In hosted mode, a list with unclear names writes no row to the store.
10. Ten simultaneous confirmations all land.
11. The hosted tool list is exactly `check_lenders` and `confirm_match`. The local list is those plus `check_lenders_in_file`.
12. The skill names only tools that exist.
13. A text search of the manifest, panel, functions file, skill and tool descriptions finds 0 of the old names: Entity Reconciliation, Analyst Desk, ERM., RECONCILE, reconcile-companies.
14. No log line from these tests contains a test company name, email, sign-in code or token, including after driving the callback route.
15. The local server refuses to listen beyond `127.0.0.1` without sign-in settings.
16. The production gate blocks an agent running the host's deploy command.
17. The add-in sends 120 names as 3 batches and spills 120 rows in order (`tests/excel_addin_check.cjs`).
18. The hosted panel has no Claude switch and never calls `/api/ask`.

**Done by Alexandre, recorded under `outputs/test-evidence/excel-claude/`:**
19. Add the manifest in Excel on the web, sign in, type `=LW.CHECK(A2:A6)`. Screenshot of the spilled rows.
20. Break an XLOOKUP on company names, and screenshot the panel's offer.
21. Add the connector in Claude, sign in, ask about the same 5 names. Save the tool's returned data from the conversation.
22. The same in Claude in Excel.
23. Confirm one match in Excel. Restart the hosted service. Repeat check 21: the match is still confirmed.
24. Compare the data from checks 19 and 21: same values for 5 of 5 names.

**Measured, written into the plan's results:**
- Seconds for 50 names, hosted, first call and repeat call.
- Index build time per quarter.
- Hosting and sign-in cost per month, from the providers' price pages, with date.
