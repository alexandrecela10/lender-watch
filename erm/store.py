"""Saved match decisions. A person's decision overrides everything and is never asked again.

Each person's answers are kept under their owner id and seen by nobody else. Automated answers have no owner
(owner "") and are shared. The command line, the review app and the evals use owner "local".
"""

from __future__ import annotations

import datetime as dt
import hashlib
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from erm.textparse import core

PERSON = "person"
JUDGE = "judge"
LOCAL = "local"
SHARED = ""


def pair_id(name: str, mention_key: str) -> str:
    return hashlib.sha1(f"{core(name)}|{mention_key}".encode()).hexdigest()[:12]


@dataclass(frozen=True)
class Decision:
    pair_id: str
    name: str
    mention_key: str
    verdict: str  # match, no_match or unsure
    decided_by: str  # person or judge
    reason: str
    decided_at: str
    owner: str = SHARED


COLUMNS = "pair_id, name, mention_key, verdict, decided_by, reason, decided_at, owner"
CREATE = """CREATE TABLE IF NOT EXISTS {table} (
    pair_id TEXT NOT NULL, name TEXT, mention_key TEXT, verdict TEXT,
    decided_by TEXT, reason TEXT, decided_at TEXT, owner TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (owner, pair_id))"""


class Store:
    def __init__(self, path: str | Path = "data/decisions.sqlite", wal: bool = False):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # One connection shared by every thread of a web server, so every use goes through one lock.
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        if wal:
            self.db.execute("PRAGMA journal_mode=WAL")
        with self.lock:
            self._upgrade()
            self.db.execute(CREATE.format(table="decisions"))
            self.db.execute(
                """CREATE TABLE IF NOT EXISTS aliases (
                    name_core TEXT, alias TEXT, source_url TEXT, PRIMARY KEY (name_core, alias))"""
            )
            self.db.commit()

    def _upgrade(self) -> None:
        """A store from before per-person answers is rebuilt in one transaction. Person answers become "local"."""
        cols = [r[1] for r in self.db.execute("PRAGMA table_info(decisions)")]
        if not cols or "owner" in cols:
            return
        with self.db:  # one transaction: all or nothing
            self.db.execute(CREATE.format(table="decisions_new"))
            self.db.execute(
                f"""INSERT INTO decisions_new ({COLUMNS})
                    SELECT pair_id, name, mention_key, verdict, decided_by, reason, decided_at,
                           CASE WHEN decided_by = ? THEN ? ELSE ? END
                    FROM decisions""",
                (PERSON, LOCAL, SHARED),
            )
            self.db.execute("DROP TABLE decisions")
            self.db.execute("ALTER TABLE decisions_new RENAME TO decisions")

    def add_alias(self, name: str, alias: str, source_url: str = "") -> None:
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO aliases VALUES (?,?,?)",
                (core(name), alias, source_url),
            )
            self.db.commit()

    def aliases(self, name: str) -> list[str]:
        with self.lock:
            return [
                r[0]
                for r in self.db.execute(
                    "SELECT alias FROM aliases WHERE name_core = ?", (core(name),)
                )
            ]

    def _row(self, pid: str, owner: str) -> Decision | None:
        row = self.db.execute(
            f"SELECT {COLUMNS} FROM decisions WHERE pair_id = ? AND owner = ?",
            (pid, owner),
        ).fetchone()
        return Decision(*row) if row else None

    def get(self, pid: str, owner: str = LOCAL) -> Decision | None:
        """This person's answer if they gave one, otherwise the shared automated answer."""
        with self.lock:
            return self._row(pid, owner) or self._row(pid, SHARED)

    def save(
        self,
        name: str,
        mention_key: str,
        verdict: str,
        decided_by: str,
        reason: str = "",
        owner: str = LOCAL,
    ) -> Decision:
        """A person's answer is kept under their owner id. An automated answer is shared and never replaces one."""
        if verdict not in {"match", "no_match", "unsure"}:
            raise ValueError(f"unknown verdict: {verdict}")
        pid = pair_id(name, mention_key)
        keep_under = owner if decided_by == PERSON else SHARED
        with self.lock:
            existing = self._row(pid, owner)
            if existing and existing.decided_by == PERSON and decided_by != PERSON:
                return existing  # automation can't overwrite a person
            now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
            d = Decision(
                pid, name, mention_key, verdict, decided_by, reason, now, keep_under
            )
            self.db.execute(
                f"INSERT OR REPLACE INTO decisions ({COLUMNS}) VALUES (?,?,?,?,?,?,?,?)",
                (
                    d.pair_id,
                    d.name,
                    d.mention_key,
                    d.verdict,
                    d.decided_by,
                    d.reason,
                    d.decided_at,
                    d.owner,
                ),
            )
            self.db.commit()
            return d

    def review(
        self, pid: str, accept: bool, reason: str = "", owner: str = LOCAL
    ) -> Decision:
        with self.lock:
            existing = self.get(pid, owner)
        if not existing:
            raise KeyError(f"no such pair: {pid}")
        return self.save(
            existing.name,
            existing.mention_key,
            "match" if accept else "no_match",
            PERSON,
            reason,
            owner,
        )

    def pending(
        self, names: set[str] | None = None, owner: str = LOCAL
    ) -> list[Decision]:
        """Open questions for one person: shared "unsure" answers they haven't answered themselves.
        Limited to a list of names when given, so one list's questions don't reach another's user."""
        with self.lock:
            rows = self.db.execute(
                f"""SELECT {COLUMNS} FROM decisions d
                    WHERE d.verdict = 'unsure' AND d.owner = ?
                      AND NOT EXISTS (SELECT 1 FROM decisions p
                                      WHERE p.pair_id = d.pair_id AND p.owner = ? AND p.decided_by = ?)
                    ORDER BY d.name""",
                (SHARED, owner, PERSON),
            ).fetchall()
        return [Decision(*r) for r in rows if names is None or r[1] in names]
