"""Agreed measures over a synthetic portfolio (prototype). Spec: specs/embedded-tools-on-semantic-layer.md.

Definitions live in semantic/measures.yaml. This module computes them. The AI never produces a number here.

Real companies: Lender Watch's own engine on the public sample, AI off, so measures 1 and 2 are exactly Lender
Watch's figures. Invented companies: synthetic lender rows passed straight to Lender Watch's flag code, never mixed
into its holdings, so Lender Watch can't find them. Every value carries its sources, each a filing or synthetic.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import yaml

from erm import telemetry
from erm.api import Engine
from erm.signals import facts_for, flags_for

ROOT = Path(__file__).resolve().parents[1]
MEASURES = ROOT / "semantic/measures.yaml"
SYN = ROOT / "data/synthetic"
PUBLIC = ROOT / "data/public/holdings.parquet"
SEED_ANSWERS = ROOT / "data/public/decisions.sqlite"
FIELDS = (
    "id",
    "name",
    "definition",
    "unit",
    "applies_to",
    "owner",
    "version",
    "compute",
    "explain",
)
INVESTOR = "P1"

log = logging.getLogger("erm.semantic")

NOT_REAL = "Not available for real companies: it needs private data we only have for invented companies."
NOT_IN_PORTFOLIO = "Not in the synthetic portfolio."


def load_measures(path: Path = MEASURES) -> dict[str, dict]:
    """The definitions, checked: every field present, every compute function exists."""
    out = {}
    for m in yaml.safe_load(path.read_text()):
        missing = [f for f in FIELDS if f not in m]
        if missing:
            raise ValueError(f"Measure {m.get('id')} is missing {', '.join(missing)}.")
        if m["applies_to"] not in ("real", "invented", "both"):
            raise ValueError(
                f"Measure {m['id']}: applies_to must be real, invented or both."
            )
        if not callable(getattr(Prototype, m["compute"], None)):
            raise TypeError(
                f"Measure {m['id']}: no function {m['compute']} in erm/semantic.py."
            )
        out[m["id"]] = m
    return out


def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(SYN / name, keep_default_na=False)


def src(kind: str, ref: str) -> dict:
    return {"kind": kind, "ref": ref}


class Portfolio:
    """The synthetic investor's records: funds, stakes and what each fund paid for each company."""

    def __init__(self):
        self.companies = _csv("companies.csv")
        self.positions = _csv("positions.csv")
        self.stakes = _csv("fund_stakes.csv")
        self.financials = _csv("financials.csv")
        self.managers = _csv("manager_values.csv")
        self.by_id = {r.company_id: r for r in self.companies.itertuples()}
        self.by_name = {r.name.casefold(): r for r in self.companies.itertuples()}
        self.weights = self._look_through()

    def _look_through(self) -> dict[str, list[tuple[float, list[int]]]]:
        """Our share of each direct fund, along every path, with the stake rows that make up each path."""
        s = self.stakes
        mine = s[s.owner == INVESTOR]
        paths: dict[str, list[tuple[float, list[int]]]] = {}
        for i, r in mine.iterrows():
            paths.setdefault(r.fund_id, []).append((r.share, [i]))
            for j, inner in s[
                s.owner == r.fund_id
            ].iterrows():  # a fund of funds and the funds it holds
                paths.setdefault(inner.fund_id, []).append(
                    (r.share * inner.share, [i, j])
                )
        return paths

    def find(self, name_or_id: str):
        key = str(name_or_id).strip()
        return self.by_id.get(key) or self.by_name.get(key.casefold())

    def cost(
        self, company_id: str, quarter: str, via_fund_of_funds: bool = False
    ) -> tuple[float, list[dict]]:
        """Look-through cost: over every path, the product of shares times the fund's cost. With its sources.
        `via_fund_of_funds` keeps only paths through a fund of funds (two stake rows)."""
        total, sources = 0.0, []
        held = self.positions[
            (self.positions.company_id == company_id)
            & (self.positions.quarter == quarter)
        ]
        for i, p in held.iterrows():
            for share, stake_rows in self.weights.get(p.fund_id, []):
                if via_fund_of_funds and len(stake_rows) < 2:
                    continue
                total += share * p.cost_usd
                sources += [
                    src("synthetic", f"synthetic:fund_stakes:{r}") for r in stake_rows
                ]
            sources.append(src("synthetic", f"synthetic:positions:{i}"))
        return total, sources

    def total_cost(self, quarter: str) -> float:
        return sum(self.cost(c, quarter)[0] for c in self.companies.company_id)


