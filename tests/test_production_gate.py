"""The production gate hook and the approval step. Nothing here runs docker or changes prod."""

import json
import os
import pty
import re
import select
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "production-gate.sh"
APPROVE = ROOT / "scripts" / "approve-prod.sh"
HEAD = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
).stdout.strip()

NEEDS_APPROVAL = [
    "make prod",
    "make rollback",
    "make prod-down",
    "make -C . rollback",
    "cd /tmp && make prod",
    "./scripts/prod-deploy.sh",
    "bash scripts/rollback.sh",
    "docker compose --profile prod up -d",
    "docker compose --profile=prod down",
    "docker-compose --profile prod restart",
    "docker compose up -d prod",
    "docker compose -p erm down",
    "COMPOSE_PROFILES=prod docker compose up -d",
    "ERM_PROD_TAG=abc docker compose --profile prod up -d",
    "docker stop erm-prod-1",
    "docker rm -f erm-prod-1",
    "docker run -d -p 8501:8501 erm-review:abc123",
    "docker rmi erm-review:abc123",
    "docker system prune -af",
    "bash -c 'make rollback'",
    'sh -c "docker compose --profile prod up -d"',
    'echo "$(make prod)"',
]

ALWAYS_BLOCKED = [
    "make approve-prod",
    "./scripts/approve-prod.sh",
    "script -q /dev/null make approve-prod",
    "printf x > ~/.erm/deploy/prod-approval",
    "rm ~/.erm/deploy/prod-approval",
    "bash -c 'make approve-prod'",
]

ALLOWED = [
    "make test",
    "make lint",
    "make dev",
    "make rehearse-rollback GOOD=aaa NEW=bbb",
    "docker compose --profile dev up --build",
    "docker compose --profile prod config --quiet",
    "docker build -t erm-review:dev .",
    "docker run --rm erm-review:dev true",
    'git commit -m "add make rollback and make approve-prod"',
    "git add scripts/approve-prod.sh scripts/rollback.sh",
    "grep -n approve-prod Makefile",
    "uv run pytest tests/test_production_gate.py",
    "brew install jq",
]


@pytest.fixture
def deploy(tmp_path):
    return tmp_path / "deploy"


def gate(deploy, tool, tool_input, path=None):
    return subprocess.run(
        ["/bin/bash", str(HOOK)],
        check=False,
        input=json.dumps({"tool_name": tool, "tool_input": tool_input}),
        env={
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(ROOT),
            "ERM_DEPLOY_DIR": str(deploy),
            "PATH": path or os.environ["PATH"],
        },
        capture_output=True,
        text=True,
    )


def bash(deploy, command):
    return gate(deploy, "Bash", {"command": command})


def approve(deploy, commit=HEAD, seconds=900):
    deploy.mkdir(parents=True, exist_ok=True)
    (deploy / "prod-approval").write_text(
        f"commit={commit}\nexpires={int(time.time()) + seconds}\nby=test\n"
    )


@pytest.mark.parametrize("command", NEEDS_APPROVAL)
def test_gate_blocks_production_change_without_approval(deploy, command):
    result = bash(deploy, command)
    assert result.returncode == 2, command
    assert "make approve-prod" in result.stderr


@pytest.mark.parametrize("command", NEEDS_APPROVAL)
def test_gate_allows_production_change_with_approval(deploy, command):
    approve(deploy)
    assert bash(deploy, command).returncode == 0, command


@pytest.mark.parametrize(
    "commit, seconds, reason",
    [("0" * 40, 900, "different commit"), (HEAD, -1, "expired")],
)
def test_gate_blocks_a_stale_approval(deploy, commit, seconds, reason):
    approve(deploy, commit, seconds)
    result = bash(deploy, "make rollback")
    assert result.returncode == 2
    assert reason in result.stderr


def test_gate_blocks_an_unreadable_approval(deploy):
    deploy.mkdir(parents=True)
    (deploy / "prod-approval").write_text("garbage\n")
    assert bash(deploy, "make prod").returncode == 2


@pytest.mark.parametrize("command", ALWAYS_BLOCKED)
def test_agents_can_never_approve_even_with_an_approval_on_file(deploy, command):
    approve(deploy)
    result = bash(deploy, command)
    assert result.returncode == 2, command
    assert "agents can't" in result.stderr


@pytest.mark.parametrize("command", ALLOWED)
def test_gate_allows_everything_else(deploy, command):
    assert bash(deploy, command).returncode == 0, command


@pytest.mark.parametrize(
    "file",
    [
        ".claude/hooks/production-gate.sh",
        ".claude/settings.json",
        "scripts/approve-prod.sh",
        "scripts/prod-lib.sh",
        "/Users/someone/.erm/deploy/prod-approval",
    ],
)
def test_edits_to_the_gate_are_blocked_even_with_approval(deploy, file):
    approve(deploy)
    path = file if file.startswith("/") else str(ROOT / file)
    assert gate(deploy, "Edit", {"file_path": path}).returncode == 2


@pytest.mark.parametrize("file", ["compose.yaml", "Dockerfile", "scripts/rollback.sh"])
def test_edits_to_prod_definition_need_approval(deploy, file):
    path = str(ROOT / file)
    assert gate(deploy, "Write", {"file_path": path}).returncode == 2
    approve(deploy)
    assert gate(deploy, "Write", {"file_path": path}).returncode == 0


def test_edits_elsewhere_pass(deploy):
    path = str(ROOT / "app" / "review.py")
    assert gate(deploy, "Edit", {"file_path": path}).returncode == 0


