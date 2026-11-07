"""Lender Watch: pick a list of companies and see which ones their lenders have marked down, with the filing behind each number.
Run: uv run streamlit run app/review.py

Public mode (the hosted demo) starts when data/holdings_clean.parquet is absent or ERM_PUBLIC=1. It uses public sample data,
takes no uploads, makes no AI calls, and keeps each visitor's answers to that visitor.
"""

import copy
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from erm.api import (
    FLAG_LABELS,
    FLAG_RULE,
    LATEST,
    LOAN_COLUMNS,
    Engine,
    default_client,
    lender_data_label,
    loan_rows,
    summary_row,
    write_workbook,
)

st.set_page_config(page_title="Lender Watch", layout="wide")
PUBLIC_HOLDINGS, PUBLIC_DECISIONS = (
    "data/public/holdings.parquet",
    "data/public/decisions.sqlite",
)
PUBLIC = (
    os.environ.get("ERM_PUBLIC") == "1"
    or not Path("data/holdings_clean.parquet").exists()
)
REPO = "https://github.com/alexandrecela10/lender-watch"
CASE_STUDY = "https://alexandrecela10.github.io/projects/lender-watch/"
PICK_NONE = "None"
ALL_FIRMS = "All 6 firms (a few minutes)"
MAX_TYPED = 20
LEVEL_ORDER = {"flagged": 0, "worth_a_look": 1, "none": 2}


@st.cache_resource(
    show_spinner="Loading lender filings. The first visit takes about a minute."
)
def base_engine() -> Engine:
    if PUBLIC:
        return Engine(
            holdings_path=PUBLIC_HOLDINGS,
            store_path=PUBLIC_DECISIONS,
            index_cache=str(Path(tempfile.gettempdir()) / "erm_index.pkl"),
            client=None,
        )
    return Engine(client=None)


def get_engine() -> Engine:
    """Public visitors each get a private copy of the saved answers, so one visitor's answer never reaches another."""
    if not PUBLIC:
        return base_engine()
    if "engine" not in st.session_state:
        from erm.store import Store

        path = Path(tempfile.mkdtemp()) / "decisions.sqlite"
        shutil.copy(PUBLIC_DECISIONS, path)
        session_engine = copy.copy(base_engine())
        session_engine.store = Store(path)
        st.session_state["engine"] = session_engine
    return st.session_state["engine"]


@st.cache_data(show_spinner=False)
def sample_list() -> pd.DataFrame:
    sp = pd.read_csv("data/sponsors/sponsor_portfolios.csv")
    return sp[["company_name", "sponsor", "sector"]].rename(
        columns={"company_name": "Company", "sponsor": "Owner", "sector": "Sector"}
    )


def run(
    engine: Engine, names: pd.DataFrame, name_col: str, sector_col: str, owner_col: str
) -> list[dict]:
    out, bar = [], st.progress(0.0, "Checking lender filings")
    records = names.to_dict("records")
    for i, r in enumerate(records):
        ctx = {"sector": r.get(sector_col), "sponsor": r.get(owner_col)}
        out.append(
            engine.gather_facts(str(r[name_col]), ctx)
            | {"row": r, "name": str(r[name_col]), "ctx": ctx}
        )
        bar.progress((i + 1) / len(records), f"Checked {i + 1} of {len(records)}")
    bar.empty()
    return out


def answer(
    engine: Engine, results: list[dict], mention_key: str, name: str, same: bool
) -> None:
    """Save the answer, then work that company out again straight away."""
    engine.answer(name, mention_key, same)
    for r in results:
        if r["name"] == name:
            r.update(engine.gather_facts(name, r["ctx"]))
    st.rerun()


def sample_choice() -> pd.DataFrame:
    sp = sample_list()
    firms = sorted(sp.Owner.unique())
    default = firms.index("Thoma Bravo") if "Thoma Bravo" in firms else 0
    firm = st.selectbox(
        "Companies owned by this private equity firm, from its own website",
        [*firms, ALL_FIRMS],
        index=default,
    )
    return sp if firm == ALL_FIRMS else sp[sp.Owner == firm]


