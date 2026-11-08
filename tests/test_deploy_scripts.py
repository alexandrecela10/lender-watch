"""The deploy and rollback scripts, with a fake docker and curl first on the PATH. No real container starts."""

import os
import stat
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HEAD = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
).stdout.strip()

FAKE_DOCKER = r"""#!/usr/bin/env bash
# Records each call. $FAKE/running is the commit "running", $FAKE/images the commits built.
echo "$*" >> "$FAKE/calls"
case "$*" in
  *" up -d "*) echo "$ERM_PROD_TAG" > "$FAKE/running" ;;
  *" ps -q prod") [ -f "$FAKE/running" ] && echo container-id ;;
  "inspect -f {{.Config.Image}} container-id") echo "erm-review:$(cat "$FAKE/running")" ;;
  "image inspect "*) grep -qx "${3#erm-review:}" "$FAKE/images"; exit $? ;;
  build*) cat > /dev/null; for a in "$@"; do case "$a" in GIT_COMMIT=*) echo "${a#GIT_COMMIT=}" >> "$FAKE/images";; esac; done ;;
  run*) [ -f "$FAKE/key_in_image" ] && echo /app/.env ;;
esac
exit 0
"""

FAKE_CURL = r"""#!/usr/bin/env bash
# Fails when the running commit is listed in $FAKE/unhealthy.
! grep -qx "$(cat "$FAKE/running")" "$FAKE/unhealthy"
"""


@pytest.fixture
def env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {"docker": FAKE_DOCKER, "curl": FAKE_CURL}.items():
        path = bin_dir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    fake = tmp_path / "fake"
    fake.mkdir()
    for name in ("images", "unhealthy", "calls"):
        (fake / name).write_text("")
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FAKE": str(fake),
        "ERM_DEPLOY_DIR": str(tmp_path / "deploy"),
        "ERM_PROD_PROJECT": "erm-test",
        "ERM_PROD_PORT": "18999",
        "ERM_HEALTH_TRIES": "1",
        "ERM_HEALTH_DELAY": "0",
    }


def run(env, script, *args):
    return subprocess.run(
        [str(ROOT / "scripts" / script), *args],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )


def fake(env, name):
    return Path(env["FAKE"]) / name


def seed(env, *commits):
    """Pretend these commits were deployed in order, the last one running."""
    deploy = Path(env["ERM_DEPLOY_DIR"])
    deploy.mkdir(parents=True, exist_ok=True)
    (deploy / "good-images").write_text("".join(f"{c}\n" for c in commits))
    fake(env, "images").write_text("".join(f"{c}\n" for c in commits))
    fake(env, "running").write_text(f"{commits[-1]}\n")


def stack(env):
    return (Path(env["ERM_DEPLOY_DIR"]) / "good-images").read_text().split()


def approve(env, commit=HEAD, seconds=900):
    deploy = Path(env["ERM_DEPLOY_DIR"])
    deploy.mkdir(parents=True, exist_ok=True)
    (deploy / "prod-approval").write_text(
        f"commit={commit}\nexpires={int(time.time()) + seconds}\nby=test\n"
    )


def test_rollback_returns_to_previous_good_image(env):
    seed(env, "aaa", "bbb", "ccc")
    result = run(env, "rollback.sh")
    assert result.returncode == 0, result.stderr
    assert fake(env, "running").read_text().strip() == "bbb"
    assert stack(env) == ["aaa", "bbb"]


def test_two_rollbacks_go_two_steps_back(env):
    seed(env, "aaa", "bbb", "ccc")
    run(env, "rollback.sh")
    assert run(env, "rollback.sh").returncode == 0
    assert fake(env, "running").read_text().strip() == "aaa"


def test_rollback_refuses_with_no_earlier_image(env):
    seed(env, "aaa")
    result = run(env, "rollback.sh")
    assert result.returncode == 1
    assert "only good image" in result.stderr
    assert "up -d" not in fake(env, "calls").read_text()


def test_rollback_refuses_when_earlier_image_is_gone(env):
    seed(env, "aaa", "bbb")
    fake(env, "images").write_text("bbb\n")
    result = run(env, "rollback.sh")
    assert result.returncode == 1
    assert "not on this machine" in result.stderr
    assert fake(env, "running").read_text().strip() == "bbb"


