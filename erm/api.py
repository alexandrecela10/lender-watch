"""The four calls: resolve_entity, gather_facts, enrich_table, review.

Decision order for each candidate borrower: a person's saved answer, then the exact-name rule, then a saved or new
language-model judgment. Anything still unclear goes to a person, and it is never treated as a match.

The judge sends a name, its sector and its owner to Anthropic, so it runs only when the caller passes a client.
With no client, nothing leaves the machine and unclear names go to a person.
"""

from __future__ import annotations

import hashlib
import logging
import time
import pickle
from dataclasses import asdict, dataclass, field
from pathlib import Path

import anthropic
import pandas as pd

from erm import telemetry
from erm.match import judge as judge_mod
from erm.match.features import compute
from erm.retrieve import Index
from erm.signals import facts_for, flags_for, usable
from erm.store import JUDGE, PERSON, Store, pair_id
from erm.textparse import core, find_mention, name_pattern, norm

LATEST, PRIOR = "2026-06-30", "2026-03-31"
NOT_CHECKED = "Not checked automatically. Please confirm."
FLAG_LABELS = {
    "flagged": "Flagged",
    "worth_a_look": "Worth a look",
    "none": "Not flagged",
}
FLAG_RULE = (
    "Flagged: on average, lenders value the company's debt below 90% of what they're owed (bigger loans count more), or that "
    "average fell 5 points or more in a quarter. Worth a look: one loan is below 90% or fell 5 points or more, or two lenders "
    "are 5 points apart on what looks like the same loan. Not flagged only covers lenders that publish their loans. Banks don't."
)


log = logging.getLogger("erm.api")


def call_judge(client, name, sector, sponsor, candidate, examples):
    """One live judge call, logged with verdict, tokens, cost and time, never the names or the reason.
    Raises anthropic.APIError after logging it, so the caller keeps its own fallback."""
    obs = telemetry.start_judge_trace(
        has_sector=bool(sector),
        has_owner=bool(sponsor),
        n_examples=len([e for e in examples if e]),
        prompt_version=judge_mod.PROMPT_VERSION,
    )
    t0 = time.monotonic()
    try:
        v, message = judge_mod.judge(client, name, sector, sponsor, candidate, examples)
    except anthropic.APIError as e:
        telemetry.end_judge_trace(obs, level="ERROR", status_message=type(e).__name__)
        log.warning(
            "judge_error",
            extra={
                "error_type": type(e).__name__,
                "latency_ms": int((time.monotonic() - t0) * 1000),
            },
        )
        raise
    u = message.usage
    cost = judge_mod.cost_usd(message.model, u)
    log.info(
        "judge_call",
        extra={
            "verdict": v.verdict,
            "model": message.model,
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0),
            "cache_write_tokens": getattr(u, "cache_creation_input_tokens", 0),
            "cost_usd": cost,
            "latency_ms": int((time.monotonic() - t0) * 1000),
        },
    )
    telemetry.add_judge_call(cost)
    telemetry.end_judge_trace(
        obs,
        model=message.model,
        usage_details={
            "input": u.input_tokens,
            "output": u.output_tokens,
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0)
            or 0,
        },
        cost_details=None if cost is None else {"total": cost},
        output={"verdict": v.verdict, "stop_reason": message.stop_reason},
    )
    return v


@dataclass
class Candidate:
    pair_id: str
    borrower: str
    mention_key: str
    n_holdings: int
    n_lenders: int
    verdict: str  # match, no_match or unsure
    decided_by: str  # person, judge or name
    reason: str
    example: str
    filing_url: str = ""


@dataclass
class Resolution:
    entity_id: str | None
    query: str
    canonical_name: str | None
    status: str  # matched, needs_review or not_found
    confidence: str  # high, medium or none
    candidates: list[Candidate] = field(default_factory=list)


def is_clear_exact(f) -> bool:
    """Skip the judge when the cleaned names are identical and rare. 39 such pairs on the answer key, none wrong."""
    return (
        f.exact_core
        and f.distinctiveness >= 0.75
        and not f.short_name
        and f.left_words == 0
    )


