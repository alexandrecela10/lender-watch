"""Source connector: SEC BDC data sets (soi.tsv) -> one clean table of holdings with provenance."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from erm.assist_profile import SourceProfile
from erm.textparse import is_funded_debt, lien_of, maturity_of

COLUMNS = {
    "Investment, Identifier Axis": "raw_text",
    "Investment Owned, Balance, Principal Amount": "principal",
    "Adjusted cost basis": "cost",
    # SEC's column label. Checked against the filing: GCRED 30 Jun 2026 KnowBe4 shows 13,851 par and 10,873 fair value.
    "Initial fair value of Investment": "fair_value",
    "Investment, Basis Spread, Variable Rate": "spread",
    "Investment Maturity Date": "maturity_col",
    "Investment, Interest Rate, Paid in Kind": "pik_rate",
}
META = ["adsh", "cik", "name", "ddate", "qtrs", "period", "filed", "form", "inlineurl"]
MIN_PCT_PAR, MAX_PCT_PAR = (
    5.0,
    130.0,
)  # outside this a value/par ratio is a data problem, not a price
# A real markdown has cost near par and fair value below it. Cost far from principal means a partly drawn loan or tags
# that don't belong together, either of which would read as a false markdown.
# Foreign loans have the same signature: filers tag principal in local currency and cost and value in US dollars, so a
# Canadian loan at full value reads about 72% of par (rows such as 123Dentist, New Look Vision). The filing has no currency tag, so the lower
# bound sits above that band. A few real write-downs fall below it too; they show as "left out, see the filing".
MIN_COST_RATIO, MAX_COST_RATIO = 0.80, 1.15


def load_soi(paths: list[str | Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if (
            Path(path).stat().st_size == 0
        ):  # SEC publishes empty tables for months with no filings
            continue
        df = pd.read_csv(path, sep="\t", dtype=str, low_memory=False)
        df = df[META + [c for c in COLUMNS if c in df]].rename(
            columns=COLUMNS | {"name": "lender"}
        )
        # Each filing also repeats the prior year-end schedule. ddate says which date a row's values are for.
        df = df[df.raw_text.notna() & (df.qtrs == "0")]
        frames.append(df.assign(period=df.ddate).drop(columns=["ddate", "qtrs"]))
    h = pd.concat(frames, ignore_index=True)
    for c in ["principal", "cost", "fair_value", "spread", "pik_rate"]:
        h[c] = pd.to_numeric(h[c], errors="coerce")
    return enrich(h.drop_duplicates(ignore_index=True))


def enrich(h: pd.DataFrame) -> pd.DataFrame:
    """Add loan descriptors and a usable-value flag. Rows are never dropped, only marked with a reason."""
    h = h.copy()
    h["lien"] = h.raw_text.map(lien_of)
    h["maturity"] = [maturity_of(r, m) for r, m in zip(h.raw_text, h.maturity_col)]
    h["funded_debt"] = h.raw_text.map(is_funded_debt)
    h["pct_par"] = (h.fair_value / h.principal * 100).where(h.principal > 0)
    reason = pd.Series("", index=h.index)
    reason[~h.funded_debt] = "not funded debt"
    reason[(reason == "") & ~(h.principal > 0)] = "no principal"
    reason[(reason == "") & ~(h.fair_value > 0)] = "no fair value"
    reason[(reason == "") & ~h.pct_par.between(MIN_PCT_PAR, MAX_PCT_PAR)] = (
        "implausible value"
    )
    ratio = h.cost / h.principal
    reason[(reason == "") & h.cost.isna()] = "no cost to check against"
    reason[(reason == "") & ~ratio.between(MIN_COST_RATIO, MAX_COST_RATIO)] = (
        "amounts don't line up"
    )
    h["excluded_reason"] = reason
    h["holding_id"] = h.adsh + ":" + h.groupby("adsh").cumcount().astype(str)
    return h


PROFILE = SourceProfile(
    source_name="the names lenders use in SEC filings",
    finds="What lenders say each company's loans are worth, with the filing behind each number.",
    clear_example='Example: "KnowBe4" and "KnowBe4, Inc.".',
    unclear_example='Example: is "Apex Bidco Limited" your "Apex Group"? The filing doesn\'t settle it.',
    lookup_example=(
        'A lookup needs identical text. Lenders write "KnowBe4, Inc. | Education", so a lookup on "KnowBe4" returns #N/A. '
        'A looser match would be wrong the other way: "Foundation" would pick up Foundation Risk Partners, a different company.'
    ),
    comes_out="You get your sheet back with new columns, plus one row per loan with its filing link.",
    cannot_do=(
        "Banks don't publish their loans, so a company with only bank debt shows nothing.",
        "A flag says what lenders report. It doesn't predict anything, and no investor has tested it yet.",
        "Values are lenders' own estimates, not market prices. This isn't investment advice.",
    ),
)


def load_holdings(path: str | Path = "data/holdings_clean.parquet") -> pd.DataFrame:
    return pd.read_parquet(path)
