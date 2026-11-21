"""Prototype tools for Claude, on the local server only (specs/embedded-tools-on-semantic-layer.md, section 3).

Never registered on the hosted service. The prototype loads on the first call, not when the server starts.
"""

from __future__ import annotations

from erm import semantic


def measure_description() -> str:
    """Lists the measures from the definitions file, so a new measure appears without editing this tool."""
    lines = [
        "Get an agreed measure for a list of companies in the synthetic portfolio, on this computer only.",
        "Each measure is defined once, with an owner and a version; code computes it. Report only values returned",
        "here, say which are synthetic, and give the not_available reason when there's no value.",
        "`as_of`: a quarter-end such as 2026-03-31, or leave it out for the latest. Measures:",
    ]
    lines += [
        f"- {m['id']}: {m['name']}. {m['definition']}"
        for m in semantic.load_measures().values()
    ]
    return "\n".join(lines)


def register(mcp) -> None:
    @mcp.tool(name="get_measure", description=measure_description())
    def get_measure(
        measure: str, companies: list[str], as_of: str | None = None
    ) -> dict:
        return semantic.prototype().get_measure(measure, companies, as_of=as_of)
