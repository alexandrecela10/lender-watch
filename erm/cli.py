"""Spreadsheet in, same spreadsheet out with lender columns and filing links added.

Usage: uv run python -m erm.cli enrich list.xlsx --name-column Company --out list_enriched.xlsx
"""

from __future__ import annotations

import argparse

from erm.api import Engine, default_client


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enrich", help="Add lender data to a spreadsheet of company names")
    e.add_argument("file")
    e.add_argument("--name-column", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--sector-column")
    e.add_argument("--sponsor-column")
    e.add_argument("--use-judge", action="store_true", help="Send unclear names, with sector and owner, to Anthropic to judge. Off by default: nothing leaves this machine")
    a = ap.parse_args()
    client = default_client() if a.use_judge else None
    if a.use_judge and client is None:
        ap.error("--use-judge needs ANTHROPIC_API_KEY in .env")
    engine = Engine(client=client)
    t = engine.enrich_table(a.file, a.name_column, a.out, a.sector_column, a.sponsor_column)
    counts = t["Lender data"].value_counts().to_dict()
    flags = t["Flag"].value_counts().to_dict()
    print(f"{len(t)} names: {counts}. Flags: {flags}. Saved to {a.out}.")
    pending = engine.store.pending({str(n) for n in t[a.name_column]})
    if pending:
        print(f"{len(pending)} matches need your review. Open the app: uv run streamlit run app/review.py")


if __name__ == "__main__":
    main()
