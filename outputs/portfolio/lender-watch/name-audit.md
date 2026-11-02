# Name audit: Lender Watch

**Status:** nothing changed, because no replacement is proposed. One item needs Alexandre's approval before publishing.

Searched: code, docs, README, `PRD_1.md`, `CLAUDE_1.md`, `KICKOFF_PROMPTS.md`, filenames, demo data and tests. No employer, client, prospect or interviewee name was found. Data files were checked by filename only. Alexandre should add any name this search can't know.

| Where | Current | Proposed | Why |
|---|---|---|---|
| Page and documents | KnowBe4, with lender values | **Keep only if Alexandre confirms the value in the filing** | Public filing, allowed by the names policy. The legal reviewer asks that a person confirm any named value first |
| `outputs/`, `data/eval/full_results.csv` | Other flagged companies, such as Techmer | Keep in private files; not on the page | The page names only examples needed to explain a point |
| Page, learnings | Bullhorn, 123Dentist, Brightview Landscapes, Ascend Learning | Keep; each is a public filing row or data example, none called stressed | Explains a data problem. Alexandre to confirm |
| `eval/verify_flags.py` | `@example.org` placeholder contact | Replace through `SEC_USER_AGENT` | SEC asks for a real contact |

**Kept and why:** SEC, BDC lenders, PE sponsors and their website portfolio lists, PitchBook, 9fin. All are public sources under the names policy (`context-library/README.md`).

**Repo hygiene:** `.env`, `data/raw/`, processed data and the decisions database are git-ignored. Nothing is committed. `CLAUDE_1.md`, `PRD_1.md` and `KICKOFF_PROMPTS.md` are early drafts: decide whether they ship.
