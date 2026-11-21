"""Change explainer (prototype): why a measure moved between the two quarters held. Spec section 5.

Code computes every part and checks the unrounded parts sum to the total. The sentence is a template, or, with
LW_PROTOTYPE_AI=1, words from the model around placeholders that code fills. The model never sees or writes a number,
and a sentence with a number or direction word outside a placeholder is thrown away for the template.
"""

from __future__ import annotations

import logging
import re

from erm.semantic import Prototype

FROM, TO = "2026-03-31", "2026-06-30"
EXPLAINABLE = ("cost_in_flagged", "share_cost_flagged", "manager_lender_gap")
DIRECTIONS = (
    "rose|fell|rise|fall|rises|falls|risen|fallen|increase|increased|increases|decrease|decreased|decreases|"
    "up|down|higher|lower|grew|grow|dropped|drop|declined|decline|gained|gain|lost|lose|climbed|slipped|jumped"
)
PLACEHOLDER = re.compile(r"\{(total|part_\d+)\.(amount|direction|label)\}")

log = logging.getLogger("erm.explain")

SYSTEM = """You write one or two plain sentences explaining why a portfolio measure changed between two quarters.

The parts are listed largest first. You never see numbers and must never write one. Refer to amounts and directions only through placeholders, which
code fills in:
- {total.amount} and {total.direction} for the whole change
- {part_N.amount}, {part_N.direction} and {part_N.label} for part N

A direction placeholder is itself the verb, such as "rose", "fell" or "narrowed the gap": write "{total.direction} by
{total.amount}", never "changed {total.direction}".

Write no digits and no words like rose, fell, up, down, higher or lower outside a placeholder. Mention only the
largest parts. Plain words, no jargon."""


def fmt(value: float, unit: str) -> str:
    if unit == "usd":
        return f"${abs(value):,.0f}"
    if unit == "share":
        return f"{abs(value) * 100:.2f}% of our cost"
    return f"{abs(value):.1f} points"


def shown(value: float, unit: str) -> float:
    """The value as displayed, so a rounding difference can be shown as its own part."""
    if unit == "usd":
        return round(value)
    if unit == "share":
        return round(value, 4)
    return round(value, 1)


def direction(value: float) -> str:
    return "rose" if value > 0 else "fell" if value < 0 else "didn't move"


def _parts(p: Prototype, measure: str, c, owner: str) -> list[tuple[str, float]]:
    """(label, amount) for one company. Amounts are unrounded and sum exactly to that company's change."""
    if measure == "manager_lender_gap":
        before_j = p.portfolio.managers.query(
            "company_id == @c.company_id and quarter == @TO"
        ).value_pct_cost.iloc[0]
        after_j = p.manager_value(c, TO)[0]
        after_m = p.manager_value(c, FROM)[0]
        lend_j = p.lender(c, TO, owner)["flags"]["weighted_pct_par"]
        lend_m = p.lender(c, FROM, owner)["flags"]["weighted_pct_par"]
        return [
            (f"{c.name}: manager's value moved", float(before_j) - after_m),
            (f"{c.name}: write-down we confirmed", after_j - float(before_j)),
            # Labelled by what lenders did. Its amount is the effect on the gap, the opposite sign.
            (
                f"{c.name}: lenders {'raised' if lend_j > lend_m else 'cut'} their value of the debt",
                -(lend_j - lend_m),
            ),
        ]
    compute = getattr(p, measure)
    now, _, _ = compute(c, TO, owner)
    then, _, _ = compute(c, FROM, owner)
    flagged_now = p.lender(c, TO, owner)["flags"]["level"] == "flagged"
    flagged_then = p.lender(c, FROM, owner)["flags"]["level"] == "flagged"
    if flagged_now and not flagged_then:
        return [(f"{c.name}: newly flagged", now)]
    if flagged_then and not flagged_now:
        return [(f"{c.name}: no longer flagged", -then)]
    if flagged_now and flagged_then:
        return [(f"{c.name}: cost moved while flagged", now - then)]
    return []