def choose_list() -> tuple[pd.DataFrame | None, str, str, str]:
    if PUBLIC:
        names = sample_choice()
        typed = st.text_area(
            f"Or type company names, one per line (up to {MAX_TYPED}). Public names only: this is a public website."
        )
        lines = [x.strip() for x in typed.splitlines() if x.strip()][:MAX_TYPED]
        if lines:
            return pd.DataFrame({"Company": lines}), "Company", "Sector", "Owner"
        st.caption(f"To check a private list, [run it on your own computer]({REPO}).")
        return names, "Company", "Sector", "Owner"
    upload = st.file_uploader(
        "Your list (Excel or CSV, one company per row)", type=["xlsx", "csv"]
    )
    if not upload:
        return sample_choice(), "Company", "Sector", "Owner"
    try:
        names = (
            pd.read_excel(upload)
            if upload.name.endswith("xlsx")
            else pd.read_csv(upload)
        )
    except Exception:  # noqa: BLE001  (pandas raises many types on a bad file)
        st.error(
            "We couldn't read that file. Save it as .xlsx or .csv, with column names in the first row, and try again."
        )
        return None, "", "", ""
    if names.empty:
        st.error("That file has no rows.")
        return None, "", "", ""
    cols = list(names.columns)
    a, b, c = st.columns(3)
    name_col = a.selectbox("Company name column", cols)
    sector_col = b.selectbox("Industry column (optional)", [PICK_NONE, *cols])
    owner_col = c.selectbox("Owner column (optional)", [PICK_NONE, *cols])
    return names.dropna(subset=[name_col]), name_col, sector_col, owner_col


def show_proof(engine: Engine, results: list[dict], ranked: list[dict]) -> None:
    st.markdown("#### Step 3: Check the proof")
    pick = st.selectbox(
        "Pick a company to see each lender's value and the filing behind it",
        [r["name"] for r in ranked],
    )
    chosen = next(r for r in ranked if r["name"] == pick)
    st.markdown(f"**{chosen['flags']['summary']}**")
    st.caption(f"Lenders call this borrower: {chosen['resolution']['canonical_name']}")
    facts = pd.DataFrame(chosen["facts"])[
        [
            "lender",
            "principal",
            "pct_par",
            "previous_pct_par",
            "change",
            "lien",
            "maturity",
            "filing_row",
            "filing_url",
        ]
    ]
    facts.columns = [
        "Lender",
        "Amount owed ($)",
        "Value now (% of amount owed)",
        "Last quarter",
        "Change",
        "Loan type",
        "Due",
        "What the filing says",
        "Filing",
    ]
    st.dataframe(
        facts,
        hide_index=True,
        width="stretch",
        column_config={
            "Filing": st.column_config.LinkColumn("Filing", display_text="Open")
        },
    )
    if chosen["excluded"]:
        st.caption(
            f"We left out {sum(chosen['excluded'].values())} other rows because their amounts can't be used. [See the filing]({chosen['excluded_filing']})."
        )
    why = pd.DataFrame(chosen["resolution"]["candidates"])[
        ["borrower", "verdict", "decided_by", "reason", "n_lenders"]
    ]
    why["verdict"] = why.verdict.map(
        {
            "match": "Same company",
            "no_match": "Different company",
            "unsure": "To confirm",
        }
    )
    why["decided_by"] = why.decided_by.map(
        {"person": "You", "judge": "AI", "name": "Exact name"}
    )
    why.columns = ["Name in the filings", "Decision", "Decided by", "Why", "Lenders"]
    with st.expander("How we matched this company"):
        st.dataframe(why, hide_index=True, width="stretch")
        for c in chosen["resolution"]["candidates"]:
            if c["verdict"] == "match" and c["decided_by"] != "person":
                a, b = st.columns([6, 1])
                a.write(c["borrower"])
                if b.button(
                    "Not this company", key="r" + c["pair_id"] + chosen["name"]
                ):
                    answer(engine, results, c["mention_key"], chosen["name"], False)


def show_results(engine: Engine, results: list[dict]) -> None:
    found = [r for r in results if r["facts"]]
    flagged = [r for r in found if r["flags"]["level"] == "flagged"]
    look = [r for r in found if r["flags"]["level"] == "worth_a_look"]
    unclear = [r for r in results if r["resolution"]["status"] == "needs_review"]
    no_data = [r for r in results if lender_data_label(r) == "No public lender found"]
    st.markdown("#### Step 2: Read the result")
    st.subheader(
        f"{len(flagged)} of {len(results)} companies are flagged: their lenders have marked the debt down"
    )
    st.write(
        f"{len(look)} more are worth a look. We found usable values for {len(found)} companies. {len(unclear)} have possible matches for you "
        f"to confirm in the next tab. {len(no_data)} have no public lender, which doesn't mean they have no debt: banks don't publish theirs."
    )
    with st.expander("What the flags mean"):
        st.write(FLAG_RULE)
    ordered = sorted(
        results,
        key=lambda r: (
            not r["facts"],
            LEVEL_ORDER[r["flags"]["level"]],
            r["flags"]["weighted_pct_par"] or 0,
        ),
    )
    table = pd.DataFrame(
        [
            {
                "Company": r["name"],
                "Flag": FLAG_LABELS[r["flags"]["level"]] if r["facts"] else "",
                "What lenders show": r["flags"]["summary"]
                if r["facts"]
                else lender_data_label(r),
                "Lenders": r["flags"]["n_lenders"] or None,
                "Average value (% of amount owed)": r["flags"]["weighted_pct_par"],
                "Change in a quarter (points)": r["flags"]["weighted_change"],
            }
            for r in ordered
        ]
    )
    st.dataframe(table, hide_index=True, width="stretch")

    buf = io.BytesIO()
    summary = pd.concat(
        [
            pd.DataFrame([r["row"] for r in results]),
            pd.DataFrame([summary_row(r) for r in results]),
        ],
        axis=1,
    )
    loans = pd.DataFrame(
        [x for r in results for x in loan_rows(r["name"], r)], columns=LOAN_COLUMNS
    )
    write_workbook(summary, loans, buf)
    st.download_button(
        "Download as Excel, with a filing link for every loan",
        buf.getvalue(),
        "lender_watch.xlsx",
    )

    ranked = [r for r in ordered if r["facts"]]
    if ranked:
        show_proof(engine, results, ranked)


