import io
import json
import logging
import sqlite3
from types import SimpleNamespace

import anthropic
import httpx2 as httpx
import pytest

from erm import telemetry
from erm.api import call_judge
from erm.match.judge import cost_usd

log = logging.getLogger("erm.test")


@pytest.fixture
def lines():
    buf = io.StringIO()
    telemetry.configure(level="INFO", stream=buf)
    yield lambda: [json.loads(x) for x in buf.getvalue().splitlines()]
    telemetry.configure(level="INFO")


def rows(path):
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute("select * from run_metrics")]


def test_allowlist_drops_unknown_fields(lines, tmp_path):
    with telemetry.run("cli", metrics_path=tmp_path / "m.sqlite"):
        log.info(
            "judge_call",
            extra={
                "company": "Orion Group",
                "pair_id": "a1b2c3d4e5f6",
                "verdict": "match",
            },
        )
    out = lines()
    text = "\n".join(json.dumps(x) for x in out)
    assert "Orion Group" not in text
    assert "a1b2c3d4e5f6" not in text
    assert out[1]["verdict"] == "match"


def test_request_id_same_on_every_line_of_a_run(lines, tmp_path):
    for _ in range(2):
        with telemetry.run("cli", metrics_path=tmp_path / "m.sqlite"):
            log.info("judge_call")
    out = lines()
    assert [x["event"] for x in out] == [
        "run_started",
        "judge_call",
        "run_finished",
    ] * 2
    first, second = (
        {x["request_id"] for x in out[:3]},
        {x["request_id"] for x in out[3:]},
    )
    assert len(first) == 1 and len(second) == 1 and first != second
    assert None not in first


def test_metrics_write_row_matches_counts(lines, tmp_path):
    db = tmp_path / "m.sqlite"
    with telemetry.run("cli", metrics_path=db):
        telemetry.count("matched", "flagged")
        telemetry.count("needs_review", "worth_a_look")
        telemetry.count("not_found")
    [row] = rows(db)
    assert row["source"] == "cli" and row["status"] == "ok" and row["judge_on"] == 0
    assert (row["names_in"], row["names_matched"], row["names_needing_review"]) == (
        3,
        1,
        1,
    )
    assert (row["flagged"], row["worth_a_look"], row["judge_calls"]) == (1, 1, 0)
    assert lines()[-1]["names_in"] == 3


def test_metrics_write_records_error_and_reraises(lines, tmp_path):
    db = tmp_path / "m.sqlite"
    with pytest.raises(KeyError), telemetry.run("cli", metrics_path=db):
        raise KeyError("Orion Group")
    [row] = rows(db)
    assert row["status"] == "error"
    assert lines()[-1]["error_type"] == "KeyError"
    assert "Orion Group" not in json.dumps(lines())


def test_metrics_write_failure_never_fails_the_run(lines, tmp_path):
    bad = tmp_path / "is_a_folder"
    bad.mkdir()
    with telemetry.run("cli", metrics_path=bad) as stats:
        telemetry.count("matched")
    assert stats.names_in == 1
    events = [x["event"] for x in lines()]
    assert "metrics_write_failed" in events and events[-1] == "run_finished"


def test_count_outside_a_run_does_nothing():
    telemetry.count("matched")


# I2: judge cost and time, with a fake client. Nothing is sent anywhere.


def fake_client(model="claude-opus-5-5", error=None):
    def create(**kw):
        if error:
            raise error
        return SimpleNamespace(
            model=model,
            stop_reason="end_turn",
            content=[
                SimpleNamespace(
                    type="text",
                    text='{"verdict": "match", "reason": "Orion Group Holdings LLC"}',
                )
            ],
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=100,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
        )

    return SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=create))
    )


ARGS = (
    "Orion Group",
    "Software",
    "Example Capital",
    "Orion Group Holdings LLC",
    ["Orion Group Holdings LLC | First Lien"],
)


def test_judge_call_logs_verdict_tokens_cost_and_time(lines, tmp_path):
    db = tmp_path / "m.sqlite"
    with telemetry.run("cli", judge_on=True, metrics_path=db):
        assert call_judge(fake_client(), *ARGS).verdict == "match"
    out = lines()
    [call] = [x for x in out if x["event"] == "judge_call"]
    assert (
        call["verdict"] == "match"
        and call["input_tokens"] == 1000
        and call["output_tokens"] == 100
    )
    assert call["cost_usd"] == 0.006 and call["latency_ms"] >= 0
    assert "Orion" not in json.dumps(out) and "Example Capital" not in json.dumps(out)
    [row] = rows(db)
    assert (row["judge_calls"], row["judge_cost_usd"]) == (1, 0.006)


def test_judge_call_unknown_model_logs_null_cost(lines, tmp_path):
    db = tmp_path / "m.sqlite"
    with telemetry.run("cli", judge_on=True, metrics_path=db):
        call_judge(fake_client(model="some-fallback-model"), *ARGS)
    [call] = [x for x in lines() if x["event"] == "judge_call"]
    assert call["cost_usd"] is None
    assert rows(db)[0]["judge_cost_usd"] is None


def test_judge_call_error_is_logged_by_type_and_reraised(lines, tmp_path):
    err = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com")
    )
    with (
        pytest.raises(anthropic.APIError),
        telemetry.run("cli", judge_on=True, metrics_path=tmp_path / "m.sqlite"),
    ):
        call_judge(fake_client(error=err), *ARGS)
    [e] = [x for x in lines() if x["event"] == "judge_error"]
    assert e["error_type"] == "APIConnectionError"


def test_unknown_model_cost_is_none():
    assert cost_usd("unknown", SimpleNamespace(input_tokens=1, output_tokens=1)) is None
