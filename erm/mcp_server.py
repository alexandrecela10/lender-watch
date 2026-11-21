"""Lender Watch as a tool AI agents can call on this computer (MCP over stdin). Run: uv run python -m erm.mcp_server

Same two tools as the hosted service, plus one that reads a local file. Answers are saved under "local".
Set ERM_USE_JUDGE=1 to send unclear names, with sector and owner, to Anthropic. Off by default.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

from erm import lender_tools, telemetry
from erm.api import Engine, default_client
from erm.assist import MAX_NAMES
from erm.store import LOCAL

mcp = MCPServer(lender_tools.SERVER_NAME)
_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine(
            client=default_client() if os.environ.get("ERM_USE_JUDGE") == "1" else None
        )
    return _engine


lender_tools.register(
    mcp,
    engine=lambda: engine(),
    owner=lambda: LOCAL,
    source="mcp",
    max_names=MAX_NAMES,
    with_file_tool=True,
)


if __name__ == "__main__":
    telemetry.configure()  # stderr only: stdout carries the MCP protocol
    mcp.run()
