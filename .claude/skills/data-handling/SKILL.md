---
name: data-handling
description: Data rules for this repo. Use before planning, describing or making any change that touches data/, erm/connectors/ (SEC BDC loading), test fixtures, demo or sample text, SEC EDGAR downloads, or anything that sends data to an external API such as the Anthropic judge. Also use when someone asks what data we may use, store or send, or how a new data source should be added.
---

# Data handling

These checks come from the Constraints section of `intent/lp-credit-readthrough.md`. Run every check that applies before you finish the change.

1. **Public data only.** The change adds data from SEC EDGAR, SEC BDC data sets or sponsor websites, nothing else. No employer, client or counterparty data appears in code, fixtures, docs or demo text, and no organisation Alexandre is applying to is ever named. Company names from public sources are fine. Demo companies are public companies named in public filings.
2. **Every value keeps its source.** Each fact carries its filing URL and filing row (`filing_url`, `filing_row`). A value with no source is dropped, never shown. Check new columns and new outputs for this.
3. **The AI judge stays off by default.** Anything that sends company names to a third party runs only when someone turns the judge on: `--use-judge` on the command line, the checkbox in the app, or `ERM_USE_JUDGE=1` for the MCP server. A list under fund confidentiality terms runs with it off, or with a model inside the LP's perimeter. Never add a new external call that is on by default. One approved exception: the CI live judge check (`eval/live.py`, `specs/ai-drift-tracking.md`), which sends answer-key data from public filings only.
4. **A person's answer wins.** A saved human decision on a match overrides every automated answer and persists across runs. A change to matching or storage must keep that order.
5. **SEC access rules.** Declared User-Agent from `.env`, 5 requests per second at most, every download cached under `data/raw/` (git-ignored). Read from the cache before fetching again.
6. **Keys stay in `.env`.** Never print, log, commit or paste a key. Read keys from the environment only.
7. Also apply the data rules in `CLAUDE.md` under "Things Claude gets wrong" (`ddate` as period, local-currency principal, size-weighted flags).
8. In your summary, state which checks applied to this change and how each was met, for example: "Checks 2 and 5 applied: new column keeps `filing_url`; downloads go through the cache."
