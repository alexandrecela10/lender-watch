# Analyst Desk: entity reconciliation in the workbook

**Decision to make:** treat the engine as one connector behind Claude and Excel, not as a separate app.

**What it is:** a triage assistant for investment analysts, inside the workbook they already use. It links the company names in their list to the names lenders use in SEC filings, then adds what lenders report.

**Goes in:** a workbook or list of company names. **Comes out:** the same sheet with lender columns, plus one row per loan with its filing link. **Can't do yet:** cover banks, predict anything, or claim real users. No investor has tested it. Pain is inferred from public signals.

## Three ways in, one engine

| What the analyst knows | What they do | What happens | Tool |
|---|---|---|---|
| The tool | Types `=RECONCILE(A2:A6)` or asks Claude to run it | Results spill onto the sheet | `reconcile_list`, `enrich_spreadsheet` |
| The problem | Asks "how would I reconcile these companies?" | Plain steps, limits, an offer to run it | `how_to_reconcile` |
| Neither | Writes an XLOOKUP that returns #N/A | The assistant says why and offers the fix | `inspect_sheets` |

**Example and counterfactual.** Exabeam appears in filings only as LogRhythm. With the desk, the analyst sees LogRhythm's loans at 86.2% of the amount owed. Without it, XLOOKUP returns #N/A, and a looser match links "Foundation" to Foundation Risk Partners, a different company.

## How it maps to the three layers

| Layer | Here | Owner in the pattern |
|---|---|---|
| Where people work | The workbook and assistant panel; a skill and connector for Claude itself | Investment teams |
| Tested tools | `erm/assist.py` and the MCP server. Code links names and does the maths | Applied AI team |
| Organised data | SEC filings with a source on every value, and saved human answers | Data team |

## What was measured

| Check | Result |
|---|---|
| Real Claude picked the right tool from the analyst's words | 15 of 15: 5 prompts, 3 runs each, public sample. Small test, not a rate. An earlier version missed "reconcile these" because Claude couldn't see the names; that's fixed |
| A lookup across the sample tabs | Finds 0 of 5 names |
| Linking the same 5 names | 2 flagged, 3 matches held for a person |

**Observed:** the numbers above, on public filings. **Assumption:** analysts would use this inside Excel. **Hypothesis:** if the offer appears at the failed lookup, then analysts who've never heard of the tool will use it, because the moment of need is the moment of the offer. Metric: share of failed name lookups that lead to an accepted link. Baseline unobserved; measure in a pilot.

**Must not get worse:** no number without a filing, and no match decided over a person's answer.

## What this is not, yet

- The workbook in the video is a working stand-in for Excel, built on the real engine.
- The Excel add-in and web connector are built, but neither has run inside real Excel or Claude in Excel. Steps are below.
- All match labels so far are Claude's, not a person's.
- Claude mode sends the sheet's company names to Anthropic. It's off by default. A confidential list needs a model inside the investor's perimeter.

## Real Excel: two routes

| | Excel add-in | Claude in Excel |
|---|---|---|
| Who it's for | Analysts who work in formulas | Analysts who ask Claude |
| What they get | `=ERM.RECONCILE(A2:A6)` and a panel that offers the fix at a failed lookup | Claude calls the engine from its own Excel panel |
| Where names go | This computer, unless Claude is ticked | Through Anthropic to wherever the connector is hosted |
| Needs | Excel, plus a trusted local certificate | A public HTTPS address, or an MCP tunnel inside a private network |

**Checked so far:** Microsoft's validator accepts the manifest. The real panel ran over HTTPS against the real server, with a stand-in for Excel's objects: formula, failed-lookup offer, results written beside the list, 65 loans on a new tab, a person's answer. The web connector answered over HTTP and refused a made-up host name.

**Not checked:** anything inside real Excel, including whether the formula spills and the recalculation event fires.

**Web connector limits:** public sample only, no AI judge, 50 names at a time, no tool that reads files or changes saved answers. Anyone with the address can call it.

### Try the add-in

1. Install Excel, or sign in at excel.cloud.microsoft.
2. Run `npx office-addin-dev-certs install`. It asks you to trust a certificate on your computer.
3. Run `make excel`.
4. Add `app/desk/excel/manifest.xml`. In Excel on the web: Home, Add-ins, More Add-ins, Upload My Add-in. On a Mac: copy it to `~/Library/Containers/com.microsoft.Excel/Data/Documents/wef/`, then restart Excel.
5. Type `=ERM.RECONCILE(A2:A6)`.

### Try Claude in Excel

1. Host `make mcp-web` at a public HTTPS address, with `ERM_MCP_BIND` and `ERM_MCP_HOSTS` set.
2. Add that address at Customize, Connectors, as a custom connector.
3. Upload `.claude/skills/reconcile-companies/` in Claude's skill settings.

## Run it

`make desk`, then open http://127.0.0.1:8765. Video: `outputs/portfolio/lender-watch/analyst-desk-demo.mp4` (59 seconds, no sound).