class Engine:
    def __init__(
        self,
        holdings_path="data/holdings_clean.parquet",
        store_path="data/decisions.sqlite",
        index_cache="data/index.pkl",
        client=None,
    ):
        self.holdings = pd.read_parquet(holdings_path)
        self.store = Store(store_path)
        self.client = client  # None means unclear pairs go straight to a person
        self.index = self._load_index(Path(index_cache))
        self.doc_freq = {t: len(rows) for t, rows in self.index.tokens.items()}
        self.total_docs = len(self.index.holdings)

    def _load_index(self, cache: Path) -> Index:
        latest = self.holdings[self.holdings.period == LATEST]
        if cache.exists():
            with cache.open("rb") as f:
                return pickle.load(f)
        idx = Index.build(latest, semantic=False)
        with cache.open("wb") as f:
            pickle.dump(idx, f)
        return idx

    def groups(self, name: str) -> dict[str, dict]:
        """Candidate borrowers for a name, including under any saved alias. One group per distinct borrower form."""
        groups: dict[str, dict] = {}
        for label in [name, *self.store.aliases(name)]:
            for i, m in self.index.name_hits(label):
                g = groups.setdefault(m.key, {"mention": m, "rows": [], "via": label})
                g["rows"].append(i)
        return groups

    def _decide(self, name, sector, sponsor, key, g) -> Candidate:
        rows = self.index.holdings.iloc[g["rows"]]
        m = g["mention"]
        examples = rows.raw_text.drop_duplicates().str.slice(0, 170).head(2).tolist()
        pid = pair_id(name, key)
        base = dict(
            pair_id=pid,
            borrower=m.text,
            mention_key=key,
            n_holdings=len(rows),
            n_lenders=rows.lender.nunique(),
            example=examples[0],
            filing_url=rows.inlineurl.iloc[0],
        )

        saved = self.store.get(pid)
        if saved and saved.decided_by == PERSON:
            return Candidate(
                **base,
                verdict=saved.verdict,
                decided_by=PERSON,
                reason=saved.reason or "Confirmed by a person",
            )

        f = compute(
            g["via"],
            m.text,
            self.doc_freq,
            self.total_docs,
            m.left,
            m.right,
            m.trade_name,
        )
        if g["via"] == name and is_clear_exact(f):
            return Candidate(
                **base,
                verdict="match",
                decided_by="name",
                reason="Same name in both, and the name is uncommon",
            )

        if saved and not (self.client and saved.reason == NOT_CHECKED):
            return Candidate(
                **base,
                verdict=saved.verdict,
                decided_by=saved.decided_by,
                reason=saved.reason,
            )
        if self.client is None:
            d = self.store.save(name, key, "unsure", JUDGE, NOT_CHECKED)
            return Candidate(
                **base, verdict=d.verdict, decided_by=d.decided_by, reason=d.reason
            )
        try:
            v = call_judge(self.client, name, sector, sponsor, m.text, examples)
        except (
            anthropic.APIError
        ):  # one failed call shouldn't stop the list; ask again next run
            d = self.store.save(name, key, "unsure", JUDGE, NOT_CHECKED)
            return Candidate(
                **base, verdict=d.verdict, decided_by=d.decided_by, reason=d.reason
            )
        d = self.store.save(name, key, v.verdict, JUDGE, v.reason)
        return Candidate(
            **base, verdict=d.verdict, decided_by=d.decided_by, reason=d.reason
        )

    def resolve_entity(self, name: str, context: dict | None = None) -> Resolution:
        """Find the company in the source. `context` may carry sector and sponsor."""
        context = context or {}
        c = core(name)
        cands = [
            self._decide(name, context.get("sector"), context.get("sponsor"), k, g)
            for k, g in self.groups(name).items()
        ]
        cands.sort(
            key=lambda x: (
                -(x.verdict == "match"),
                -(x.verdict == "unsure"),
                -x.n_holdings,
            )
        )
        matched = [x for x in cands if x.verdict == "match"]
        unsure = [x for x in cands if x.verdict == "unsure"]
        if not matched and not unsure:
            return Resolution(None, name, None, "not_found", "none", cands)
        entity = "ent_" + hashlib.sha1(c.encode()).hexdigest()[:10]
        canonical = matched[0].borrower if matched else None
        status = "needs_review" if unsure else "matched"
        confidence = (
            "high" if matched and not unsure else "medium" if matched else "none"
        )
        return Resolution(entity, name, canonical, status, confidence, cands)

    def _matched_rows(self, res: Resolution) -> pd.DataFrame:
        """Rows of confirmed matches across all periods. A row counts only if the borrower it names is a confirmed form:
        confirming "Ascensus" must not bring back "Ascensus Specialties", which a person or the judge rejected."""
        keys = {x.mention_key for x in res.candidates if x.verdict == "match"}
        if not keys:
            return self.holdings.iloc[0:0]
        keep = []
        for key in keys:
            p = name_pattern(key)
            sub = self.holdings[self.holdings.raw_text.str.contains(p)]
            same = [
                (m := find_mention(t, p)) is not None and m.key in keys
                for t in sub.raw_text
            ]
            keep.append(sub.loc[pd.Series(same, index=sub.index, dtype=bool)])
        return pd.concat(keep).loc[lambda d: ~d.index.duplicated()]

    def gather_facts(
        self, name: str, context: dict | None = None, res: Resolution | None = None
    ) -> dict:
        """Loan facts for confirmed matches. Every fact carries its filing link and row text."""
        res = res or self.resolve_entity(name, context)
        rows = self._matched_rows(res)
        facts = facts_for(rows, LATEST, PRIOR)
        flags = flags_for(facts)
        excluded = rows[(rows.period == LATEST) & (rows.excluded_reason != "")]
        return {
            "resolution": asdict(res),
            "flags": asdict(flags),
            "facts": [asdict(f) for f in facts],
            "n_positions_used": int(len(usable(rows[rows.period == LATEST]))),
            "excluded": excluded.excluded_reason.value_counts().to_dict(),
            "excluded_filing": excluded.inlineurl.iloc[0] if len(excluded) else "",
        }

    def enrich_table(
        self,
        in_path,
        name_column: str,
        out_path,
        sector_column=None,
        sponsor_column=None,
    ) -> pd.DataFrame:
        """Same spreadsheet back with lender columns added, plus one row per loan with its filing link.

        An .xlsx gets a second sheet. A .csv gets a second file ending in _loans.csv.
        """
        t = (
            pd.read_excel(in_path)
            if str(in_path).endswith((".xlsx", ".xls"))
            else pd.read_csv(in_path)
        )
        summary, loans = [], []
        for r in t.to_dict("records"):
            ctx = {
                "sector": r.get(sector_column) if sector_column else None,
                "sponsor": r.get(sponsor_column) if sponsor_column else None,
            }
            name = str(r[name_column])
            out = self.gather_facts(name, ctx)
            telemetry.count_result(out)
            summary.append(summary_row(out))
            loans += loan_rows(name, out)
        result = pd.concat([t, pd.DataFrame(summary)], axis=1)
        write_workbook(result, pd.DataFrame(loans, columns=LOAN_COLUMNS), out_path)
        return result

    def answer(self, name: str, mention_key: str, same: bool, reason: str = "") -> dict:
        """A person's answer on any candidate, including one the name rule accepted and so never saved."""
        d = self.store.save(
            name, mention_key, "match" if same else "no_match", PERSON, reason
        )
        log.info("person_answer", extra={"decided_by": PERSON, "verdict": d.verdict})
        return asdict(d)

    def review(self, pair: str, accept: bool, reason: str = "") -> dict:
        d = self.store.review(pair, accept, reason)
        log.info("person_answer", extra={"decided_by": PERSON, "verdict": d.verdict})
        return asdict(d)


