"""Build the answer-key candidate pool: a stratified company sample x candidates from four search methods.
The labelling file hides which method found a pair, so labellers can't favour one."""
import pandas as pd

from erm.retrieve import Index
from erm.textparse import norm

SEED, PER_SPONSOR = 11, 14
sp = pd.read_csv("data/sponsors/sponsor_portfolios.csv")
sample = sp.groupby("sponsor", group_keys=False).sample(n=PER_SPONSOR, random_state=SEED).reset_index(drop=True)
h = pd.read_parquet("data/holdings_clean.parquet")
q2 = h[h.period == "2026-06-30"]
idx = Index.build(q2)
print("borrower vocabulary", len(idx.borrowers))

def lender_count(rows):
    return idx.holdings.lender.iloc[rows].nunique()

out = []
for cid, r in sample.iterrows():
    groups = {}
    for i, m in idx.name_hits(r.company_name):
        g = groups.setdefault(m.key, dict(text=m.text, rows=[], sources=set()))
        g["rows"].append(i)
        g["sources"].add("name")
    for src, found in [("fuzzy", idx.fuzzy_borrowers(r.company_name)), ("tfidf", idx.tfidf_borrowers(r.company_name)),
                       ("embed", idx.embedding_borrowers(r.company_name, str(r.sector)))]:
        for b in found:
            g = groups.setdefault(norm(b), dict(text=b, rows=[], sources=set()))
            g["rows"].extend(idx.borrower_rows[b])
            g["sources"].add(src)
    for key, g in groups.items():
        rows = sorted(set(g["rows"]))
        ex = idx.holdings.raw_text.iloc[rows].drop_duplicates().str.slice(0, 170).head(2).tolist()
        out.append(dict(company_id=cid, sponsor=r.sponsor, company_name=r.company_name, sector=r.sector, hq=r.hq,
                        candidate=g["text"], key=key, sources="+".join(sorted(g["sources"])),
                        n_rows=len(rows), n_lenders=lender_count(rows), example_1=ex[0] if ex else "", example_2=ex[1] if len(ex) > 1 else ""))
pool = pd.DataFrame(out)
pool.insert(0, "pair_id", range(len(pool)))
pool.to_csv("data/eval_pool.csv", index=False)
print(len(sample), "companies", len(pool), "pairs")
print(pool.groupby("company_id").size().describe().round(1).to_dict())
print(pool.sources.value_counts().head(8).to_dict())
print(pool.groupby("company_name").size().sort_values().tail(8).to_dict())
