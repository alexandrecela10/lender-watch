"""The layer between where people work (Claude, Excel) and the engine.

Three ways in, one engine underneath:
1. The person knows the tool and calls it: reconcile_list.
2. The person knows the problem and asks: how_to_reconcile.
3. The person knows neither: inspect_sheets notices that two lists name companies differently and offers the tool.

Nothing here calls an outside service. Numbers come from the engine; the wording around them is fixed text.
Source-specific wording lives in a SourceProfile, supplied by the connector.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from erm import telemetry
from erm.api import FLAG_LABELS, FLAG_RULE, Engine, summary_row
from erm.assist_profile import SourceProfile
from erm.textparse import core, name_pattern, norm

MAX_NAMES = 200
MAX_COMPARED = (
    5000  # values read from the longer list; enough to judge whether two lists line up
)
MIN_NUMERIC_FREE = 0.7
OFFER_BELOW = 0.9  # offer only when a lookup would find fewer than 90% of the names

NAME_WORDS = {
    "company",
    "companies",
    "borrower",
    "issuer",
    "entity",
    "name",
    "holding",
    "investment",
    "portfolio",
    "counterparty",
    "obligor",
    "target",
}
OWNER_WORDS = {"owner", "sponsor", "gp", "manager"}
SECTOR_WORDS = {"sector", "industry"}
HOW_LINKED = {
    "person": "Confirmed by a person",
    "judge": "AI check, saved",
    "name": "Same name, and the name is uncommon",
}


# --- Reading a workbook ----------------------------------------------------------------------------


def read_workbook(source, filename: str | None = None) -> dict[str, list[list]]:
    """A .xlsx or .csv as {sheet: rows}, first row included. `source` is a path or bytes; bytes need `filename`."""
    label = str(filename if filename is not None else source)
    if not label.lower().endswith((".xlsx", ".xls", ".csv")):
        raise ValueError("Only .xlsx, .xls and .csv files can be opened.")
    data = io.BytesIO(source) if isinstance(source, bytes) else source
    if label.lower().endswith(".csv"):
        frames = {Path(label).stem: pd.read_csv(data, header=None, dtype=object)}
    else:
        frames = pd.read_excel(data, sheet_name=None, header=None, dtype=object)
    return {
        sheet: [
            [None if pd.isna(v) else v for v in row]
            for row in frame.itertuples(index=False, name=None)
        ]
        for sheet, frame in frames.items()
    }


def _header_words(header: object) -> set[str]:
    return set(norm(header).split()) if header is not None else set()


def _column(rows: list[list], index: int) -> list[str]:
    values = (row[index] for row in rows[1:] if index < len(row))
    return [str(v).strip() for v in values if v is not None and str(v).strip()]


def _looks_like_names(values: list[str]) -> bool:
    if not values:
        return False
    numeric_free = sum(
        not v.replace(",", "").replace(".", "").isdigit() for v in values
    )
    return numeric_free / len(values) >= MIN_NUMERIC_FREE


def name_columns(rows: list[list]) -> list[tuple[int, str]]:
    """Columns that hold company names, judged from the header and then the values."""
    if not rows:
        return []
    found = []
    for i, header in enumerate(rows[0]):
        words = _header_words(header)
        is_name_header = words & NAME_WORDS and not words & OWNER_WORDS
        if is_name_header and _looks_like_names(_column(rows, i)):
            found.append((i, str(header)))
    return found


def list_from_sheet(rows: list[list]) -> list[dict]:
    """One {name, sector, sponsor} per row of the sheet's first name column."""
    columns = name_columns(rows)
    if not columns:
        return []
    name_at = columns[0][0]
    header = [_header_words(h) for h in rows[0]]
    owner_at = next((i for i, w in enumerate(header) if w & OWNER_WORDS), None)
    sector_at = next((i for i, w in enumerate(header) if w & SECTOR_WORDS), None)

    def cell(row, i):
        return row[i] if i is not None and i < len(row) and row[i] is not None else None

    return [
        {
            "name": str(row[name_at]).strip(),
            "sponsor": cell(row, owner_at),
            "sector": cell(row, sector_at),
        }
        for row in rows[1:]
        if name_at < len(row) and row[name_at] is not None and str(row[name_at]).strip()
    ]


