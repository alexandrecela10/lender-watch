"""Run the language-model judge on every pool pair through the Batch API. Blind to labels. Saves cost per pair."""

import csv
import json
import time
from pathlib import Path

import anthropic
import pandas as pd
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from dotenv import load_dotenv

from erm.match.judge import parse, request_params

load_dotenv(".env")
c = anthropic.Anthropic()
state = Path("data/eval/judge_batch_id.txt")
p = pd.read_csv("data/eval_pool.csv").fillna("")
if state.exists():
    batch_id = state.read_text().strip()
else:
    reqs = [
        Request(
            custom_id=str(r.pair_id),
            params=MessageCreateParamsNonStreaming(
                **request_params(
                    r.company_name,
                    r.sector,
                    r.sponsor,
                    r.candidate,
                    [r.example_1, r.example_2],
                )
            ),
        )
        for r in p.itertuples()
    ]
    b = c.messages.batches.create(requests=reqs)
    batch_id = b.id
    state.write_text(batch_id)
print("batch", batch_id, flush=True)
while True:
    b = c.messages.batches.retrieve(batch_id)
    if b.processing_status == "ended":
        break
    print(b.request_counts.processing, "left", flush=True)
    time.sleep(30)
rows, tin, tout = [], 0, 0
for item in c.messages.batches.results(batch_id):
    if item.result.type == "succeeded":
        v = parse(item.result.message)
        u = item.result.message.usage
        tin += u.input_tokens
        tout += u.output_tokens
        rows.append(
            dict(pair_id=int(item.custom_id), verdict=v.verdict, reason=v.reason)
        )
    else:
        rows.append(
            dict(
                pair_id=int(item.custom_id),
                verdict="unsure",
                reason=f"batch {item.result.type}",
            )
        )
pd.DataFrame(rows).sort_values("pair_id").to_csv(
    "data/eval/judge_results.csv", index=False, quoting=csv.QUOTE_MINIMAL
)
cost = (tin * 4e-6 + tout * 20e-6) * 0.5
Path("data/eval/judge_cost.json").write_text(
    json.dumps(
        dict(
            pairs=len(rows),
            input_tokens=tin,
            output_tokens=tout,
            usd=round(cost, 3),
            usd_per_100_pairs=round(cost / len(rows) * 100, 3),
            model="claude-opus-5-5",
            effort="low",
            batch=True,
        )
    )
)
print("done", len(rows), "usd", round(cost, 3), flush=True)
