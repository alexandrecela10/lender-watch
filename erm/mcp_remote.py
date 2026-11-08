"""The engine as a web connector for Claude in Excel and other Claude apps. Run: make mcp-web

Anyone with the address can call it, so it offers less than the local server in erm/mcp_server.py:
- public sample data only, and no AI judge
- no tool that reads or writes a file, and no tool that changes a saved answer
- answers saved along the way go to a temporary copy

It listens on this computer only unless ERM_MCP_BIND and ERM_MCP_HOSTS are set. Names sent to it reach whoever hosts it.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from erm import assist, telemetry
from erm.api import Engine
from erm.connectors.bdc import PROFILE

ROOT = Path(__file__).resolve().parents[1]
MAX_NAMES = 50
DEFAULT_HOSTS = ["127.0.0.1:*", "localhost:*"]

mcp = MCPServer("lender-watch")
_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        folder = Path(tempfile.mkdtemp())
        shutil.copy(ROOT / "data/public/decisions.sqlite", folder / "decisions.sqlite")
        _engine = Engine(
            holdings_path=str(ROOT / "data/public/holdings.parquet"),
            store_path=str(folder / "decisions.sqlite"),
            index_cache=str(Path(tempfile.gettempdir()) / "erm_index.pkl"),
            client=None,
        )
    return _engine


@mcp.tool()
def inspect_sheets(sheets: dict[str, list[list]], failed_lookups: int = 0) -> dict:
    """Check whether the company names in a workbook's tabs line up. Call this without being asked when a person
    compares or joins lists of companies, or when XLOOKUP, VLOOKUP or a merge on company names returns #N/A or misses
    rows. Pass `sheets` as {tab: rows, header first}. Set `failed_lookups` to how many lookups failed. If
    `should_offer` is true, tell the person `message` and `facts`, and ask before running reconcile_list."""
    return assist.inspect_sheets(sheets, failed_lookups)


@mcp.tool()
def how_to_reconcile(n_names: int | None = None, has_context: bool = False) -> dict:
    """Plain answer to 'how do I reconcile or match these companies?': steps, why a lookup fails, and what the tool
    can't do. Use it when a person asks how, before running anything. `has_context` means owner or sector columns."""
    return assist.how_to_reconcile(PROFILE, n_names, has_context)


@mcp.tool()
def reconcile_list(companies: list[dict]) -> dict:
    """Link companies to the names lenders use in SEC filings. Each item is {name, sector?, sponsor?}. Up to 50.
    Returns one row per company: flag, the name lenders use, value as % of the amount owed, change in a quarter, every
    loan with its filing link and row, and `to_confirm` for names a person must settle. Report only numbers returned
    here, name the lender and filing, and never decide a `to_confirm` item yourself. Public sample of SEC filings."""
    if len(companies) > MAX_NAMES:
        raise ValueError(f"Send {MAX_NAMES} names or fewer at a time.")
    return assist.reconcile_list(engine(), companies, source="mcp_remote")


@mcp.tool()
def resolve_entity(
    name: str, sector: str | None = None, sponsor: str | None = None
) -> dict:
    """Find one company in public lender filings. Returns the name lenders use and why each candidate was accepted or
    rejected."""
    e = engine()
    with telemetry.run("mcp_remote", judge_on=False):
        res = e.resolve_entity(name, {"sector": sector, "sponsor": sponsor})
        telemetry.count(res.status)
    return asdict(res)


def main() -> None:
    telemetry.configure()
    engine()  # build the search index before accepting calls
    hosts = [
        h for h in os.environ.get("ERM_MCP_HOSTS", "").split(",") if h
    ] or DEFAULT_HOSTS
    mcp.run(
        "streamable-http",
        host=os.environ.get("ERM_MCP_BIND", "127.0.0.1"),
        port=int(os.environ.get("ERM_MCP_PORT", "8770")),
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(allowed_hosts=hosts),
    )


if __name__ == "__main__":
    main()