def lender_data_label(out: dict) -> str:
    """What we know about a company, so that an unclear match or an unusable row never reads as no data."""
    status = out["resolution"]["status"]
    if out["facts"]:
        return "Found, more matches to confirm" if status == "needs_review" else "Found"
    if status == "needs_review":
        return "To confirm"
    if out["excluded"]:
        return "Listed by lenders, but the amounts can't be used. See the filing."
    if status == "matched":
        return "Found, but no usable value this quarter"
    return "No public lender found"


def summary_row(out: dict) -> dict:
    fl, facts = out["flags"], out["facts"]
    lowest = facts[0] if facts else None
    return {
        "Lender data": lender_data_label(out),
        "Flag": FLAG_LABELS[fl["level"]] if facts else "",
        "What lenders show": fl["summary"] if facts else "",
        "Lender borrower name": out["resolution"]["canonical_name"],
        "Lenders": fl["n_lenders"] or None,
        "Average value (% of amount owed, bigger loans count more)": fl[
            "weighted_pct_par"
        ],
        "Change in a quarter (points)": fl["weighted_change"],
        "Lowest loan (% of amount owed)": fl["lowest_pct_par"],
        "Largest change on one loan (points)": fl["biggest_drop"],
        "Some interest paid with more debt": ("Yes" if fl["pik"] else "No")
        if facts
        else "",
        "Filing behind lowest value": lowest["filing_url"]
        if lowest
        else out.get("excluded_filing", ""),
        "Rows left out, amounts unusable (see filing)": sum(out["excluded"].values())
        or None,
    }


LOAN_COLUMNS = [
    "Company",
    "Lender",
    "Loan type",
    "Due",
    "Amount owed ($)",
    "Value this quarter (% of amount owed)",
    "Value last quarter (% of amount owed)",
    "Change (points)",
    "Filed",
    "Filing",
    "Filing text",
]


def loan_rows(name: str, out: dict) -> list[dict]:
    return [
        dict(
            zip(
                LOAN_COLUMNS,
                [
                    name,
                    f["lender"],
                    f["lien"],
                    f["maturity"],
                    f["principal"],
                    f["pct_par"],
                    f["previous_pct_par"],
                    f["change"],
                    f["filed"],
                    f["filing_url"],
                    f["filing_row"],
                ],
            )
        )
        for f in out["facts"]
    ]


def write_workbook(summary: pd.DataFrame, loans: pd.DataFrame, out) -> None:
    """`out` is a path or a binary buffer. A buffer is written as Excel."""
    if str(out).endswith(".csv"):
        summary.to_csv(out, index=False)
        loans.to_csv(str(out)[:-4] + "_loans.csv", index=False)
        return
    with pd.ExcelWriter(out) as w:
        summary.to_excel(w, sheet_name="Your list", index=False)
        loans.to_excel(w, sheet_name="All loans", index=False)


def default_client():
    """Judge client if a key is configured; otherwise None. Pass the result to Engine only when the user has agreed to
    send names outside their machine."""
    import os

    from dotenv import load_dotenv

    load_dotenv(".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic()


__all__ = ["Engine", "default_client", "norm"]
