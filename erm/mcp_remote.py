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
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from erm import lender_tools, telemetry
from erm.api import Engine
from erm.store import LOCAL

ROOT = Path(__file__).resolve().parents[1]
MAX_NAMES = 50
DEFAULT_HOSTS = ["127.0.0.1:*", "localhost:*"]

mcp = MCPServer(lender_tools.SERVER_NAME)
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


lender_tools.register(
    mcp,
    engine=lambda: engine(),
    owner=lambda: LOCAL,
    source="mcp_remote",
    max_names=MAX_NAMES,
)


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
