"""Lender-side facts and flags for one company's holdings.

Rules that came from checking real rows:
- Pair and compare loan by loan, then weigh by size. A lowest-position rule flagged 11 companies whose debt averages 90%
  of par or more, such as Bullhorn on one $68k position.
- A quarter-on-quarter change needs the same lender and the same loan. Without a confident pairing, report no change.
- A gap between lenders needs the same lien and maturity. Otherwise it may be two different loans (Bonterra).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import pandas as pd

from erm.textparse import norm

BELOW_PAR = 90.0
DROP_POINTS = 5.0
GAP_POINTS = 5.0
MAX_PRINCIPAL_CHANGE = 0.25  # above this a "same" loan was likely resized or isn't the same loan
MIN_PAIRED_SHARE = 0.5  # a company-level change needs last quarter's value for at least half the debt by size


@dataclass(frozen=True)
class Fact:
    lender: str
    period: str
    loan: str
    lien: str | None
    maturity: str | None
    principal: float
    fair_value: float
    pct_par: float
    pik: bool
    previous_pct_par: float | None
    change: float | None
    filing_url: str
    filing_row: str
    filed: str


def _descriptor(raw: str) -> str:
    """Holding text with numbers removed, so a rate or date change doesn't break the pairing across quarters."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "", norm(raw))).strip()


def usable(rows: pd.DataFrame) -> pd.DataFrame:
    """Funded debt with a plausible value, one row per loan position."""
    u = rows[rows.excluded_reason == ""]
    return u.drop_duplicates(["lender", "period", "principal", "fair_value", "lien", "maturity"])


def pair_quarters(latest: pd.DataFrame, prior: pd.DataFrame) -> dict[int, float]:
    """Map each latest row to its prior-quarter value. Each prior row is used at most once."""
    out: dict[int, float] = {}
    used: set[int] = set()
    latest = latest.assign(_d=latest.raw_text.map(_descriptor))
    prior = prior.assign(_d=prior.raw_text.map(_descriptor))
    # Unchanged positions first, so a 1.50M loan can't steal the prior row of a different 1.49M loan.
    for i, r in latest.iterrows():
        same = prior[(prior.lender == r.lender) & (prior.principal == r.principal) & (prior.fair_value == r.fair_value)]
        same = same[~same.index.isin(used)]
        if len(same):
            j = same.index[0]
            out[i] = same.loc[j, "pct_par"]
            used.add(j)
    for i, r in latest.iterrows():
        if i in out:
            continue
        c = prior[(prior.lender == r.lender) & (prior._d == r._d) & ~prior.index.isin(used)]
        if r.maturity is not None:
            c = c[c.maturity.isna() | (c.maturity == r.maturity)]
        if not len(c):
            continue
        dist = (c.principal - r.principal).abs() / r.principal
        j = dist.idxmin()
        if dist[j] <= MAX_PRINCIPAL_CHANGE:
            out[i] = c.loc[j, "pct_par"]
            used.add(j)
    return out


def facts_for(rows: pd.DataFrame, latest_period: str, prior_period: str | None) -> list[Fact]:
    u = usable(rows)
    latest = u[u.period == latest_period]
    prior = u[u.period == prior_period] if prior_period else u.iloc[0:0]
    prev = pair_quarters(latest, prior) if len(prior) else {}
    out = []
    for i, r in latest.iterrows():
        p = prev.get(i)
        pik = pd.notna(r.pik_rate) and r.pik_rate > 0
        out.append(
            Fact(
                lender=r.lender, period=r.period, loan=r.raw_text[:160],
                lien=r.lien if isinstance(r.lien, str) else None,
                maturity=r.maturity if isinstance(r.maturity, str) else None,
                principal=float(r.principal), fair_value=float(r.fair_value), pct_par=round(float(r.pct_par), 1),
                pik=bool(pik), previous_pct_par=round(float(p), 1) if p is not None else None,
                change=round(float(r.pct_par - p), 1) if p is not None else None,
                filing_url=r.inlineurl, filing_row=r.raw_text, filed=r.filed,
            )
        )
    return sorted(out, key=lambda f: f.pct_par)


@dataclass(frozen=True)
class Flags:
    level: str  # flagged, worth_a_look or none
    n_lenders: int
    n_loans: int
    weighted_pct_par: float | None  # average value of the company's debt, weighted by loan size
    weighted_change: float | None  # same average on loans paired with last quarter
    lowest_pct_par: float | None
    biggest_drop: float | None
    below_90: bool  # at least one position is below 90
    dropped: bool  # at least one position fell 5 points or more
    lender_gap: bool
    pik: bool
    summary: str  # plain sentences for the analyst

    @property
    def any(self) -> bool:
        return self.level != "none"


