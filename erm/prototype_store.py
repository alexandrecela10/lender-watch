"""Events proposed from letters, and a person's answer on each (prototype). Only confirmed events change a measure."""

from __future__ import annotations

import datetime as dt
import sqlite3
import threading
import uuid
from pathlib import Path

PROPOSED, CONFIRMED, REJECTED = "proposed", "confirmed", "rejected"
COLUMNS = "event_id, letter, company_id, company, type, size_pct_cost, effective, received, quote, status, decided_at"


class EventStore:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock:
            self.db.execute(
                """CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY, letter TEXT, company_id TEXT, company TEXT, type TEXT,
                    size_pct_cost REAL, effective TEXT, received TEXT, quote TEXT, status TEXT, decided_at TEXT)"""
            )
            self.db.commit()

    def propose(self, letter: str, events: list[dict]) -> list[dict]:
        """Stores proposals from one letter. Each gets an id the person answers with."""
        out = []
        with self.lock:
            for e in events:
                row = {
                    "event_id": "P" + uuid.uuid4().hex[:8],
                    "letter": letter,
                    "company_id": e.get("company_id"),
                    "company": e["company"],
                    "type": e["type"],
                    "size_pct_cost": e.get("size_pct_cost"),
                    "effective": e["effective"],
                    "received": e["received"],
                    "quote": e["quote"],
                    "status": PROPOSED,
                    "decided_at": None,
                }
                self.db.execute(
                    f"INSERT INTO events ({COLUMNS}) VALUES ({','.join('?' * 11)})",
                    tuple(row.values()),
                )
                out.append(row)
            self.db.commit()
        return out

    def decide(self, event_id: str, yes: bool) -> dict:
        now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        with self.lock:
            if not self.db.execute(
                "SELECT 1 FROM events WHERE event_id = ?", (event_id,)
            ).fetchone():
                raise KeyError(f"No proposed event {event_id}.")
            self.db.execute(
                "UPDATE events SET status = ?, decided_at = ? WHERE event_id = ?",
                (CONFIRMED if yes else REJECTED, now, event_id),
            )
            self.db.commit()
            return self.get(event_id)

    def get(self, event_id: str) -> dict:
        with self.lock:
            row = self.db.execute(
                f"SELECT {COLUMNS} FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return dict(zip(COLUMNS.split(", "), row, strict=True))

    def confirmed_writedowns(self, company_id: str) -> list[dict]:
        """What measure 6 may use: write-downs a person confirmed, for one company."""
        with self.lock:
            rows = self.db.execute(
                "SELECT event_id, size_pct_cost, received FROM events WHERE company_id = ? AND type = 'write_down' AND status = ?",
                (company_id, CONFIRMED),
            ).fetchall()
        return [
            {"event_id": r[0], "size_pct_cost": r[1], "received": r[2]} for r in rows
        ]
