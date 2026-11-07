# Intent: LP credit read-through on a list of company names

Author: Alexandre Cela, writing as the LP analyst (private equity funds team). Status: draft, awaiting correction by the author.
Source: `outputs/opportunity-analyses/lp-credit-readthrough-opportunity.md` (Go, scoped, 2026-11-01, corrected 2026-11-02).
Evidence: public filings only. No LP analyst has been interviewed. The pain is inferred.

## Problem

I keep a list of the companies inside our PE funds. Lenders to those companies publish every loan and what they think it's worth, about 42 days after quarter end. Our GP reports arrive 60 to 120 days after. Nobody matches the lenders' numbers to my list, because one company sits in a median of 4 lender funds under 5 different descriptions, and there are about 160 filers.

One case: Vista owns KnowBe4. Nine lender funds valued its loans between 77.5% and 78.5% of par on 30 June 2026, filed 11 August. The GP report arrives 29 August at best and shows equity value, not the lenders' view.

## Proposed outcome

I load my list as a spreadsheet. I get the same spreadsheet back with, per company: whether any lender values its debt below 90% of par (weighted by loan size), the change since last quarter, and one row per loan with a link to the filing row. Unclear names are shown to me once; my answer is saved and reused next quarter.

What should change: companies I check each quarter, from a handful by hand to the whole list. Wrong loans attached to a company: from 6 in 100 (plain name match, observed) to under 3 in 100. What must not get worse: values shown without a filing link, 0.

## Affected users and systems

Users: LP analysts on a private equity funds team; later, secondaries and credit teams with their own lists.
Systems: SEC BDC data sets (monthly), sponsor websites (company lists), the matching engine in `erm/`, the review app in `app/`, the saved decisions store, the optional AI judge (Anthropic API).

## Constraints

- Public data only. No employer, client or counterparty data or names in code, fixtures, docs or demo text.
- Every value keeps its filing URL and row. No uncited value is ever shown.
- The AI judge sends company names to a third party. Off by default. A list under fund confidentiality terms must run with it off, or with a model inside the LP's perimeter.
- A person's answer on a match overrides every automated answer and persists across runs.
- SEC access: declared User-Agent, 5 requests per second at most, every download cached.
- Keys live in `.env`. Never printed, never committed.

## Open questions

- Do LP analysts keep a list of underlying companies, or only GP PDFs? If only PDFs, reading them becomes step one.
- Does a lender flag predict a later GP markdown? Unobserved. Needs 3 LP interviews and one quarter of history.
- Do 9fin or PitchBook already tell an LP which of their companies are stressed? If 3 analysts say yes, this is a No-go.
