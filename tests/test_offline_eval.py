"""The offline eval gate passes on the real answer key and fails when 5% of labels are flipped."""

from __future__ import annotations

import subprocess
import sys

import pandas as pd

ANSWER_KEY = "data/eval/answer_key.csv"


def run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "eval.offline", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_gate_passes_on_current_data():
    r = run_gate()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


def test_gate_fails_with_five_percent_of_labels_flipped(tmp_path):
    key = pd.read_csv(ANSWER_KEY)
    decided = key.index[key.label != "unsure"]
    flip = key.loc[decided].sample(frac=0.05, random_state=17).index
    key.loc[flip, "label"] = key.loc[flip, "label"].map(
        {"match": "no_match", "no_match": "match"}
    )
    path = tmp_path / "answer_key_flipped.csv"
    key.to_csv(path, index=False)

    r = run_gate("--answer-key", str(path))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "FAIL" in r.stdout