class Prototype:
    """One function behind every front end: get_measure."""

    def __init__(
        self,
        engine: Engine | None = None,
        writedowns: Callable[[str], list[dict]] | None = None,
    ):
        self.measures = load_measures()
        self.portfolio = Portfolio()
        self.engine = engine or _public_engine()
        self.synthetic_loans = pd.read_parquet(SYN / "holdings.parquet")
        # Confirmed write-downs for a company: [{size_pct_cost, received, event_id}]. Set by the events store.
        self.writedowns = writedowns or (lambda _company_id: [])
        self._lender: dict[tuple[str, str, str], dict] = {}

    # --- Lender facts, real or synthetic -------------------------------------------------------------------

    def lender(self, company, quarter: str, owner: str) -> dict:
        """{status, flags, sources} for a company and quarter. Status is checked or a reason it isn't."""
        key = (company.company_id, quarter, owner)
        if key not in self._lender:
            if company.kind == "real":
                out = self.engine.gather_facts(company.name, as_of=quarter, owner=owner)
                # Same as Lender Watch: figures come from confirmed matches. Unsettled names add a note, not a block.
                if out["facts"]:
                    status = "checked"
                elif out["resolution"]["status"] == "needs_review":
                    status = "Not checked: Lender Watch needs a person to confirm this company's name in the filings."
                else:
                    status = "Not checked: no usable loan in this quarter."
                note = (
                    "Some lender names for this company still need a person's answer."
                    if out["facts"] and out["resolution"]["status"] == "needs_review"
                    else None
                )
                sources = [src("filing", f["filing_url"]) for f in out["facts"]]
                self._lender[key] = {
                    "status": status,
                    "flags": out["flags"],
                    "sources": sources,
                    "note": note,
                }
            else:
                rows = self.synthetic_loans[
                    self.synthetic_loans.company_id == company.company_id
                ]
                periods = sorted(rows.period.unique())
                prior = (
                    periods[periods.index(quarter) - 1]
                    if quarter in periods and periods.index(quarter)
                    else None
                )
                facts = facts_for(rows, quarter, prior)
                flags = asdict(flags_for(facts))
                status = (
                    "checked"
                    if facts
                    else "Not checked: no usable loan in this quarter."
                )
                sources = [src("synthetic", f.filing_url) for f in facts]
                self._lender[key] = {
                    "status": status,
                    "flags": flags,
                    "sources": sources,
                    "note": None,
                }
        return self._lender[key]

    # --- The measures -----------------------------------------------------------------------------------------

    def lender_value(self, c, q, owner):
        lw = self.lender(c, q, owner)
        if lw["status"] != "checked":
            return None, lw["status"], lw["sources"]
        return lw["flags"]["weighted_pct_par"], None, lw["sources"]

    def lender_change(self, c, q, owner):
        if self.engine.previous(q) is None:
            return None, "No earlier quarter is held, so there's no change to show.", []
        lw = self.lender(c, q, owner)
        if lw["status"] != "checked":
            return None, lw["status"], lw["sources"]
        change = lw["flags"]["weighted_change"]
        if change is None:
            return (
                None,
                "Not enough paired loans: too few loans appear in both quarters.",
                lw["sources"],
            )
        return change, None, lw["sources"]

    def cost_in_flagged(self, c, q, owner):
        lw = self.lender(c, q, owner)
        cost, cost_sources = self.portfolio.cost(c.company_id, q)
        if lw["status"] != "checked":
            return None, lw["status"], cost_sources
        flagged = lw["flags"]["level"] == "flagged"
        return (cost if flagged else 0.0), None, lw["sources"] + cost_sources

    def share_cost_flagged(self, c, q, owner):
        value, reason, sources = self.cost_in_flagged(c, q, owner)
        if value is None:
            return None, reason, sources
        return value / self._total(q), None, sources

    def debt_to_ebitda(self, c, q, owner):
        f = self.portfolio.financials
        rows = f[(f.company_id == c.company_id) & (f.quarter == q)]
        i = rows.index[0]
        sources = [src("synthetic", f"synthetic:financials:{i}")]
        ebitda = rows.ebitda_usd.iloc[0]
        if ebitda <= 0:
            return None, "Not meaningful: EBITDA is zero or below.", sources
        return rows.net_debt_usd.iloc[0] / (ebitda * 4), None, sources

    def manager_value(self, c, q) -> tuple[float, list[dict], dict | None]:
        """The manager's value as % of cost at the quarter, after confirmed write-downs received in time."""
        m = self.portfolio.managers
        rows = m[(m.company_id == c.company_id) & (m.quarter == q)]
        i, row = rows.index[0], rows.iloc[0]
        value, sources, applied = (
            float(row.value_pct_cost),
            [src("synthetic", f"synthetic:manager_values:{i}")],
            None,
        )
        for w in sorted(self.writedowns(c.company_id), key=lambda w: w["received"]):
            # Counts from when we learned it, and only if the manager's figure was reported before we did.
            if row.reported < w["received"] <= q:
                value, applied = float(w["size_pct_cost"]), w
                sources.append(src("synthetic", f"synthetic:events:{w['event_id']}"))
        return value, sources, applied

    def manager_lender_gap(self, c, q, owner):
        lw = self.lender(c, q, owner)
        if lw["status"] != "checked":
            return None, lw["status"], lw["sources"]
        value, sources, _ = self.manager_value(c, q)
        return value - lw["flags"]["weighted_pct_par"], None, sources + lw["sources"]

    def share_via_funds_of_funds(self, c, q, owner):
        cost, sources = self.portfolio.cost(c.company_id, q)
        if cost == 0:
            return None, "We paid nothing for this company in this quarter.", sources
        return (
            self.portfolio.cost(c.company_id, q, via_fund_of_funds=True)[0] / cost,
            None,
            sources,
        )

    def _total(self, q: str) -> float:
        key = ("_total", q)
        if key not in self._lender:
            self._lender[key] = self.portfolio.total_cost(q)
        return self._lender[key]

    # --- The one entry point -----------------------------------------------------------------------------------

    def get_measure(
        self,
        measure: str,
        companies: list[str],
        as_of: str | None = None,
        owner: str = "local",
    ) -> dict:
        """One row per company, in the order asked, plus a total row for measures that add up."""
        if measure not in self.measures:
            raise ValueError(
                f"No measure {measure}. Measures: {', '.join(self.measures)}."
            )
        m = self.measures[measure]
        q = self.engine.quarter(as_of)
        rows = []
        with telemetry.run("prototype_measure", judge_on=False):
            for asked in companies:
                c = self.portfolio.find(asked)
                base = {
                    "company": str(asked),
                    "measure": measure,
                    "version": m["version"],
                    "unit": m["unit"],
                    "as_of": q,
                }
                if c is None:
                    rows.append(
                        {
                            **base,
                            "company_id": None,
                            "value": None,
                            "not_available": NOT_IN_PORTFOLIO,
                            "synthetic": False,
                            "sources": [],
                        }
                    )
                    continue
                if m["applies_to"] == "invented" and c.kind == "real":
                    rows.append(
                        {
                            **base,
                            "company_id": c.company_id,
                            "value": None,
                            "not_available": NOT_REAL,
                            "synthetic": False,
                            "sources": [],
                        }
                    )
                    continue
                value, reason, sources = getattr(self, m["compute"])(c, q, owner)
                uses_lenders = m["compute"] != "debt_to_ebitda"
                note = self.lender(c, q, owner)["note"] if uses_lenders else None
                rows.append(
                    {
                        **base,
                        "company": c.name,
                        "company_id": c.company_id,
                        "value": None if value is None else round(float(value), 6),
                        "not_available": reason,
                        "note": note,
                        "synthetic": any(s["kind"] == "synthetic" for s in sources),
                        "sources": sources,
                    }
                )
        out = {
            "measure": measure,
            "name": m["name"],
            "definition": m["definition"],
            "version": m["version"],
            "as_of": q,
            "rows": rows,
        }
        if measure in ("cost_in_flagged", "share_cost_flagged"):
            known = [r for r in rows if r["value"] is not None]
            out["total"] = {
                "value": round(sum(r["value"] for r in known), 6),
                "not_checked": sum(
                    r["company_id"] is not None and r["value"] is None for r in rows
                ),
                "synthetic": True,
            }
        log.info("measure", extra={"names_in": len(companies)})
        return out


def _public_engine() -> Engine:
    """Lender Watch on the public sample with a private copy of the seed answers, AI off: the same on any computer."""
    folder = Path(tempfile.mkdtemp())
    shutil.copy(SEED_ANSWERS, folder / "decisions.sqlite")
    return Engine(
        holdings_path=str(PUBLIC),
        store_path=str(folder / "decisions.sqlite"),
        index_cache=str(Path(tempfile.gettempdir()) / "erm_index.pkl"),
        client=None,
    )


_prototype: Prototype | None = None


def prototype() -> Prototype:
    """Built once per process, on first use. The hosted service never calls this.
    Confirmed write-downs come from the events store in the local data folder."""
    global _prototype
    if _prototype is None:
        import os

        from erm.prototype_store import EventStore

        folder = Path(os.environ.get("LW_DATA_DIR", str(Path.home() / ".erm/service")))
        store = EventStore(folder / "prototype.sqlite")
        _prototype = Prototype(writedowns=store.confirmed_writedowns)
        _prototype.store = store
    return _prototype