def explain(
    p: Prototype, measure: str, companies: list[str], client=None, owner: str = "local"
) -> dict:
    if measure not in EXPLAINABLE:
        raise ValueError(
            f"{measure} has no explainer. Measures that do: {', '.join(EXPLAINABLE)}."
        )
    if measure == "manager_lender_gap" and len(companies) != 1:
        raise ValueError(
            "Explain manager_lender_gap for one company at a time: gaps in points don't add up across companies."
        )
    m = p.measures[measure]
    unit = m["unit"]
    rows_then = {
        r["company"]: r for r in p.get_measure(measure, companies, FROM, owner)["rows"]
    }
    rows_now = p.get_measure(measure, companies, TO, owner)["rows"]
    parts, skipped, total = [], [], 0.0
    for r in rows_now:
        then = rows_then.get(r["company"])
        if r["value"] is None or then is None or then["value"] is None:
            skipped.append(
                {
                    "company": r["company"],
                    "reason": r["not_available"] or (then or {}).get("not_available"),
                }
            )
            continue
        c = p.portfolio.find(r["company_id"])
        mine = _parts(p, measure, c, owner)
        # The parts come from the same functions as the measure, so they match its shown change to its rounding.
        change = sum(a for _, a in mine)
        assert abs(change - (r["value"] - then["value"])) < 1e-5, (
            measure,
            c.company_id,
        )
        total += change
        parts += [{"label": label, "amount": a} for label, a in mine if a != 0]
    shown_parts = [shown(x["amount"], unit) for x in parts]
    gap = shown(total, unit) - sum(shown_parts)
    if abs(gap) > 1e-9:
        parts.append({"label": "rounding", "amount": gap})
    for i, x in enumerate(parts, 1):
        x["id"] = f"part_{i}"
        x["shown"] = fmt(x["amount"], unit)
        x["direction"] = direction(x["amount"])
        if "lenders raised" in x["label"] or "lenders cut" in x["label"]:
            x["direction"] = (
                "narrowed the gap" if x["amount"] < 0 else "widened the gap"
            )
    out = {
        "measure": measure,
        "from": FROM,
        "to": TO,
        "total": total,
        "total_shown": fmt(total, unit),
        "direction": direction(total),
        "parts": parts,
        "not_explained": skipped,
        "sum_check": abs(
            sum(x["amount"] for x in parts if x["label"] != "rounding") - total
        )
        < 1e-6,
    }
    out["sentence"], out["sentence_from"] = sentence(m["name"], out, client)
    log.info("explain", extra={"names_in": len(companies), "names_matched": len(parts)})
    return out


def template(name: str, out: dict) -> str:
    biggest = sorted(out["parts"], key=lambda x: -abs(x["amount"]))[:3]
    lead = f"{name} {out['direction']} by {out['total_shown']} between 31 March and 30 June 2026."
    if not biggest:
        return lead
    return (
        lead
        + " Largest parts: "
        + "; ".join(f"{x['label']}, {x['shown']}" for x in biggest)
        + "."
    )


def check_words(text: str, out: dict) -> bool:
    """True when every number and direction in the model's words sits inside a placeholder that names a real part."""
    ids = {"total"} | {x["id"] for x in out["parts"]}
    for m in PLACEHOLDER.finditer(text):
        if m.group(1) not in ids:
            return False
    if "{" in PLACEHOLDER.sub("", text) or "}" in PLACEHOLDER.sub("", text):
        return False
    bare = PLACEHOLDER.sub(" ", text)
    if re.search(r"\d", bare):
        return False
    return not re.search(rf"\b({DIRECTIONS})\b", bare, flags=re.IGNORECASE)


def fill(text: str, out: dict) -> str:
    by_id = {x["id"]: x for x in out["parts"]}
    by_id["total"] = {
        "shown": out["total_shown"],
        "direction": out["direction"],
        "label": "the total",
    }

    def put(m):
        x = by_id[m.group(1)]
        return {"amount": x["shown"], "direction": x["direction"], "label": x["label"]}[
            m.group(2)
        ]

    return PLACEHOLDER.sub(put, text)


def sentence(name: str, out: dict, client) -> tuple[str, str]:
    """('...', 'model') when the model's words pass the check, else the template."""
    if client is None or not out["parts"]:
        return template(name, out), "template"
    # The three largest parts only, largest first, so "mainly" can only point at the largest.
    largest = sorted(
        (x for x in out["parts"] if x["label"] != "rounding"),
        key=lambda x: -abs(x["amount"]),
    )[:3]
    listing = "\n".join(f"{x['id']}: {x['label']}" for x in largest)
    response = client.beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Measure: {name}\nParts:\n{listing}"}],
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    words = "".join(
        b.text for b in response.content if getattr(b, "type", "") == "text"
    ).strip()
    if response.stop_reason == "refusal" or not check_words(words, out):
        log.info("explain_rejected", extra={"model": response.model})
        return template(name, out), "template"
    return fill(words, out), "model"
