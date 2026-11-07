"""Check flagged values against the filings themselves: is the fair value printed next to the borrower's name?
This checks the data pipeline, not the match; a person checks matches.
Usage: PYTHONPATH=. uv run python eval/verify_flags.py data/eval/flag_sample.csv  (columns: lender, borrower_word, fair_value, principal, filing_url)
"""

import hashlib
import html
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(".env")
UA = os.environ.get(
    "SEC_USER_AGENT", "EntityReconciliationMachine research admin@example.org"
)
CACHE = Path("data/raw/filings")
CACHE.mkdir(parents=True, exist_ok=True)


def fetch(url: str) -> str:
    doc = url.split("ix?doc=")[-1]
    full = doc if doc.startswith("http") else "https://www.sec.gov" + doc
    path = CACHE / (hashlib.sha1(full.encode()).hexdigest() + ".htm")
    if not path.exists():
        time.sleep(0.25)  # stays under 5 requests a second
        r = requests.get(full, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path.read_text(encoding="utf-8", errors="ignore")


def visible(doc: str) -> str:
    doc = re.sub(r"<ix:header>.*?</ix:header>", " ", doc, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", doc)))


def forms(value: float) -> list[str]:
    """How a value may be printed: dollars, thousands or millions."""
    v = int(round(value))
    return [
        f"{v:,}",
        f"{round(value / 1000):,}",
        f"{value / 1e6:,.1f}",
        f"{value / 1e6:,.2f}",
    ]


def check(text: str, word: str, fair_value: float, principal: float) -> str:
    pos = [m.start() for m in re.finditer(re.escape(word), text, re.I)]
    if not pos:
        return "name not found in filing"
    fv, pr = forms(fair_value), forms(principal)
    for p in pos:
        window = text[p : p + 1200]
        has = lambda ns: any(
            re.search(r"(?<![\d,.])" + re.escape(n) + r"(?![\d,])", window) for n in ns
        )
        if has(fv) and has(pr):
            return "confirmed"
    return "name found, values not next to it"


def main(path: str) -> None:
    s = pd.read_csv(path)
    out = []
    for r in s.itertuples():
        try:
            res = check(
                visible(fetch(r.filing_url)), r.borrower_word, r.fair_value, r.principal
            )
        except requests.RequestException as e:
            res = f"fetch failed: {type(e).__name__}"
        out.append(res)
        print(r.lender[:30], "|", r.borrower_word, "|", res, flush=True)
    s["result"] = out
    s.to_csv(path.replace(".csv", "_checked.csv"), index=False)
    print(pd.Series(out).value_counts().to_dict())


if __name__ == "__main__":
    main(sys.argv[1])
