"""The Lender Watch tools, written once for both servers.

The local server (erm/mcp_server.py) and the hosted service (erm/service.py) register the same two tools with the
same descriptions, so Claude sees one product wherever it meets it. The tool-choice eval reads these descriptions too.
The owner of each answer is set by the server, never by the caller.
"""

from __future__ import annotations

from collections.abc import Callable

from erm import assist, telemetry
from erm.api import Engine
from erm.connectors.bdc import PROFILE

SERVER_NAME = "lender-watch"

CHECK_LENDERS = """Check what lenders report about a list of companies: Lender Watch.

Use it when someone asks what lenders say about companies, whether any portfolio companies show stress in their
debt, or asks to check, match or reconcile company names against lender filings. Also use it, after asking, when a
lookup on company names (XLOOKUP, VLOOKUP, INDEX MATCH, a merge) returns #N/A or misses rows, because lenders write
names differently.

`companies`: up to {max_names} items, each {{name, sector?, sponsor?}}. `as_of`: a quarter-end date such as
2026-03-31, or leave it out for the latest quarter.

Returns one row per company: flag, the name lenders use, value as % of the amount owed, change in a quarter, every
loan with its lender, filing link and filing row, and `to_confirm` for names a person must settle. Every row says its
quarter (`as_of`), data version and rule version.

Report only numbers returned here, name the lender and filing beside each, and never decide a `to_confirm` item
yourself. Values are lenders' own estimates, not market prices. Banks don't publish loans, so "Not flagged" covers
only lenders that do."""

CONFIRM_MATCH = """Record a person's answer on an unclear match from check_lenders: is this filing's company the same
as theirs? Call it only after the person has said yes or no. Their answer is saved for them, beats every automated
answer, and they are never asked again. `name` is their company, `mention_key` comes from the `to_confirm` item,
`same` is true or false."""

CHECK_LENDERS_IN_FILE = """Check what lenders report about the companies in a .xlsx or .csv on this computer, and
write a copy beside it ending in _lenders.xlsx: the same sheet with lender columns added, plus one row per loan with
its filing link. The original is not changed. Use when the person points to a file rather than pasting names."""


def register(
    mcp,
    engine: Callable[[], Engine],
    owner: Callable[[], str],
    source: str,
    max_names: int,
    with_file_tool: bool = False,
) -> None:
    """Add the tools to an MCP server. `owner` returns the signed-in person's id for the current call."""

    @mcp.tool(
        name="check_lenders",
        description=CHECK_LENDERS.format(max_names=max_names),
    )
    def check_lenders(companies: list[dict], as_of: str | None = None) -> dict:
        return assist.check_list(
            engine(),
            companies,
            PROFILE,
            as_of=as_of,
            owner=owner(),
            source=source,
            max_names=max_names,
        )

    @mcp.tool(name="confirm_match", description=CONFIRM_MATCH)
    def confirm_match(
        name: str, mention_key: str, same: bool, reason: str = ""
    ) -> dict:
        e = engine()
        with telemetry.run(f"{source}_answer", judge_on=False):
            return e.answer(name, mention_key, same, reason, owner=owner())

    if with_file_tool:

        @mcp.tool(name="check_lenders_in_file", description=CHECK_LENDERS_IN_FILE)
        def check_lenders_in_file(
            path: str,
            name_column: str,
            sector_column: str | None = None,
            sponsor_column: str | None = None,
        ) -> dict:
            from pathlib import Path

            src = Path(path).expanduser()
            if src.suffix.lower() not in (".xlsx", ".xls", ".csv"):
                raise ValueError("Only .xlsx, .xls and .csv files can be read.")
            out = src.with_name(f"{src.stem}_lenders.xlsx")
            e = engine()
            with telemetry.run(source, judge_on=e.client is not None):
                table = e.enrich_table(
                    src, name_column, out, sector_column, sponsor_column
                )
            return {"written_to": str(out), "rows": len(table)}