# --- Way in 3: notice the need -----------------------------------------------------------------------


def _compare(names: list[str], others: list[str]) -> dict:
    exact_set = {v.casefold() for v in others}
    missed, possible, examples = [], [], []
    for name in names:
        if name.casefold() in exact_set:
            continue
        missed.append(name)
        pattern = name_pattern(core(name))
        hit = next((v for v in others if pattern.search(v)), None)
        if hit is not None:
            possible.append(name)
            examples.append({"name": name, "written_as": hit})
    return {
        "exact": len(names) - len(missed),
        "possible": len(possible),
        "no_obvious_match": len(missed) - len(possible),
        "examples": examples[:3],
    }


def _no_offer(why: str) -> dict:
    return {"should_offer": False, "why": why, "message": why}


def inspect_sheets(sheets: dict[str, list[list]], failed_lookups: int = 0) -> dict:
    """Decide whether two lists in a workbook name companies differently, and say so in plain words.

    Compares the shortest company list with every longer list on another sheet. `failed_lookups` is how many
    lookups in the workbook just returned nothing; it makes the offer stronger, never a match.
    """
    lists = [
        (sheet, column, _column(rows, i))
        for sheet, rows in sheets.items()
        for i, column in name_columns(rows)
    ]
    lists = [item for item in lists if item[2]]
    if len({sheet for sheet, _, _ in lists}) < 2:
        return _no_offer("Only one list of company names here, so nothing to compare.")

    lists.sort(key=lambda item: len(item[2]))
    left_sheet, left_column, names = lists[0]
    names = list(dict.fromkeys(names))[:MAX_NAMES]
    best = None
    for right_sheet, right_column, others in lists[1:]:
        if right_sheet == left_sheet:
            continue
        result = _compare(names, others[:MAX_COMPARED])
        if best is None or result["possible"] > best[2]["possible"]:
            best = (right_sheet, right_column, result)
    if best is None:
        return _no_offer("Only one list of company names here, so nothing to compare.")

    right_sheet, right_column, result = best
    total = len(names)
    lookup_share = result["exact"] / total
    should_offer = lookup_share < OFFER_BELOW and (
        result["possible"] > 0 or failed_lookups > 0
    )
    summary = {
        "list": {"sheet": left_sheet, "column": left_column, "names": total},
        "compared_with": {"sheet": right_sheet, "column": right_column},
        "failed_lookups": failed_lookups,
        **result,
    }
    if not should_offer:
        return {
            "should_offer": False,
            "why": "The names line up, or nothing in the other list looks related.",
            "message": f"A lookup finds {result['exact']} of {total} names in {right_sheet}. No linking needed.",
            **summary,
        }

    facts = [
        f"A lookup finds {result['exact']} of {total} names in {right_sheet}, because it needs identical text."
    ]
    if result["possible"]:
        facts.append(f"{result['possible']} appear there inside a longer description.")
    if result["no_obvious_match"]:
        facts.append(
            f"{result['no_obvious_match']} {'shows' if result['no_obvious_match'] == 1 else 'show'} no similar name, so {'it' if result['no_obvious_match'] == 1 else 'they'} may borrow under another name."
        )
    if result["examples"]:
        example = result["examples"][0]
        facts.append(
            f'Example: "{example["name"]}" is written "{example["written_as"][:60]}".'
        )
    return {
        "should_offer": True,
        "why": "The two lists name the same companies differently.",
        "message": "These tabs name companies differently. Want me to link them?",
        "facts": facts,
        **summary,
    }


# --- Way in 2: answer how -----------------------------------------------------------------------------


