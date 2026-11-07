from eval.plan_drift import departures, planned_files

PLAN = """## Order

### I1. Core

Files: `erm/telemetry.py`, `tests/test_telemetry.py`.
Build it.

### I2. Cost

Files: `erm/api.py`.
"""


def test_planned_files_reads_only_its_step():
    assert planned_files(PLAN, "I1") == {"erm/telemetry.py", "tests/test_telemetry.py"}
    assert planned_files(PLAN, "I2") == {"erm/api.py"}


def test_departures_both_ways():
    extra, missing = departures(
        planned={"erm/telemetry.py", "tests/test_telemetry.py"},
        changed={"erm/telemetry.py", "erm/api.py", "plans/p-drift.md"},
        ignore={"plans/p-drift.md"},
    )
    assert extra == ["erm/api.py"]
    assert missing == ["tests/test_telemetry.py"]
