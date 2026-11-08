"""The engine as a tool AI agents can call (MCP). Run: uv run python -m erm.mcp_server

Set ERM_USE_JUDGE=1 to send unclear names, with sector and owner, to Anthropic. Off by default.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from erm import assist, telemetry
from erm.api import Engine, default_client
from erm.connectors.bdc import PROFILE

mcp = MCPServer("entity-reconciliation")
_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine(
            client=default_client() if os.environ.get("ERM_USE_JUDGE") == "1" else None
        )
    return _engine


@mcp.tool()
def resolve_entity(
    name: str, sector: str | None = None, sponsor: str | None = None
) -> dict:
    """Find a company in public BDC lender filings. Returns status (matched, needs_review, not_found), the borrower
    name lenders use, and every candidate with the reason it was accepted or rejected."""
    e = engine()
    with telemetry.run("mcp", judge_on=e.client is not None):
        res = e.resolve_entity(name, {"sector": sector, "sponsor": sponsor})
        telemetry.count(res.status)
    return asdict(res)


@mcp.tool()
def gather_facts(
    name: str, sector: str | None = None, sponsor: str | None = None
) -> dict:
    """Latest-quarter loan values for a company, from each lender, with last quarter's value when the same loan can be
    paired. Every fact has a filing link and the filing's row text. Values are the lender's estimate, not a market price."""
    e = engine()
    with telemetry.run("mcp", judge_on=e.client is not None):
        out = e.gather_facts(name, {"sector": sector, "sponsor": sponsor})
        telemetry.count_result(out)
    return out


@mcp.tool()
def inspect_sheets(
    sheets: dict[str, list[list]] | None = None,
    path: str | None = None,
    failed_lookups: int = 0,
) -> dict:
    """Check whether the company names in a workbook's tabs line up. Call this without being asked when a person
    compares or joins lists of companies, or when XLOOKUP, VLOOKUP or a merge on company names returns #N/A or misses
    rows. Pass `sheets` as {tab: rows, header first}, or `path` to a local .xlsx or .csv. Set `failed_lookups` to how
    many lookups failed. If `should_offer` is true, tell the person `message` and `facts`, and ask before running
    reconcile_list. No company names leave this computer."""
    if (sheets is None) == (path is None):
        raise ValueError("Pass exactly one of sheets or path.")
    return assist.inspect_sheets(
        sheets if sheets is not None else assist.read_workbook(path), failed_lookups
    )


@mcp.tool()
def how_to_reconcile(
    n_names: int | None = None, has_context: bool = False, confidential: bool = False
) -> dict:
    """Plain answer to 'how do I reconcile or match these companies?': steps, why a lookup fails, privacy, and what
    the tool can't do. Use it when a person asks how, before running anything. `has_context` means the list has owner
    or sector columns. `confidential` means the list falls under fund confidentiality terms."""
    return assist.how_to_reconcile(PROFILE, n_names, has_context, confidential)


@mcp.tool()
def reconcile_list(companies: list[dict]) -> dict:
    """Link a list of companies to the names lenders use in SEC filings. Each item is {name, sector?, sponsor?}.
    Returns one row per company: result, flag, the name lenders use, value as % of the amount owed, change in a
    quarter, every loan with its filing link and row, and `to_confirm` for names a person must settle. Report only
    numbers returned here, and say which lender and filing they come from. Up to 200 names."""
    return assist.reconcile_list(engine(), companies, source="mcp")


@mcp.tool()
def enrich_spreadsheet(
    path: str,
    name_column: str,
    sector_column: str | None = None,
    sponsor_column: str | None = None,
) -> dict:
    """Write a copy of a local .xlsx or .csv with lender columns added, plus one row per loan with its filing link.
    The copy sits beside the original, ending in _reconciled. The original is not changed."""
    source = Path(path).expanduser()
    if source.suffix.lower() not in (".xlsx", ".xls", ".csv"):
        raise ValueError("Only .xlsx, .xls and .csv files can be read.")
    out = source.with_name(f"{source.stem}_reconciled.xlsx")
    e = engine()
    with telemetry.run("mcp", judge_on=e.client is not None):
        table = e.enrich_table(source, name_column, out, sector_column, sponsor_column)
    return {"written_to": str(out), "rows": len(table)}


@mcp.tool()
def review(pair_id: str, accept: bool, reason: str = "") -> dict:
    """Record a person's decision on an unclear match. It overrides automation and is never asked again.
    Call this only when a person has told you the answer."""
    e = engine()
    with telemetry.run("mcp", judge_on=e.client is not None):
        return e.review(pair_id, accept, reason)


if __name__ == "__main__":
    telemetry.configure()  # stderr only: stdout carries the MCP protocol
    mcp.run()
