# Lender Watch

**See which companies owned by private equity firms have had their loans marked down by lenders, with the filing behind each number.**

Private equity firms own companies, and those companies borrow money. Some lenders must publish every loan each quarter, and what they think it's worth today. A value well below the amount owed can mean a lender expects trouble.

The catch is names. One company, KnowBe4, sits with 10 funds under 9 different descriptions. This tool matches your list of names to the filings and shows the result.

- **Try it:** [the demo](https://lender-watch.streamlit.app) | [the case study](https://alexandrecela10.github.io/projects/lender-watch/)
- **Goes in:** a spreadsheet of company names.
- **Comes out:** the same spreadsheet with a flag per company, plus one row per loan with its filing link.
- **Can't do yet:** cover banks, which don't publish loans, or say whether a flag predicts anything. No investor has tested it. Values are lenders' own estimates, not market prices, and this isn't investment advice.

Results and limits: [`outputs/analyses/matching-comparison.md`](outputs/analyses/matching-comparison.md).

## Run it on your own computer

Use this for a private list. By default nothing leaves your computer, and you confirm unclear matches yourself.

```
uv sync
uv run streamlit run app/review.py
```

The app reads the public sample in `data/public/` until you build the full data:

1. Set `SEC_USER_AGENT` in `.env` to your name and email, as SEC asks.
2. Download `soi.tsv` files from SEC's [BDC data sets](https://www.sec.gov/data-research/sec-markets-data/bdc-data-sets) into `data/raw/bdc/<month>/`.
3. Build the table:

```
uv run python -c "import glob; from erm.connectors.bdc import load_soi; load_soi(glob.glob('data/raw/bdc/*/soi.tsv')).to_parquet('data/holdings_clean.parquet', index=False)"
```

**Spreadsheet:** `uv run python -m erm.cli enrich data/demo/sample_list.csv --name-column Company --sector-column Sector --sponsor-column Owner --out enriched.xlsx`

**Tool for AI agents:** `uv run python -m erm.mcp_server`

**Inside a workbook:** `make desk`, then open http://127.0.0.1:8765. A workbook with an assistant beside it, on the same engine. Type `=RECONCILE(A2:A6)`, ask how to reconcile a list, or write a lookup that fails and it offers the fix. Names stay on your computer unless you tick "Let Claude answer".

**In real Excel:** `app/desk/excel/` is an add-in with `=ERM.RECONCILE(A2:A6)`. `make excel` serves it. `make mcp-web` is a web connector for Claude in Excel. Neither has run inside real Excel yet. Steps: [`outputs/prototypes/analyst-desk/analyst-desk.md`](outputs/prototypes/analyst-desk/analyst-desk.md).

**Tests:** `uv run pytest`

**AI judge (optional):** put `ANTHROPIC_API_KEY` in `.env`, then use `--use-judge`, the app checkbox or `ERM_USE_JUDGE=1`. It sends the name, industry and owner of unclear companies to Anthropic, so check your fund agreements first. It cuts the names you must confirm from 45% to 11%.

## Layout

| Path | What it does |
|---|---|
| `erm/textparse.py` | Cleans names and reads a borrower's name out of a filing row |
| `erm/connectors/bdc.py` | The SEC source, and the rules that leave out unusable rows |
| `erm/retrieve.py` | Searches by name, name variants and spelling |
| `erm/match/judge.py` | Optional AI judge for unclear pairs. It never produces a number |
| `erm/match/aliases.py` | Web research for other names a company borrows under. Tested, not in the product |
| `erm/signals.py` | Loan-by-loan facts, and flags on the average weighted by loan size |
| `erm/store.py` | Saved answers. A person's answer overrides everything |
| `erm/api.py` | `resolve_entity`, `gather_facts`, `enrich_table`, `review` |
| `erm/assist.py` | The ways in: notices when lists don't line up, explains how, runs a list |
| `app/desk/` | Analyst Desk: the workbook and assistant |
| `eval/` | Answer key, method comparison, filing check |
| `erm/match/linkage.py`, `features.py` | Scoring model, tested and dropped; kept for the comparison |

## Checks on GitHub

- **CI** (`.github/workflows/ci.yml`): tests, style check and the offline eval gate on every pull request, every push to `main` and nightly.
- **AI review** (`.github/workflows/review.yml`): `REVIEW.md` on every pull request. It reports; a person merges.
- **Live judge check** (`.github/workflows/live-eval.yml`): asks the AI judge again about 145 answer-key pairs, on judge changes and every Monday. It fails below precision 0.97 or recall 0.90. Results on `main` go to the issue "Live judge check history". GitHub turns a weekly schedule off after 60 days with no repo activity; CI warns when the last check is more than 8 days old.
