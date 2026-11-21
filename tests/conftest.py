"""Checks that hold across the whole test run."""

import hashlib
from pathlib import Path

SEED = Path(__file__).resolve().parents[1] / "data/public/decisions.sqlite"
_seed_hash: dict[str, str] = {}


def _hash() -> str:
    return hashlib.sha256(SEED.read_bytes()).hexdigest()


def pytest_sessionstart(session):
    _seed_hash["start"] = _hash()


def pytest_sessionfinish(session, exitstatus):
    """The committed seed of saved answers must never be changed by a run (spec check 7)."""
    if _hash() != _seed_hash["start"]:
        print(
            "\nFAILED: a test changed data/public/decisions.sqlite. Tests must work on a copy."
        )
        session.exitstatus = 1
