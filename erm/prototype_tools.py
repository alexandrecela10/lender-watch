"""Prototype tools for Claude, on the local server only (specs/embedded-tools-on-semantic-layer.md, section 3).

Never registered on the hosted service. The prototype loads on the first call, not when the server starts.
"""

from __future__ import annotations

import re

from erm import letters, semantic

LETTERS = semantic.SYN / "letters"


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

    @mcp.tool(
        name="read_letter",
        description=(
            "Propose events from a fund manager's letter: write-downs and covenant breaches, each with the exact "
            "sentence it comes from. Nothing changes a number until the person confirms it with confirm_event: show "
            "each proposal and ask. Pass the letter's text, or a synthetic letter's number such as 07. Off unless "
            "LW_PROTOTYPE_AI=1, because it sends the letter's text to Anthropic."
        ),
    )
    def read_letter(letter: str) -> dict:
        if not letters.ai_enabled():
            return {"error": letters.OFF}
        from erm.api import default_client

        name = letter.strip()
        text = (
            (LETTERS / f"{int(name):02d}.md").read_text()
            if re.fullmatch(r"\d{1,2}", name)
            else letter
        )
        out = letters.read_letter(text, default_client())
        p = semantic.prototype()
        for e in out["kept"]:
            found = p.portfolio.find(e["company"])
            e["company_id"] = found.company_id if found is not None else None
        proposed = p.store.propose(
            name if re.fullmatch(r"\d{1,2}", name) else "pasted", out["kept"]
        )
        return {
            "received": out["received"],
            "proposed": proposed,
            "dropped_quote_not_found": out["dropped"],
        }

    @mcp.tool(
        name="confirm_event",
        description=(
            "Record the person's answer on an event read_letter proposed: yes counts it, no rejects it. Call only "
            "after the person answers. A confirmed write-down changes manager_lender_gap from the date received."
        ),
    )
    def confirm_event(event_id: str, yes: bool) -> dict:
        return semantic.prototype().store.decide(event_id, yes)
