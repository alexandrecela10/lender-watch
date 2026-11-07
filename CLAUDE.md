# Entity Reconciliation Machine

**Product:** an entity reconciliation engine for private capital. It links the same company across sources that name it differently, and returns facts with a link to the source row. First use: LP analysts see lender-side stress (BDC loan marks) on the companies inside their PE funds.

**Brief and decisions:** `outputs/opportunity-analyses/`, then `outputs/prds/`. Earlier drafts: `docs/archive/PRD_1.md`, `docs/archive/CLAUDE_1.md` (context only, not binding).

**Hard constraints**
- Public data only (SEC EDGAR, SEC BDC data sets, sponsor websites). No employer, client or counterparty data or names.
- Every fact keeps its source (filing URL + row). No uncited value is ever shown.
- Pain is inferred from public signals until real LP users are interviewed. Say so in every document.
- Core engine stays source-agnostic so other side projects and customers can plug in their own lists and sources.
- SEC access: declared User-Agent, max 5 requests/second, cache every download under `data/raw/` (git-ignored).
- Keys live in `.env`. Never print or commit them.

**Stack:** Python 3.12 via `uv`. Engine in `erm/`, app in `app/`, measurement in `eval/`, data in `data/`. See `README.md`.

**Data rules learned the hard way**
- In SEC's `soi.tsv`, use `ddate` as the period. About half the rows are prior-period comparison schedules.
- Check any column or claim against a real filing before relying on it.
- All labels so far are Claude's. Never describe them as human or hand-labelled.
- Principal can be in local currency while cost and value are in US dollars. There is no currency tag.
- Flags use the size-weighted average. A single small position never flags a company.