def test_failed_rollback_restores_current_and_keeps_the_list(env):
    seed(env, "aaa", "bbb")
    fake(env, "unhealthy").write_text("aaa\n")
    result = run(env, "rollback.sh")
    assert result.returncode == 1
    assert fake(env, "running").read_text().strip() == "bbb"
    assert stack(env) == ["aaa", "bbb"]


def test_deploy_records_the_image_only_after_health_passes(env):
    seed(env, "aaa")
    assert run(env, "prod-deploy.sh", "HEAD").returncode == 0
    assert stack(env) == ["aaa", HEAD[:12]]


def test_failed_deploy_is_not_recorded_and_restores_current(env):
    seed(env, "aaa")
    fake(env, "unhealthy").write_text(f"{HEAD[:12]}\n")
    assert run(env, "prod-deploy.sh", "HEAD").returncode == 1
    assert stack(env) == ["aaa"]
    assert fake(env, "running").read_text().strip() == "aaa"


def test_deploy_stops_if_the_image_holds_a_key(env):
    seed(env, "aaa")
    fake(env, "key_in_image").write_text("1")
    assert run(env, "prod-deploy.sh", "HEAD").returncode != 0
    assert stack(env) == ["aaa"]
    assert " up -d " not in fake(env, "calls").read_text()


@pytest.mark.parametrize("script", ["prod-deploy.sh", "rollback.sh"])
def test_real_prod_refuses_without_approval(env, script):
    env["ERM_PROD_PROJECT"] = "erm"
    seed(env, "aaa", "bbb")
    result = run(env, script)
    assert result.returncode == 1
    assert "make approve-prod" in result.stderr
    assert fake(env, "calls").read_text() == ""


@pytest.mark.parametrize(
    "commit, seconds, reason",
    [("0" * 40, 900, "different commit"), (HEAD, -1, "expired")],
)
def test_real_prod_refuses_a_stale_approval(env, commit, seconds, reason):
    env["ERM_PROD_PROJECT"] = "erm"
    seed(env, "aaa", "bbb")
    approve(env, commit, seconds)
    result = run(env, "rollback.sh")
    assert result.returncode == 1
    assert reason in result.stderr


def test_approved_rollback_runs_and_uses_up_the_approval(env):
    env["ERM_PROD_PROJECT"] = "erm"
    seed(env, "aaa", "bbb")
    approve(env)
    assert run(env, "rollback.sh").returncode == 0
    assert not (Path(env["ERM_DEPLOY_DIR"]) / "prod-approval").exists()


def test_real_prod_deploys_only_the_approved_commit(env):
    env["ERM_PROD_PROJECT"] = "erm"
    approve(env)
    result = run(env, "prod-deploy.sh", "HEAD~1")
    assert result.returncode == 1
    assert "approved commit" in result.stderr


def test_rehearsal_cannot_use_the_real_prod_port(env):
    env["ERM_PROD_PORT"] = "8501"
    seed(env, "aaa", "bbb")
    result = run(env, "rollback.sh")
    assert result.returncode == 1
    assert "8501" in result.stderr
    assert fake(env, "calls").read_text() == ""


@pytest.mark.parametrize("script", ["prod-deploy.sh", "rollback.sh"])
def test_prod_refuses_a_compose_file_that_differs_from_the_commit(
    env, tmp_path, script
):
    """A copy of the repo's scripts in a throwaway git repo, so the real compose.yaml is never touched."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for f in (ROOT / "scripts").iterdir():
        if f.is_file():
            target = repo / "scripts" / f.name
            target.write_bytes(f.read_bytes())
            target.chmod(f.stat().st_mode)
    (repo / "compose.yaml").write_text("services: {}\n")
    git = [
        "git",
        "-C",
        str(repo),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
    ]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "base"], check=True)
    (repo / "compose.yaml").write_text("services: {prod: {env_file: .env}}\n")
    r = subprocess.run(
        [str(repo / "scripts" / script)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1 and "compose.yaml differs" in r.stderr
    assert " up -d " not in Path(env["FAKE"], "calls").read_text()
