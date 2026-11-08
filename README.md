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
| `eval/` | Answer key, method comparison, filing check |
| `erm/match/linkage.py`, `features.py` | Scoring model, tested and dropped; kept for the comparison |

## Run it in Docker

The image holds the public sample data only. It runs in public mode, so it has no AI judge and needs no key.

- **Try it:** `make dev` builds the image and serves the app at `http://localhost:8501`. Code changes reload.
- **Approve a prod change:** run `make approve-prod` in your own terminal and type the code it shows. One approval covers one change, for 15 minutes, at the current commit. Prod refuses to start or roll back if `compose.yaml` differs from the commit.
- **Deploy:** `make prod` builds the current commit, refuses an image with a key or a `.env`, runs it, and records it as good once it answers its health check.
- **Roll back:** `make rollback` returns prod to the previous good image. If that image fails its health check, the current one is put back.
- **Rehearse:** `make rehearse-rollback GOOD=<commit> NEW=<commit>` tries a rollback in a separate Docker project on port 18501. Real prod is not touched. Last run: [`outputs/test-evidence/stage5/rehearsal.log`](outputs/test-evidence/stage5/rehearsal.log).
- **Stop prod:** `make prod-down` stops the app and keeps the images.
- **Agents:** `.claude/hooks/production-gate.sh` blocks an agent from starting or changing prod until a person has approved. No agent can approve. Each decision is logged in `~/.erm/deploy/gate.log`.
- **Limit:** the gate reads command text, so a script an agent wrote could hide a command. The deploy and rollback scripts check the approval again. The hook lives in the repo, so someone who can edit the repo can remove it.

## Checks on GitHub

- **CI** (`.github/workflows/ci.yml`): tests, style check and the offline eval gate on every pull request, every push to `main` and nightly.
- **AI review** (`.github/workflows/review.yml`): `REVIEW.md` on every pull request. It reports; a person merges.
- **Live judge check** (`.github/workflows/live-eval.yml`): asks the AI judge again about 145 answer-key pairs, on judge changes and every Monday. It fails below precision 0.97 or recall 0.90. Results on `main` go to the issue "Live judge check history". GitHub turns a weekly schedule off after 60 days with no repo activity; CI warns when the last check is more than 8 days old.

## Is the review load drifting?

`make bands` checks one number: the share of names that need a person's review.

- **What it reads:** counts from your run records (`data/metrics.sqlite`, or `ERM_METRICS_PATH`). Runs with the AI judge on, latest 20 pooled. No company names.
- **What it compares with:** an expected range, also called a control band, in `evals/bands.yaml`. The centre is 33 of 291 names (11%), from one full run on 2 November.
- **Provisional:** one run is not history. Real limits need months of real runs.
- **Outside the range:** it writes a draft intent in `intent/` for a person to correct or dismiss, and exits with code 1. It uses no AI model and makes no outside call.
- **Fewer than 100 names:** it says it can't judge yet.
- **Try it safely:** `uv run python -m eval.bands --simulate` uses made-up runs in a temporary database, and marks everything SIMULATED. Saved example: `outputs/test-evidence/stage6/`.
- **`--open-pr`:** off by default. It would open a draft pull request from a real draft.
- **Limit:** no real LP analyst has been interviewed. The pain is inferred from public signals.
