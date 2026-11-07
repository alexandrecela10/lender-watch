"""The engine as a tool AI agents can call (MCP). Run: uv run python -m erm.mcp_server

Set ERM_USE_JUDGE=1 to send unclear names, with sector and owner, to Anthropic. Off by default.
"""

from __future__ import annotations

import os
from dataclasses import asdict

from mcp.server.mcpserver import MCPServer

from erm.api import Engine, default_client

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
    return asdict(engine().resolve_entity(name, {"sector": sector, "sponsor": sponsor}))


@mcp.tool()
def gather_facts(
    name: str, sector: str | None = None, sponsor: str | None = None
) -> dict:
    """Latest-quarter loan values for a company, from each lender, with last quarter's value when the same loan can be
    paired. Every fact has a filing link and the filing's row text. Values are the lender's estimate, not a market price."""
    return engine().gather_facts(name, {"sector": sector, "sponsor": sponsor})


@mcp.tool()
def review(pair_id: str, accept: bool, reason: str = "") -> dict:
    """Record a person's decision on an unclear match. It overrides automation and is never asked again.
    Call this only when a person has told you the answer."""
    return engine().review(pair_id, accept, reason)


if __name__ == "__main__":
    mcp.run()
