"""Saved match decisions. A person's decision overrides everything and is never asked again."""

from __future__ import annotations

import datetime as dt
import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from erm.textparse import core

PERSON = "person"
JUDGE = "judge"


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


class Store:
    def __init__(self, path: str | Path = "data/decisions.sqlite"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS decisions (
                pair_id TEXT PRIMARY KEY, name TEXT, mention_key TEXT, verdict TEXT,
                decided_by TEXT, reason TEXT, decided_at TEXT)"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS aliases (
                name_core TEXT, alias TEXT, source_url TEXT, PRIMARY KEY (name_core, alias))"""
        )
        self.db.commit()

    def add_alias(self, name: str, alias: str, source_url: str = "") -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO aliases VALUES (?,?,?)",
            (core(name), alias, source_url),
        )
        self.db.commit()

    def aliases(self, name: str) -> list[str]:
        return [
            r[0]
            for r in self.db.execute(
                "SELECT alias FROM aliases WHERE name_core = ?", (core(name),)
            )
        ]

    def get(self, pid: str) -> Decision | None:
        row = self.db.execute(
            "SELECT * FROM decisions WHERE pair_id = ?", (pid,)
        ).fetchone()
        return Decision(*row) if row else None

    def save(
        self,
        name: str,
        mention_key: str,
        verdict: str,
        decided_by: str,
        reason: str = "",
    ) -> Decision:
        if verdict not in {"match", "no_match", "unsure"}:
            raise ValueError(f"unknown verdict: {verdict}")
        pid = pair_id(name, mention_key)
        existing = self.get(pid)
        if existing and existing.decided_by == PERSON and decided_by != PERSON:
            return existing  # automation can't overwrite a person
        now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        self.db.execute(
            "INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?,?)",
            (pid, name, mention_key, verdict, decided_by, reason, now),
        )
        self.db.commit()
        return Decision(pid, name, mention_key, verdict, decided_by, reason, now)

    def review(self, pid: str, accept: bool, reason: str = "") -> Decision:
        existing = self.get(pid)
        if not existing:
            raise KeyError(f"no such pair: {pid}")
        return self.save(
            existing.name,
            existing.mention_key,
            "match" if accept else "no_match",
            PERSON,
            reason,
        )

    def pending(self, names: set[str] | None = None) -> list[Decision]:
        """Open questions, limited to a list of names when given, so one list's questions don't reach another's user."""
        rows = self.db.execute(
            "SELECT * FROM decisions WHERE verdict = 'unsure' ORDER BY name"
        ).fetchall()
        return [Decision(*r) for r in rows if names is None or r[1] in names]
