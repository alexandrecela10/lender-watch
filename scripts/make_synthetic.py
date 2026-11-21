"""Build the synthetic portfolio for the prototype (specs/embedded-tools-on-semantic-layer.md, section 1).

Two steps:
  uv run python scripts/make_synthetic.py --select-real   Picks the 20 real companies with Lender Watch, AI off,
                                                          on the public sample. Run once; the result is committed.
  uv run python scripts/make_synthetic.py --seed 2026     Writes everything else in data/synthetic/ from the seed
                                                          and the committed list of real companies.

Every row is marked synthetic. Real companies get only the invented investor's own records: which funds hold them and
what they paid. Nothing invented about a real company itself. No model writes anything here.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data/synthetic"
PUBLIC = ROOT / "data/public/holdings.parquet"
SEED_ANSWERS = ROOT / "data/public/decisions.sqlite"
QUARTERS = ["2026-03-31", "2026-06-30"]
# Managers value their funds part-way through the quarter in this synthetic world, so news after that date can
# still change the quarter-end view.
MANAGER_REPORTED = {"2026-03-31": "2026-02-13", "2026-06-30": "2026-05-15"}
N_REAL, N_INVENTED, N_LETTERS = 20, 40, 20
LENDERS = [f"Synthetic Lender {c}" for c in "ABCDE"]
INVESTOR = "Synthetic Pension Plan"
FUNDS = [f"Synthetic Fund {i}" for i in range(1, 9)]
FUND_OF_FUNDS = {"Synthetic Fund 7": FUNDS[0:3], "Synthetic Fund 8": FUNDS[3:6]}
DIRECT_FUNDS = FUNDS[0:6]

# --- Letters: phrasings per event type, and commentary with no company name and no number ------------------------

WRITE_DOWN = [
    "Following the latest trading update, we have reduced our valuation of {company} to {size} of cost, effective {effective}.",
    "We marked down {company} to {size} of cost as of {effective}, reflecting weaker results.",
    "Our holding in {company} is now carried at {size} of cost, a write-down effective {effective}.",
    "After review, the committee wrote {company} down to {size} of cost with effect from {effective}.",
    "{company} has been revalued at {size} of cost, effective {effective}, following a missed budget.",
    "We have taken a write-down on {company}: it is held at {size} of cost from {effective}.",
]
COVENANT = [
    "{company} breached a financial covenant under its credit agreement on {effective}.",
    "On {effective}, {company} did not meet the leverage test in its loan agreement.",
    "Lenders to {company} were notified of a covenant breach dated {effective}.",
    "{company} reported a covenant breach to its lenders, effective {effective}.",
    "We note that {company} fell short of a loan covenant on {effective}.",
    "A covenant under {company}'s credit facility was breached on {effective}.",
]
COMMENTARY = [
    "Market conditions remained mixed over the quarter.",
    "We continue to work closely with management teams across the portfolio.",
    "Exit activity was slower than we expected.",
    "Our team visited several portfolio companies during the period.",
    "We remain focused on cash generation and cost discipline.",
    "Hiring across the portfolio has slowed.",
    "Customer demand held up better than we feared.",
    "We expect to share more detail at the annual meeting.",
    "Financing markets reopened for stronger credits.",
    "Thank you for your continued support.",
]


def day(d: date) -> str:
    """Canonical date in letters: 15 May 2026."""
    return f"{d.day} {d.strftime('%B %Y')}"


def pct(x: float) -> str:
    """Canonical size in letters: 40.0%."""
    return f"{x:.1f}%"


# --- Choosing the real companies --------------------------------------------------------------------------------


def select_real() -> None:
    """Real companies that Lender Watch settles on its own, with usable loans in both quarters, AI off."""
    from erm.api import Engine

    folder = Path(tempfile.mkdtemp())
    shutil.copy(SEED_ANSWERS, folder / "d.sqlite")
    engine = Engine(
        holdings_path=str(PUBLIC),
        store_path=str(folder / "d.sqlite"),
        index_cache=str(Path(tempfile.gettempdir()) / "erm_index.pkl"),
        client=None,
    )
    demo = pd.read_csv(ROOT / "data/demo/sample_list.csv").Company.tolist()
    sponsors = sorted(
        pd.read_csv(ROOT / "data/sponsors/sponsor_portfolios.csv").company_name.unique()
    )
    flagged, other, seen = [], [], set()
    for name in demo + sponsors:
        if name.casefold() in seen:
            continue
        seen.add(name.casefold())
        june = engine.gather_facts(name)
        res = june["resolution"]
        if res["status"] != "matched" or not june["facts"]:
            continue
        march = engine.gather_facts(name, res=None, as_of=QUARTERS[0])
        if not march["facts"]:
            continue
        (flagged if june["flags"]["level"] == "flagged" else other).append(name)
        if len(flagged) >= 5 and len(flagged) + len(other) >= N_REAL:
            break
    chosen = flagged[:5] + other[: N_REAL - min(len(flagged), 5)]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "real_companies.json").write_text(
        json.dumps({"data_version": engine.data_version, "companies": chosen}, indent=2)
        + "\n"
    )
    print(
        f"{len(chosen)} real companies, {min(len(flagged), 5)} flagged, data version {engine.data_version}"
    )


# --- Generating everything else ---------------------------------------------------------------------------------


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({**r, "synthetic": "true"} if "synthetic" in r else r)


def generate(seed: int, out: Path = OUT) -> None:
    rng = random.Random(seed)
    real = json.loads((OUT / "real_companies.json").read_text())["companies"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "letters").mkdir(exist_ok=True)
    if out != OUT:
        shutil.copy(OUT / "real_companies.json", out / "real_companies.json")

    companies = [
        {"company_id": f"R{i + 1:02d}", "name": n, "kind": "real", "synthetic": True}
        for i, n in enumerate(real)
    ]
    companies += [
        {
            "company_id": f"I{i:02d}",
            "name": f"Synthetic Company {i:02d}",
            "kind": "invented",
            "synthetic": True,
        }
        for i in range(1, N_INVENTED + 1)
    ]
    write_csv(
        out / "investor.csv",
        [{"investor_id": "P1", "name": INVESTOR, "synthetic": True}],
    )
    write_csv(
        out / "funds.csv",
        [
            {
                "fund_id": f"F{i + 1}",
                "name": n,
                "fund_of_funds": n in FUND_OF_FUNDS,
                "synthetic": True,
            }
            for i, n in enumerate(FUNDS)
        ],
    )

    # Who owns what share of each fund. Funds of funds own direct funds only, so there are no loops.
    fid = {n: f"F{i + 1}" for i, n in enumerate(FUNDS)}
    stakes = []
    for n in FUNDS:
        stakes.append(
            {
                "owner": "P1",
                "fund_id": fid[n],
                "share": round(rng.uniform(0.05, 0.25), 4),
                "synthetic": True,
            }
        )
    for fof, held in FUND_OF_FUNDS.items():
        for n in held:
            stakes.append(
                {
                    "owner": fid[fof],
                    "fund_id": fid[n],
                    "share": round(rng.uniform(0.05, 0.20), 4),
                    "synthetic": True,
                }
            )
    write_csv(out / "fund_stakes.csv", stakes)

    # Each company sits in one or two direct funds. Cost moves a little between quarters.
    positions = []
    ids = [c["company_id"] for c in companies]
    for k, cid in enumerate(ids):
        holders = [DIRECT_FUNDS[k % 6]]
        if k % 7 == 0:
            holders.append(DIRECT_FUNDS[(k + 3) % 6])
        for fund in holders:
            cost = round(rng.uniform(5, 80), 2) * 1_000_000
            for q in QUARTERS:
                positions.append(
                    {
                        "fund_id": fid[fund],
                        "company_id": cid,
                        "quarter": q,
                        "cost_usd": round(cost, 2),
                        "synthetic": True,
                    }
                )
                cost *= 1 + rng.choice([0, 0, 0, 0.05, -0.1])
    write_csv(out / "positions.csv", positions)

    invented = [c for c in companies if c["kind"] == "invented"]
    financials, managers, loans = [], [], []
    for k, c in enumerate(invented):
        cid = c["company_id"]
        stressed = k % 4 == 0
        n_loans = rng.randint(1, 3)
        principals = [
            round(rng.uniform(20, 120), 1) * 1_000_000 for _ in range(n_loans)
        ]
        values = []
        for j, p in enumerate(principals):
            march = rng.uniform(78, 92) if stressed else rng.uniform(95, 100.5)
            june = (
                march - rng.uniform(2, 9)
                if stressed
                else march + rng.uniform(-1.5, 1.5)
            )
            values.append((p, round(march, 1), round(june, 1)))
        debt_floor = sum(principals)
        for qi, q in enumerate(QUARTERS):
            revenue = round(rng.uniform(50, 500), 1) * 1_000_000
            margin = (
                rng.uniform(-0.08, -0.01) if k % 10 == 3 else rng.uniform(0.08, 0.30)
            )
            financials.append(
                {
                    "company_id": cid,
                    "quarter": q,
                    "revenue_usd": revenue,
                    "ebitda_usd": round(revenue * margin, 2),
                    "net_debt_usd": round(debt_floor * rng.uniform(1.0, 1.3), 2),
                    "synthetic": True,
                }
            )
            base = rng.uniform(60, 90) if stressed else rng.uniform(95, 140)
            managers.append(
                {
                    "company_id": cid,
                    "quarter": q,
                    "reported": MANAGER_REPORTED[q],
                    "value_pct_cost": round(base - (8 * qi if stressed else 0), 1),
                    "synthetic": True,
                }
            )
        for j, (p, march, june) in enumerate(values):
            lender = LENDERS[(k + j) % len(LENDERS)]
            maturity = f"{2029 + j}-06-30"
            for q, v, scale in (
                (QUARTERS[0], march, 1.0),
                (QUARTERS[1], june, 1.0 - 0.01 * j),
            ):
                principal = round(p * scale, 2)
                loans.append(
                    {
                        "lender": lender,
                        "period": q,
                        "raw_text": f"{c['name']} | First lien term loan {j + 1}",
                        "principal": principal,
                        "fair_value": round(principal * v / 100, 2),
                        "lien": "First lien",
                        "maturity": maturity,
                        "pik_rate": None,
                        "pct_par": round(
                            round(principal * v / 100, 2) / principal * 100, 4
                        ),
                        "excluded_reason": "",
                        "inlineurl": "",
                        "filed": "2026-08-14" if q == QUARTERS[1] else "2026-05-15",
                        "company_id": cid,
                        "synthetic": True,
                    }
                )
    write_csv(out / "financials.csv", financials)
    h = pd.DataFrame(loans)
    h["inlineurl"] = [f"synthetic:holdings:{i}" for i in range(len(h))]
    h.to_parquet(out / "holdings.parquet", index=False, compression="zstd")

    # Events about invented companies only, grouped into letters. Each letter has one date: the date it was received.
    events = []
    pool = [c for c in invented]
    rng.shuffle(pool)
    letter_days = sorted(rng.sample(range(150), N_LETTERS))
    for n in range(N_LETTERS):
        received = date(2026, 2, 1) + timedelta(days=letter_days[n])
        subjects = [pool[(2 * n) % len(pool)]] + (
            [pool[(2 * n + 1) % len(pool)]] if n % 3 == 0 else []
        )
        lines = []
        for s in subjects:
            kind = "write_down" if rng.random() < 0.6 else "covenant_breach"
            effective = received - timedelta(days=rng.randint(3, 20))
            size = round(rng.uniform(30, 85), 1) if kind == "write_down" else ""
            events.append(
                {
                    "event_id": f"E{len(events) + 1:02d}",
                    "company_id": s["company_id"],
                    "type": kind,
                    "size_pct_cost": size,
                    "effective": effective.isoformat(),
                    "received": received.isoformat(),
                    "letter": f"{n + 1:02d}",
                    "synthetic": True,
                }
            )
            phrasing = rng.choice(WRITE_DOWN if kind == "write_down" else COVENANT)
            lines.append(
                phrasing.format(
                    company=s["name"],
                    size=pct(size) if size != "" else "",
                    effective=day(effective),
                )
            )
        commentary = rng.sample(COMMENTARY, rng.randint(2, 4))
        body = commentary[:1] + lines + commentary[1:]
        fund = DIRECT_FUNDS[n % 6]
        text = (
            f"# {fund}: letter to investors\n\n{day(received)}\n\nSynthetic letter, written by code for a test.\n\n"
            + "\n\n".join(body)
            + "\n"
        )
        (out / "letters" / f"{n + 1:02d}.md").write_text(text)
    write_csv(out / "events.csv", events)

    # A manager value reported after a write-down was received already includes it, so it can't count twice.
    for e in sorted(events, key=lambda e: e["received"]):
        if e["type"] != "write_down":
            continue
        for m in managers:
            if m["company_id"] == e["company_id"] and e["received"] <= m["reported"]:
                m["value_pct_cost"] = e["size_pct_cost"]
    write_csv(out / "manager_values.csv", managers)
    write_csv(out / "companies.csv", companies)


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--select-real", action="store_true")
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--out", default=str(OUT))
    a = p.parse_args()
    if a.select_real:
        select_real()
    else:
        generate(a.seed, Path(a.out))
        print(f"Wrote {a.out}")


if __name__ == "__main__":
    main()