def test_gate_fails_closed_without_jq(deploy, tmp_path):
    bin_dir = tmp_path / "nojq"
    bin_dir.mkdir()
    for tool in ("cat", "grep", "date", "mkdir"):
        (bin_dir / tool).symlink_to(shutil.which(tool))
    result = gate(deploy, "Bash", {"command": "make rollback"}, path=str(bin_dir))
    assert result.returncode == 2
    assert "jq is not installed" in result.stderr


def test_gate_fails_closed_on_unreadable_input(deploy):
    result = subprocess.run(
        ["/bin/bash", str(HOOK)],
        check=False,
        input="not json make rollback",
        env={
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(ROOT),
            "ERM_DEPLOY_DIR": str(deploy),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2


def test_each_decision_is_logged_with_a_time_and_no_command_text(deploy):
    bash(deploy, "make rollback")
    log = (deploy / "gate.log").read_text()
    assert re.match(r"\d{4}-\d{2}-\d{2}T\S+Z block Bash", log)
    assert "make rollback" not in log


def clean_env(deploy):
    env = {**os.environ, "ERM_DEPLOY_DIR": str(deploy)}
    env.pop("CLAUDECODE", None)
    return env


def test_approval_step_refuses_without_a_terminal(deploy):
    result = subprocess.run(
        [str(APPROVE)],
        check=False,
        input="anything\n",
        env=clean_env(deploy),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "own terminal" in result.stderr
    assert not (deploy / "prod-approval").exists()


def approve_at_terminal(deploy, env, answer=None):
    """Runs the approval step on a real pseudo-terminal, typing the code it asks for."""
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        [str(APPROVE)],
        stdin=slave,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    os.close(slave)
    output = b""
    deadline = time.time() + 30
    while b"to approve:" not in output and time.time() < deadline:
        ready, _, _ = select.select([proc.stdout], [], [], 1)
        if ready:
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                break
            output += chunk
    match = re.search(rb"Type (\w+) to approve:", output)
    if match:
        os.write(master, (answer or match.group(1).decode()).encode() + b"\n")
    rest = proc.communicate(timeout=30)[0]
    os.close(master)
    return proc.returncode, (output + rest).decode()


def test_approval_step_inside_claude_code_refuses_even_at_a_terminal(deploy):
    env = {**clean_env(deploy), "CLAUDECODE": "1"}
    code, output = approve_at_terminal(deploy, env)
    assert code == 1
    assert "own terminal" in output
    assert not (deploy / "prod-approval").exists()


def test_approval_step_rejects_the_wrong_code(deploy):
    code, output = approve_at_terminal(deploy, clean_env(deploy), answer="wrong")
    assert code == 1
    assert "Not approved" in output
    assert not (deploy / "prod-approval").exists()


def test_a_person_at_a_terminal_opens_the_gate(deploy):
    assert bash(deploy, "make rollback").returncode == 2
    code, output = approve_at_terminal(deploy, clean_env(deploy))
    assert code == 0, output
    assert bash(deploy, "make rollback").returncode == 0
    assert (deploy / "prod-approval").stat().st_mode & 0o077 == 0


def approval_left(deploy):
    return (deploy / "prod-approval").exists()


@pytest.mark.parametrize(
    "command",
    [
        "make prod-down",
        "docker compose -p erm --profile prod down",
        "docker rm -f erm-prod-1",
    ],
)
def test_one_approval_covers_one_direct_change(deploy, command):
    approve(deploy)
    assert bash(deploy, command).returncode == 0
    assert not approval_left(deploy)
    assert bash(deploy, command).returncode == 2


def test_one_approval_covers_one_file_edit(deploy):
    approve(deploy)
    assert gate(deploy, "Edit", {"file_path": "compose.yaml"}).returncode == 0
    assert not approval_left(deploy)
    assert gate(deploy, "Edit", {"file_path": "compose.yaml"}).returncode == 2


@pytest.mark.parametrize(
    "command", ["make prod", "make rollback", "./scripts/prod-deploy.sh"]
)
def test_deploy_scripts_keep_the_approval_for_their_own_check(deploy, command):
    approve(deploy)
    assert bash(deploy, command).returncode == 0
    assert approval_left(deploy)


def test_a_script_joined_to_a_direct_change_uses_the_approval(deploy):
    approve(deploy)
    assert bash(deploy, "make prod; docker rm -f erm-prod-1").returncode == 0
    assert not approval_left(deploy)


@pytest.mark.parametrize(
    "command",
    [
        "rm .claude/hooks/production-gate.sh",
        "cd .claude/hooks && rm production-gate.sh",
        "sed -i '' s/a/b/ .claude/settings.json",
        "git checkout main -- .claude/settings.json",
        "git -C . restore .claude/hooks/production-gate.sh",
        "echo {} > .claude/settings.json",
        "echo {} | tee .claude/settings.local.json",
        "mv scripts/prod-lib.sh /tmp/x",
        "python3 -c \"open('.claude/settings.json','w')\"",
        "uv run python -c \"open('scripts/approve-prod.sh','w')\"",
    ],
)
def test_shell_commands_cannot_change_the_gate_even_with_approval(deploy, command):
    approve(deploy)
    assert bash(deploy, command).returncode == 2, command


@pytest.mark.parametrize(
    "command",
    [
        "cat .claude/settings.json",
        "grep -n prod .claude/hooks/production-gate.sh",
        "sed -n 1,5p scripts/prod-lib.sh",
        "git diff -- .claude/settings.json",
        "git log -- scripts/prod-lib.sh",
        'git commit -m "tidy production-gate.sh"',
        'gh pr create --body "changes settings.json wording"',
    ],
)
def test_reading_or_mentioning_the_gate_files_is_allowed(deploy, command):
    assert bash(deploy, command).returncode == 0, command
