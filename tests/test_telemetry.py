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


# I3: Langfuse traces. A fake Langfuse records what would be sent; nothing leaves the machine.
class FakeObservation:
    def __init__(self, sent):
        self.sent = sent

    def update(self, **kw):
        self.sent.append(("update", kw))

    def end(self):
        self.sent.append(("end", {}))


class FakeLangfuse:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def start_observation(self, **kw):
        if self.fail:
            raise ConnectionError("langfuse down")
        self.sent.append(("start", kw))
        return FakeObservation(self.sent)

    def flush(self):
        self.sent.append(("flush", {}))


@pytest.fixture
def fake_langfuse(monkeypatch):
    def install(fail=False):
        fake = FakeLangfuse(fail)
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-only")
        monkeypatch.setattr(telemetry, "_make_langfuse", lambda: fake)
        monkeypatch.setattr(telemetry, "_lf", None)
        monkeypatch.setattr(telemetry, "_lf_tried", False)
        return fake

    return install


def test_trace_payload_holds_no_names_or_ids(lines, tmp_path, fake_langfuse):
    from erm.store import pair_id

    fake = fake_langfuse()
    with telemetry.run("cli", judge_on=True, metrics_path=tmp_path / "m.sqlite"):
        call_judge(fake_client(), *ARGS)
    sent = json.dumps(fake.sent, default=str)
    for secret in [
        *ARGS[:4],
        ARGS[4][0],
        pair_id(ARGS[0], "orion group holdings"),
        "Orion",
        "Software",
    ]:
        assert secret not in sent
    [(_, start)] = [x for x in fake.sent if x[0] == "start"]
    assert start["input"] == {"has_sector": True, "has_owner": True, "n_examples": 1}
    [(_, upd)] = [x for x in fake.sent if x[0] == "update"]
    assert upd["output"] == {"verdict": "match", "stop_reason": "end_turn"}
    assert upd["cost_details"] == {"total": 0.006}
    assert ("flush", {}) in fake.sent


def test_trace_send_failed_leaves_the_verdict_unchanged(lines, tmp_path, fake_langfuse):
    fake_langfuse(fail=True)
    with telemetry.run("cli", judge_on=True, metrics_path=tmp_path / "m.sqlite"):
        assert call_judge(fake_client(), *ARGS).verdict == "match"
    events = [x["event"] for x in lines()]
    assert "trace_send_failed" in events and "judge_call" in events


def test_no_langfuse_when_judge_off_cli_and_mcp(monkeypatch, fake_langfuse):
    """With the judge off, the entry points build an Engine without a judge client, so no judge call and no Langfuse client."""
    import sys

    from erm import cli, mcp_server

    fake_langfuse()
    made = []
    monkeypatch.setattr(telemetry, "_make_langfuse", lambda: made.append(1))
    seen = []

    class Stop(Exception):
        pass

    def fake_engine(client=None, **kw):
        seen.append(client)
        raise Stop

    monkeypatch.setattr(cli, "Engine", fake_engine)
    monkeypatch.setattr(
        sys,
        "argv",
        ["erm", "enrich", "in.csv", "--name-column", "Company", "--out", "o.xlsx"],
    )
    with pytest.raises(Stop):
        cli.main()
    monkeypatch.delenv("ERM_USE_JUDGE", raising=False)
    monkeypatch.setattr(mcp_server, "Engine", fake_engine)
    monkeypatch.setattr(mcp_server, "_engine", None)
    with pytest.raises(Stop):
        mcp_server.engine()
    assert seen == [None, None] and made == []


def test_trace_payload_real_sdk_exports_only_our_fields(monkeypatch):
    """The installed Langfuse SDK, recording to memory. A span from another library, even one carrying a
    company name in a gen_ai attribute, must not be exported."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "local-only")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://127.0.0.1:9")
    exp = InMemorySpanExporter()
    lf = telemetry._make_langfuse(span_exporter=exp)
    with trace.get_tracer("some.other.library").start_as_current_span("chat") as other:
        other.set_attribute("gen_ai.prompt", "Is Orion Group the borrower?")
    obs = lf.start_observation(
        name="judge_call", as_type="generation", input={"n_examples": 1}
    )
    obs.update(output={"verdict": "match", "stop_reason": "end_turn"})
    obs.end()
    lf.flush()
    spans = exp.get_finished_spans()
    assert [s.name for s in spans] == ["judge_call"]
    assert "Orion" not in json.dumps(
        {k: str(v) for s in spans for k, v in s.attributes.items()}
    )
