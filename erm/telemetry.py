"""Run records: JSON logs with a request id, and one run_metrics row per run.

Spec: specs/instrumentation.md, sections 1 and 2. Library code only gets a
logger (`logging.getLogger("erm....")`); entry points call `configure()` once.
Nothing here ever logs a company name: the formatter writes allowlisted keys only.
"""

from __future__ import annotations

import contextvars
import datetime as dt
import json
import logging
import os
import sqlite3
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

# ERM_METRICS_PATH moves the file, for tests or a hosted app with another writable folder.
METRICS_PATH = "data/metrics.sqlite"

COUNTS = (
    "names_in",
    "names_matched",
    "names_needing_review",
    "flagged",
    "worth_a_look",
)

# Spec section 1. Anything else passed in `extra` is dropped, so a future
# extra={"name": ...} can never reach a log line. No name-derived id is listed.
ALLOWED = {
    "ts",
    "level",
    "event",
    "request_id",
    "session_id",
    "source",
    "judge_on",
    "status",
    "error_type",
    *COUNTS,
    "duration_ms",
    "latency_ms",
    "verdict",
    "decided_by",
    "model",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "cost_usd",
    "judge_calls",
    "judge_cost_usd",
}

log = logging.getLogger("erm.telemetry")

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "session_id", default=str(uuid.uuid4())
)
_source: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "source", default=None
)
_stats: contextvars.ContextVar[RunStats | None] = contextvars.ContextVar(
    "run_stats", default=None
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line, allowlisted keys only."""

    def format(self, record: logging.LogRecord) -> str:
        line = {
            "ts": dt.datetime.fromtimestamp(record.created, dt.UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": _request_id.get(),
            "session_id": _session_id.get(),
        }
        line.update(
            {k: v for k, v in record.__dict__.items() if k in ALLOWED and k not in line}
        )
        return json.dumps(line, default=str)


def configure(level: str | None = None, stream=None) -> None:
    """Send `erm` logs as JSON to stderr (never stdout: the MCP server talks on stdout)."""
    root = logging.getLogger("erm")
    for h in [h for h in root.handlers if getattr(h, "_erm", False)]:
        root.removeHandler(h)
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter())
    handler._erm = True
    root.addHandler(handler)
    root.setLevel(level or os.environ.get("ERM_LOG_LEVEL", "INFO"))
    root.propagate = False


def set_session(session_id: str) -> None:
    """One anonymous id per Streamlit session; CLI and MCP keep the per-process default."""
    _session_id.set(session_id)


@dataclass
class RunStats:
    names_in: int = 0
    names_matched: int = 0
    names_needing_review: int = 0
    flagged: int = 0
    worth_a_look: int = 0
    judge_calls: int = 0
    judge_cost_usd: float | None = 0.0


def count_result(out: dict) -> None:
    """Count one name from a gather_facts result."""
    count(out["resolution"]["status"], out["flags"]["level"] if out["facts"] else None)


def count(status: str, flag_level: str | None = None) -> None:
    """Add one name to the current run. Does nothing outside a run."""
    s = _stats.get()
    if s is None:
        return
    s.names_in += 1
    s.names_matched += status == "matched"
    s.names_needing_review += status == "needs_review"
    s.flagged += flag_level == "flagged"
    s.worth_a_look += flag_level == "worth_a_look"


def add_judge_call(cost: float | None) -> None:
    """Add one live judge call to the current run. One unpriced call makes the run's total unknown (None)."""
    s = _stats.get()
    if s is None:
        return
    s.judge_calls += 1
    s.judge_cost_usd = (
        None
        if cost is None or s.judge_cost_usd is None
        else round(s.judge_cost_usd + cost, 6)
    )


def write_metrics(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS run_metrics (request_id TEXT PRIMARY KEY, session_id TEXT,"
            " source TEXT, started_at TEXT, judge_on INTEGER, status TEXT, names_in INTEGER,"
            " names_matched INTEGER, names_needing_review INTEGER, flagged INTEGER,"
            " worth_a_look INTEGER, duration_ms INTEGER, judge_calls INTEGER, judge_cost_usd REAL)"
        )
        con.execute(
            f"INSERT INTO run_metrics ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
            list(row.values()),
        )


@contextmanager
def run(
    source: str, judge_on: bool = False, metrics_path: Path | None = None
) -> Iterator[RunStats]:
    """One run: a fresh request id for every log line inside, one run_metrics row on exit."""
    stats = RunStats()
    rid_token = _request_id.set(str(uuid.uuid4()))
    src_token = _source.set(source)
    stats_token = _stats.set(stats)
    started_at = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = time.monotonic()
    status, error_type = "ok", None
    log.info("run_started", extra={"source": source, "judge_on": judge_on})
    try:
        yield stats
    except BaseException as e:
        status, error_type = "error", type(e).__name__
        raise
    finally:
        row = {
            "request_id": _request_id.get(),
            "session_id": _session_id.get(),
            "source": source,
            "started_at": started_at,
            "judge_on": int(judge_on),
            "status": status,
            **{k: getattr(stats, k) for k in COUNTS},
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "judge_calls": stats.judge_calls,
            "judge_cost_usd": stats.judge_cost_usd,
        }
        try:
            write_metrics(
                Path(metrics_path or os.environ.get("ERM_METRICS_PATH", METRICS_PATH)),
                row,
            )
        except (sqlite3.Error, OSError) as e:
            log.warning("metrics_write_failed", extra={"error_type": type(e).__name__})
        fields = {
            k: v
            for k, v in row.items()
            if k not in ("request_id", "session_id", "started_at")
        }
        fields["judge_on"] = judge_on
        log.info("run_finished", extra={**fields, "error_type": error_type})
        flush_traces()
        _stats.reset(stats_token)
        _source.reset(src_token)
        _request_id.reset(rid_token)


# --- Langfuse traces on judge calls (spec section 3) ---------------------------------------------
# A client exists only after a live judge call asked for one (so only with the judge on) and only when
# both keys are set. It gets a private OpenTelemetry provider and exports Langfuse's own spans only,
# so spans from other libraries (for example an instrumented Anthropic SDK carrying prompts) never leave.
# Every trace field is set explicitly below; no decorator captures function arguments.

_lf = None
_lf_tried = False


def _make_langfuse(**kw):
    from langfuse import Langfuse
    from langfuse.span_filter import is_langfuse_span
    from opentelemetry.sdk.trace import TracerProvider

    return Langfuse(
        tracer_provider=TracerProvider(), should_export_span=is_langfuse_span, **kw
    )


def langfuse():
    """The Langfuse client, or None when either key is missing or it failed to start."""
    global _lf, _lf_tried
    if not _lf_tried:
        _lf_tried = True
        if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get(
            "LANGFUSE_SECRET_KEY"
        ):
            try:
                _lf = _make_langfuse()
            except Exception as e:  # noqa: BLE001 - tracing must never stop a run
                log.warning("trace_send_failed", extra={"error_type": type(e).__name__})
    return _lf


def start_judge_trace(
    has_sector: bool, has_owner: bool, n_examples: int, prompt_version: str
):
    """Open one generation for a judge call. Input is counts and flags only. Returns None when off or failing."""
    lf = langfuse()
    if lf is None:
        return None
    try:
        return lf.start_observation(
            name="judge_call",
            as_type="generation",
            input={
                "has_sector": has_sector,
                "has_owner": has_owner,
                "n_examples": n_examples,
            },
            metadata={
                "request_id": _request_id.get(),
                "source": _source.get(),
                "prompt_version": prompt_version,
            },
        )
    except Exception as e:  # noqa: BLE001
        log.warning("trace_send_failed", extra={"error_type": type(e).__name__})
        return None


def end_judge_trace(obs, **fields) -> None:
    """Close the generation with model, usage, cost and verdict, or with an error type."""
    if obs is None:
        return
    try:
        obs.update(**fields)
        obs.end()
    except Exception as e:  # noqa: BLE001
        log.warning("trace_send_failed", extra={"error_type": type(e).__name__})


def flush_traces() -> None:
    if _lf is None:
        return
    try:
        _lf.flush()
    except Exception as e:  # noqa: BLE001
        log.warning("trace_send_failed", extra={"error_type": type(e).__name__})
