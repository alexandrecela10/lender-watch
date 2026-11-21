# Step 8 checklist: Lender Watch in real Excel and real Claude

For Alexandre. About 2 hours in total, in four sittings. Save each screenshot in this folder under the name given.
Workbook for every check: `lender-watch-test.xlsx` (5 public companies, and a Lenders tab whose lookup fails on purpose).

## A. Sign-in account (15 minutes, any time)

1. Create a free WorkOS account. In AuthKit, switch on:
   - dynamic client registration
   - client ID metadata documents (Claude's published identity)
   - resource indicators (otherwise the token's audience is the client id, and our server refuses it)
   - sign-up off, invitations on
2. Create one public client for the Excel add-in, with PKCE and no secret. Note its client id.
3. Invite your personal email.
4. Send me the AuthKit issuer address and the client id. Neither is a secret. Never send a secret.

## B. Excel sign-in, on your computer (20 minutes, after A)

This tests the riskiest part before anything is hosted.

1. In your own terminal: `npx office-addin-dev-certs install`, then `make excel` with the sign-in settings I send you.
2. Excel on the web: Home, Add-ins, More Add-ins, Upload My Add-in, choose `app/desk/excel/manifest.xml`.
3. Open Lender Watch on the Home tab. Click **Sign in**, sign in with your personal email.
   - Pass: the panel says "Signed in" and shows the audience ending in `/mcp`. Screenshot: `b1-signed-in.png`.
4. Sign out, then try an email that wasn't invited.
   - Pass: refused, by the provider or by our "not invited yet" message. Screenshot: `b2-not-invited.png`.

If step 3 fails, stop. I revise the sign-in design before going further.

## C. Deploy (30 minutes)

1. `brew install flyctl`, then `fly auth login`.
2. `fly apps create <name>`. If the name isn't `lender-watch`, tell me and I update `deploy/fly.toml`.
3. `fly volumes create lw_data --size 1 --region lhr`.
4. `fly secrets set LW_AUTH_ISSUER=... LW_AUTH_AUDIENCE=https://<name>.fly.dev/mcp LW_INVITED=<your user id> LW_EXCEL_CLIENT_ID=...`
   Your user id is shown on the "not invited yet" message the first time you sign in.
5. In WorkOS, add these callbacks: `https://claude.ai/api/mcp/auth_callback` and `https://<name>.fly.dev/excel/signin-callback.html`.
6. Apply the gate patch: `git apply outputs/patches/production-gate-host.patch`, then `make test`. Commit it.
7. `make approve-prod`, then `make host-deploy`.
   - Pass: it ends without an error, and `https://<name>.fly.dev/health` shows `{"ok":true}`.

## D. Real runs (45 minutes)

Make the hosted manifest: `uv run python scripts/make_manifest.py --base-url https://<name>.fly.dev --auth-domain <issuer> --out outputs/manifest-hosted.xml`.

| # | Do | Pass when | Save as |
|---|---|---|---|
| 22 | Add `outputs/manifest-hosted.xml` in Excel on the web, sign in, type `=LW.CHECK(A2:A6)` in F2 of the Portfolio tab | 5 rows spill, KnowBe4 flagged, each with a filing link | `d22-formula.png` |
| 23 | Look at column D, which shows #N/A | The panel offers to link the names | `d23-offer.png` |
| 24 | claude.ai: Customize, Connectors, add `https://<name>.fly.dev/mcp`, sign in. Upload `.claude/skills/lender-watch/` as a skill. Ask: "What do lenders say about KnowBe4, Apex Group, Foundation, Exabeam and Anaplan?" | Claude calls check_lenders and names a filing for each number | `d24-claude.png`, plus the tool result copied into `d24-tool-result.json` |
| 25 | The same question in Claude in Excel | Same | `d25-claude-excel.png` |
| 26 | In the Excel panel, confirm one match ("Same company" or "Different"). Then `fly machine restart`, after `make approve-prod`. Repeat 24 | The match you answered isn't asked again | `d26-after-restart.png` |
| 27 | Compare 22 with 24 | Same value for 5 of 5 names | Write the result in `results.md` |

## E. One name

Before the pull request is merged: who is the first analyst to try it? A name, or "none yet".