def show_review(engine: Engine, results: list[dict]) -> None:
    to_confirm = [
        (r["name"], c)
        for r in results
        for c in r["resolution"]["candidates"]
        if c["verdict"] == "unsure"
    ]
    answered = [
        (r["name"], c)
        for r in results
        for c in r["resolution"]["candidates"]
        if c["decided_by"] == "person"
    ]
    if not results:
        st.write("Check a list first. Any unclear matches will appear here.")
    elif not to_confirm:
        st.write("Nothing left to confirm on this list.")
    else:
        st.subheader(
            f"{len(to_confirm)} possible matches need your answer. We save each one and won't ask again."
        )
        st.write(
            "Lenders often use a different name from the one on your list. Only a confirmed match counts in your result."
        )
    for name, c in to_confirm:
        with st.container(border=True):
            st.markdown(f"Is **{name}** the same company as **{c['borrower']}**?")
            st.write(
                f'{c["n_lenders"]} lender(s) hold this loan. The filing says: "{c["example"]}"'
            )
            if c["filing_url"]:
                st.markdown(f"[Open the filing]({c['filing_url']})")
            st.caption(c["reason"])
            a, b, _ = st.columns([1, 1, 6])
            if a.button("Same company", key="y" + c["pair_id"] + name):
                answer(engine, results, c["mention_key"], name, True)
            if b.button("Different", key="n" + c["pair_id"] + name):
                answer(engine, results, c["mention_key"], name, False)
    if answered:
        with st.expander(
            f"Your answers ({len(answered)}). Change one if you got it wrong."
        ):
            for name, c in answered:
                same = c["verdict"] == "match"
                a, b = st.columns([6, 1])
                a.write(
                    f"{name} and {c['borrower']}: {'same company' if same else 'different'}"
                )
                if b.button("Change", key="c" + c["pair_id"] + name):
                    answer(engine, results, c["mention_key"], name, not same)


engine = get_engine()
st.title("Lender Watch")
st.write(
    "Private equity firms own companies, and those companies borrow money. Some lenders must publish every loan each quarter, "
    "and what they think it's worth today. A value well below the amount owed can mean a lender expects trouble."
)
st.write(
    "You're checking on the companies you've invested in through these firms. Their lenders use different names, so the answer is hard to find by hand. "
    f"This tool finds it, with the filing as proof. Data: public SEC filings for the quarter ending {pd.Timestamp(LATEST):%d %B %Y}."
)
st.caption(
    "Values are each lender's own estimate, not a market price. Not investment advice. Matching is scored against answers an AI wrote, "
    f"and a person hasn't checked them yet. [Read the case study]({CASE_STUDY})."
)

tab_list, tab_review = st.tabs(["Your list", "Matches to confirm"])

with tab_list:
    st.markdown("#### Step 1: Pick a list")
    names, name_col, sector_col, owner_col = choose_list()
    use_judge = False
    if not PUBLIC:
        use_judge = st.checkbox(
            "Send unclear names to Anthropic's AI to judge",
            help="Sends the name, industry and owner of unclear companies. Check your fund agreements first. Left off, nothing leaves "
            "this computer and you confirm unclear matches yourself.",
        )
        if use_judge and default_client() is None:
            st.warning(
                "This needs an Anthropic key in the .env file, so unclear names will come to you instead."
            )
    if names is not None and st.button("Check lender filings", type="primary"):
        engine.client = default_client() if use_judge else None
        st.session_state["results"] = run(
            engine, names, name_col, sector_col, owner_col
        )
    if st.session_state.get("results"):
        show_results(engine, st.session_state["results"])

with tab_review:
    show_review(engine, st.session_state.get("results") or [])
