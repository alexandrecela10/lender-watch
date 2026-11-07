"""Run all 291 sponsor companies: judge every unclear pair by batch, save verdicts, then write facts and flags."""

import csv
import json
import time
from pathlib import Path

import anthropic
import pandas as pd
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from dotenv import load_dotenv

from erm.api import Engine
from erm.match.features import compute
from erm.match.rules import is_clear_exact
from erm.match.judge import parse, request_params
from erm.store import JUDGE, pair_id

load_dotenv(".env")
client = anthropic.Anthropic()
e = Engine(client=None)
sp = pd.read_csv("data/sponsors/sponsor_portfolios.csv").fillna("")

# Aliases that automated research found on the 20-company test; judged like any other candidate.
for x in json.load(open("data/eval/alias_test.json"))["results"]:
    for hit in x["hits"]:
        e.store.add_alias(x["company"], hit["alias"], hit["source"])

state = Path("data/eval/full_batch_id.txt")
todo = {}
for r in sp.itertuples():
    for key, g in e.groups(r.company_name).items():
        m = g["mention"]
        f = compute(
            g["via"], m.text, e.doc_freq, e.total_docs, m.left, m.right, m.trade_name
        )
        pid = pair_id(r.company_name, key)
        if (g["via"] == r.company_name and is_clear_exact(f)) or e.store.get(pid):
            continue
        ex = (
            e.index.holdings.iloc[g["rows"]]
            .raw_text.drop_duplicates()
            .str.slice(0, 170)
            .head(2)
            .tolist()
        )
        todo[pid] = (
            r.company_name,
            key,
            request_params(r.company_name, r.sector, r.sponsor, m.text, ex),
        )
print(len(todo), "pairs to judge", flush=True)
if todo:
    if state.exists():
        bid = state.read_text().strip()
    else:
        bid = client.messages.batches.create(
            requests=[
                Request(custom_id=k, params=MessageCreateParamsNonStreaming(**v[2]))
                for k, v in todo.items()
            ]
        ).id
        state.write_text(bid)
    while client.messages.batches.retrieve(bid).processing_status != "ended":
        time.sleep(20)
    tin = tout = 0
    for it in client.messages.batches.results(bid):
        name, key, _ = todo[it.custom_id]
        if it.result.type == "succeeded":
            v = parse(it.result.message)
            tin += it.result.message.usage.input_tokens
            tout += it.result.message.usage.output_tokens
            e.store.save(name, key, v.verdict, JUDGE, v.reason)
        else:
            e.store.save(name, key, "unsure", JUDGE, f"Batch {it.result.type}")
    usd = (tin * 4e-6 + tout * 20e-6) * 0.5
    Path("data/eval/full_cost.json").write_text(
        json.dumps(dict(pairs=len(todo), usd=round(usd, 3)))
    )
    print("usd", round(usd, 3), flush=True)

rows, facts = [], []
t0 = time.time()
for r in sp.itertuples():
    o = e.gather_facts(r.company_name, {"sector": r.sector, "sponsor": r.sponsor})
    res, fl = o["resolution"], o["flags"]
    rows.append(
        dict(
            sponsor=r.sponsor,
            company=r.company_name,
            sector=r.sector,
            status=res["status"],
            borrower=res["canonical_name"],
            level=fl["level"],
            n_lenders=fl["n_lenders"],
            n_loans=fl["n_loans"],
            weighted=fl["weighted_pct_par"],
            weighted_change=fl["weighted_change"],
            lowest=fl["lowest_pct_par"],
            biggest_drop=fl["biggest_drop"],
            below_90=fl["below_90"],
            dropped=fl["dropped"],
            lender_gap=fl["lender_gap"],
            pik=fl["pik"],
            summary=fl["summary"],
            n_candidates=len(res["candidates"]),
            n_unsure=sum(c["verdict"] == "unsure" for c in res["candidates"]),
        )
    )
    for f in o["facts"]:
        facts.append(dict(company=r.company_name, **f))
pd.DataFrame(rows).to_csv("data/eval/full_results.csv", index=False)
pd.DataFrame(facts).to_csv(
    "data/eval/full_facts.csv", index=False, quoting=csv.QUOTE_MINIMAL
)
d = pd.DataFrame(rows)
print("seconds", round(time.time() - t0), d.status.value_counts().to_dict())
with_f = d[d.n_loans > 0]
print(
    "with usable loan",
    len(with_f),
    {k: int(with_f[k].sum()) for k in ["below_90", "dropped", "lender_gap", "pik"]},
    "levels",
    with_f.level.value_counts().to_dict(),
)
print(
    d.groupby("sponsor")
    .apply(lambda g: f"{(g.n_loans > 0).sum()}/{len(g)}", include_groups=False)
    .to_dict()
)
print(
    with_f.sort_values("biggest_drop")
    .head(12)[["company", "n_lenders", "lowest", "biggest_drop", "summary"]]
    .to_string(index=False, max_colwidth=120)
)
