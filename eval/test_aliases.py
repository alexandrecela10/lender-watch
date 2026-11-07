"""Does automated alias research find the names that separate web research found, and what do wrong aliases cost?
Sample: all 13 companies with a found or unsure alias, plus 7 with none. Enriched on purpose: not a rate for all names."""

import concurrent.futures as cf
import json

import anthropic
import pandas as pd
from dotenv import load_dotenv

from erm.match.aliases import research
from erm.retrieve import Index
from erm.textparse import core, find_mention, name_pattern

load_dotenv(".env")
c = anthropic.Anthropic(max_retries=4)
r = pd.read_csv("data/eval/recall_probe.csv")
sp = pd.read_csv("data/sponsors/sponsor_portfolios.csv").set_index("company_name")
pos = r[r.verdict != "no_bdc_loan_found"]
neg = r[r.verdict == "no_bdc_loan_found"].sample(7, random_state=2)
sample = pd.concat([pos, neg])
h = pd.read_parquet("data/holdings_clean.parquet")
idx = Index.build(h[h.period == "2026-06-30"], semantic=False)


def one(row):
    s = sp.loc[row.company_name]
    al, u = research(
        c,
        row.company_name,
        s.sector if isinstance(s.sector, str) else None,
        row.sponsor,
    )
    found = []
    for a in al:
        k = core(a["name"])
        if not k:
            continue
        pat = name_pattern(k)
        rows = [
            i
            for i in idx.rarest_rows(k)
            if find_mention(idx.holdings.raw_text.iloc[i], pat)
        ]
        if rows:
            found.append(
                dict(
                    alias=a["name"],
                    source=a["source_url"],
                    n_holdings=len(rows),
                    n_lenders=int(idx.holdings.lender.iloc[rows].nunique()),
                    example=idx.holdings.raw_text.iloc[rows[0]][:150],
                )
            )
    return dict(
        company=row.company_name,
        probe_verdict=row.verdict,
        probe_alias=row.alias_found_in_bdc,
        aliases=[a["name"] for a in al],
        hits=found,
        **u,
    )


with cf.ThreadPoolExecutor(5) as ex:
    res = list(ex.map(one, sample.itertuples()))
tin = sum(x["input_tokens"] for x in res)
tout = sum(x["output_tokens"] for x in res)
srch = sum(x["searches"] for x in res)
usd = tin * 4e-6 + tout * 20e-6 + srch * 0.01
json.dump(
    dict(results=res, usd=usd, input_tokens=tin, output_tokens=tout, searches=srch),
    open("data/eval/alias_test.json", "w"),
    indent=1,
)
for x in res:
    print(
        x["company"],
        "|",
        x["probe_verdict"][:12],
        "|",
        [(h["alias"], h["n_lenders"]) for h in x["hits"]][:4],
        "| no hit:",
        [a for a in x["aliases"] if a not in [h["alias"] for h in x["hits"]]][:3],
    )
print("usd", round(usd, 2), "searches", srch, "tokens", tin, tout)
