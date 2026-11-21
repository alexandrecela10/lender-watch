"""Rebuild a saved-answers file for per-person answers, in one transaction, then compact it.

Run once on the committed seed: uv run python scripts/upgrade_store.py data/public/decisions.sqlite
Any other store upgrades itself the first time it's opened, so this script is only needed for files kept in git.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from erm.store import Store


def main(path: str) -> None:
    before = (
        sqlite3.connect(path).execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    )
    store = Store(path)
    after = store.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    store.db.execute("VACUUM")
    store.db.close()
    if before != after:
        raise SystemExit(f"Row count changed: {before} before, {after} after.")
    print(f"{path}: {after} answers kept, owner column added")


if __name__ == "__main__":
    main(sys.argv[1])
