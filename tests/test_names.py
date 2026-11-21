"""One product name, and a skill that names only real tools (spec checks 12 and 13)."""

import re
from pathlib import Path

from erm import lender_tools, mcp_server

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/lender-watch/SKILL.md"
OLD_NAMES = re.compile(
    r"Entity Reconciliation|Analyst Desk|ERM\.|RECONCILE|reconcile-companies|reconcile_list|entity-reconciliation"
)
ADDIN = ROOT / "app/desk/excel"
# Everything an analyst or Claude reads about the product.
ANALYST_FACING = [
    SKILL,
    ADDIN / "manifest.xml",
    ADDIN / "manifest.template.xml",
    ADDIN / "functions.json",
    ADDIN / "functions.js",
    ADDIN / "taskpane.html",
    ADDIN / "taskpane.js",
    ADDIN / "api.js",
    ADDIN / "auth.js",
    ADDIN / "signin.html",
    ADDIN / "signin-callback.html",
]


def tool_names() -> set[str]:
    return {t.name for t in mcp_server.mcp._tool_manager.list_tools()}


def test_skill_names_only_tools_that_exist():
    named = set(re.findall(r"`([a-z_]+)`", SKILL.read_text()))
    tools_named = {n for n in named if n.startswith(("check_", "confirm_"))}
    assert tools_named == tool_names()


def test_no_old_names_where_analysts_or_claude_read():
    texts = [p.read_text() for p in ANALYST_FACING]
    texts += [
        lender_tools.CHECK_LENDERS,
        lender_tools.CONFIRM_MATCH,
        lender_tools.CHECK_LENDERS_IN_FILE,
    ]
    found = [m.group(0) for t in texts for m in OLD_NAMES.finditer(t)]
    assert found == []