_KEEP_UPPER = {"BDC", "LLC", "KKR", "FS", "SLR", "SCP", "TCP", "BSP", "AB", "MSC", "PGIM", "HPS", "TPG", "NMF", "CCS", "SL", "II", "III", "IV", "L.L.C.", "LP", "OHA", "WTI", "CION"}


def _short(lender: str) -> str:
    """SEC names are upper case. Title-case them without breaking acronyms."""
    return " ".join(w if w in _KEEP_UPPER else w.title() for w in lender.split())


def _money(amount: float) -> str:
    """Filers report dollars. Shown so a small position reads as small."""
    if amount >= 1e6:
        return f"${amount / 1e6:,.1f}M"
    return f"${amount / 1e3:,.0f}k"


def _weighted(facts: list[Fact]) -> tuple[float, float | None]:
    total = sum(f.principal for f in facts)
    avg = sum(f.pct_par * f.principal for f in facts) / total
    paired = [f for f in facts if f.change is not None]
    held = sum(f.principal for f in paired)
    change = sum(f.change * f.principal for f in paired) / held if held >= total * MIN_PAIRED_SHARE else None
    return round(avg, 1), round(change, 1) if change is not None else None


def flags_for(facts: list[Fact]) -> Flags:
    """Flagged means the company's debt as a whole, weighted by loan size. A single small position can't flag a company.

    Bullhorn has 52 positions averaging 98.2% of par. One $68k position at 80.9% makes it worth a look, not flagged.
    """
    if not facts:
        return Flags("none", 0, 0, None, None, None, None, False, False, False, False, "No funded loan with a usable value in this quarter.")
    avg, change = _weighted(facts)
    low = min(facts, key=lambda f: f.pct_par)
    drops = [f for f in facts if f.change is not None]
    worst = min(drops, key=lambda f: f.change) if drops else None
    below, dropped = low.pct_par < BELOW_PAR, bool(worst and worst.change <= -DROP_POINTS)

    gap = None
    groups: dict[tuple, list[Fact]] = {}
    for f in facts:
        if f.lien and f.maturity:
            groups.setdefault((f.lien, f.maturity), []).append(f)
    for fs in groups.values():
        if len({f.lender for f in fs}) >= 2:
            hi, lo = max(fs, key=lambda f: f.pct_par), min(fs, key=lambda f: f.pct_par)
            if hi.pct_par - lo.pct_par >= GAP_POINTS and (gap is None or hi.pct_par - lo.pct_par > gap[0].pct_par - gap[1].pct_par):
                gap = (hi, lo)

    flagged = avg < BELOW_PAR or (change is not None and change <= -DROP_POINTS)
    level = "flagged" if flagged else "worth_a_look" if below or dropped or gap else "none"

    parts = []
    if level == "none":
        parts.append(f"Lenders value this debt at {avg:.1f}% of the amount owed on average, with no large fall.")
    else:
        moved = f", {'down' if change < 0 else 'up'} {abs(change):.1f} points in a quarter" if change is not None and abs(change) >= 1 else ""
        parts.append(f"Lenders value this debt at {avg:.1f}% of the amount owed on average{moved}.")
    if dropped:
        parts.append(f"Largest fall: {_short(worst.lender)} cut a {_money(worst.principal)} loan from {worst.previous_pct_par:.1f}% to {worst.pct_par:.1f}%.")
    elif below:
        parts.append(f"Lowest: {_short(low.lender)} values a {_money(low.principal)} loan at {low.pct_par:.1f}%.")
    if gap:
        parts.append(f"On what looks like the same loan, {_short(gap[0].lender)} says {gap[0].pct_par:.1f}% and {_short(gap[1].lender)} says {gap[1].pct_par:.1f}%.")
    pik = any(f.pik for f in facts)
    if pik:
        parts.append("Some interest is paid with more debt instead of cash.")
    return Flags(
        level=level, n_lenders=len({f.lender for f in facts}), n_loans=len(facts), weighted_pct_par=avg, weighted_change=change,
        lowest_pct_par=low.pct_par, biggest_drop=worst.change if worst else None, below_90=below, dropped=dropped,
        lender_gap=bool(gap), pik=pik, summary=" ".join(parts),
    )


def fact_dict(f: Fact) -> dict:
    return asdict(f)
