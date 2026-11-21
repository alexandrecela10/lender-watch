"""Saved answers kept per person (specs/engine-in-excel-and-claude.md, section 3, checks 5, 6, 9 and 10)."""

import shutil
import sqlite3
import tempfile
import threading
from pathlib import Path

import pytest

from erm.api import Engine
from erm.store import JUDGE, PERSON, Store, pair_id

ROOT = Path(__file__).resolve().parents[1]


def test_one_persons_answer_is_theirs_alone(tmp_path):
    s = Store(tmp_path / "d.sqlite")
    shared = s.save("Orion Group", "orion services", "unsure", JUDGE)
    s.review(shared.pair_id, True, owner="A")
    assert s.get(shared.pair_id, "A").verdict == "match"
    assert s.get(shared.pair_id, "B").verdict == "unsure"
    assert [d.name for d in s.pending(owner="A")] == []
    assert [d.name for d in s.pending(owner="B")] == ["Orion Group"]


def test_automation_never_replaces_a_persons_answer(tmp_path):
    s = Store(tmp_path / "d.sqlite")
    s.save("Orion Group", "orion services", "no_match", PERSON, owner="A")
    kept = s.save("Orion Group", "orion services", "match", JUDGE, owner="A")
    assert (kept.verdict, kept.decided_by, kept.owner) == ("no_match", PERSON, "A")


def test_answers_survive_closing_and_reopening(tmp_path):
    path = tmp_path / "d.sqlite"
    Store(path).save("Orion Group", "orion services", "match", PERSON, owner="A")
    again = Store(path).get(pair_id("Orion Group", "orion services"), "A")
    assert (again.verdict, again.owner) == ("match", "A")


def test_an_old_store_keeps_every_answer_and_person_answers_become_local(tmp_path):
    path = tmp_path / "old.sqlite"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE decisions (pair_id TEXT PRIMARY KEY, name TEXT, mention_key TEXT, verdict TEXT,"
        " decided_by TEXT, reason TEXT, decided_at TEXT)"
    )
    db.executemany(
        "INSERT INTO decisions VALUES (?,?,?,?,?,?,?)",
        [
            ("p1", "A Co", "a co", "match", PERSON, "", "t"),
            ("p2", "B Co", "b co", "unsure", JUDGE, "", "t"),
        ],
    )
    db.commit()
    db.close()
    s = Store(path)
    assert (s.get("p1").owner, s.get("p1").verdict) == ("local", "match")
    assert (s.get("p2").owner, s.get("p2").verdict) == ("", "unsure")
    assert s.get("p1", "someone else") is None


def test_simultaneous_confirmations_all_land(tmp_path):
    s = Store(tmp_path / "d.sqlite", wal=True)
    errors = []

    def confirm(i):
        try:
            s.save(
                f"Company {i}", f"company {i}", "match", PERSON, owner=f"user{i % 3}"
            )
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=confirm, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert s.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 10


@pytest.fixture(scope="module")
def hosted_engine():
    folder = Path(tempfile.mkdtemp())
    shutil.copy(ROOT / "data/public/decisions.sqlite", folder / "d.sqlite")
    return Engine(
        holdings_path=str(ROOT / "data/public/holdings.parquet"),
        store_path=str(folder / "d.sqlite"),
        index_cache=str(Path(tempfile.gettempdir()) / "erm_index.pkl"),
        save_automated=False,
    )


def test_hosted_mode_keeps_no_list(hosted_engine):
    count = "SELECT COUNT(*) FROM decisions"
    before = hosted_engine.store.db.execute(count).fetchone()[0]
    out = hosted_engine.gather_facts("Foundation", owner="A")
    assert out["resolution"]["status"] == "needs_review"  # it had unclear names to save
    assert hosted_engine.store.db.execute(count).fetchone()[0] == before


def test_a_confirmation_changes_only_that_persons_result(hosted_engine):
    res = hosted_engine.resolve_entity("Foundation", owner="A")
    unsure = next(c for c in res.candidates if c.verdict == "unsure")
    hosted_engine.answer("Foundation", unsure.mention_key, True, owner="A")
    mine = hosted_engine.gather_facts("Foundation", owner="A")["resolution"]
    theirs = hosted_engine.gather_facts("Foundation", owner="B")["resolution"]
    assert any(
        c["mention_key"] == unsure.mention_key and c["verdict"] == "match"
        for c in mine["candidates"]
    )
    assert any(
        c["mention_key"] == unsure.mention_key and c["verdict"] == "unsure"
        for c in theirs["candidates"]
    )