def how_to_reconcile(
    profile: SourceProfile,
    n_names: int | None = None,
    has_context: bool = False,
    confidential: bool = False,
) -> dict:
    """The same plain answer from every front door: what goes in, what comes out, what it can't do."""
    size = f"your {n_names} names" if n_names else "your list of company names"
    steps = [
        f"Pick the column that holds {size}.",
        f"Clear names link automatically. {profile.clear_example}",
        f"Unclear names come to you, and nothing counts until you answer. {profile.unclear_example}",
        profile.comes_out,
    ]
    if not has_context:
        steps.insert(
            1,
            "Add owner and sector columns if you have them. They settle unclear names.",
        )
    privacy = (
        "Keep the AI check off for this list. Names then stay on your computer, and more of them come to you."
        if confidential
        else "The AI check is off by default. Names stay on your computer unless you turn it on."
    )
    return {
        "answer": f"Link {size} to {profile.source_name}, then add what they show. It takes one step.",
        "why_not_a_lookup": profile.lookup_example,
        "finds": profile.finds,
        "steps": steps,
        "privacy": privacy,
        "cannot_do": list(profile.cannot_do),
        "next_tool": "reconcile_list",
    }


# --- Way in 1: run it -----------------------------------------------------------------------------------


def _slim_loan(fact: dict) -> dict | None:
    """A loan with its source, or nothing: a value without both a link and a row is never returned."""
    if not fact.get("filing_url") or not fact.get("filing_row"):
        return None
    return {
        "lender": fact["lender"],
        "type": fact["lien"],
        "due": fact["maturity"],
        "amount_owed": fact["principal"],
        "value_pct": round(fact["pct_par"], 1),
        "last_quarter_pct": None
        if fact["previous_pct_par"] is None
        else round(fact["previous_pct_par"], 1),
        "change": None if fact["change"] is None else round(fact["change"], 1),
        "filed": fact["filed"],
        "filing_url": fact["filing_url"],
        "filing_row": fact["filing_row"],
    }


def company_row(name: str, out: dict) -> dict:
    """One company in the shape every front door shows. Every number sits next to its loans and their filings."""
    summary = summary_row(out)
    res, flags = out["resolution"], out["flags"]
    loans = [loan for fact in out["facts"] if (loan := _slim_loan(fact))]
    has_numbers = bool(loans)
    return {
        "name": name,
        "result": summary["Lender data"],
        "flag": FLAG_LABELS[flags["level"]] if has_numbers else "",
        "what_it_shows": flags["summary"] if has_numbers else "",
        "listed_as": res["canonical_name"],
        "lenders": flags["n_lenders"] if has_numbers else None,
        "value_pct": flags["weighted_pct_par"] if has_numbers else None,
        "change": flags["weighted_change"] if has_numbers else None,
        "lowest_pct": flags["lowest_pct_par"] if has_numbers else None,
        "linked_because": [
            {
                "listed_as": c["borrower"],
                "how": HOW_LINKED.get(c["decided_by"], c["decided_by"]),
                "reason": c["reason"],
            }
            for c in res["candidates"]
            if c["verdict"] == "match"
        ],
        "to_confirm": [
            {
                "mention_key": c["mention_key"],
                "listed_as": c["borrower"],
                "filing_row": c["example"],
                "filing_url": c["filing_url"],
                "reason": c["reason"],
            }
            for c in res["candidates"]
            if c["verdict"] == "unsure"
        ],
        "filing_url": summary["Filing behind lowest value"] or None,
        "loans": loans,
    }


def reconcile_list(engine: Engine, rows: list[dict], source: str = "assist") -> dict:
    """Link each {name, sector, sponsor} to the source and return one row per company.

    Runs under one request id. No outside call happens unless the engine was built with a judge client.
    """
    if len(rows) > MAX_NAMES:
        raise ValueError(f"Send {MAX_NAMES} names or fewer at a time.")
    out = []
    with telemetry.run(source, judge_on=engine.client is not None):
        for row in rows:
            name = str(row["name"])
            result = engine.gather_facts(
                name, {"sector": row.get("sector"), "sponsor": row.get("sponsor")}
            )
            telemetry.count_result(result)
            out.append(company_row(name, result))
    return {
        "rows": out,
        "counts": {
            "names": len(out),
            "flagged": sum(r["flag"] == FLAG_LABELS["flagged"] for r in out),
            "to_confirm": sum(len(r["to_confirm"]) for r in out),
            "no_source_found": sum(not r["loans"] and not r["to_confirm"] for r in out),
        },
        "flag_rule": FLAG_RULE,
    }
