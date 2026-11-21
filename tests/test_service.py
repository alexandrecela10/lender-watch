"""The hosted service: sign-in on every protected route, same rows for Excel and Claude, no names in logs.

Spec checks 1, 2, 4, 11 (hosted), 14 and 15. Uses a stand-in provider with its own keys. No network.
"""

import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from erm import service, telemetry
from erm.api import Engine
from tests import fake_provider as fp

ROOT = Path(__file__).resolve().parents[1]
DEMO = ["KnowBe4", "Exabeam", "Apex Group", "Foundation", "Not A Real Company Xyzzy"]
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
PROTECTED = ["/mcp", "/api/check", "/api/confirm", "/api/inspect"]


@pytest.fixture(scope="module")
def engine():
    folder = Path(tempfile.mkdtemp())
    shutil.copy(ROOT / "data/public/decisions.sqlite", folder / "d.sqlite")
    return Engine(
        holdings_path=str(ROOT / "data/public/holdings.parquet"),
        store_path=str(folder / "d.sqlite"),
        index_cache=str(Path(tempfile.gettempdir()) / "erm_index.pkl"),
        save_automated=False,
    )


@pytest.fixture(scope="module")
def client(engine):
    posted = []

    async def post_token(url, form):
        posted.append((url, form))
        return 200, {"access_token": "t", "refresh_token": "r"}

    app = service.create_app(
        fp.config(invited=(fp.INVITED, "user_b")),
        fp.BASE,
        Path(tempfile.mkdtemp()),
        engine=engine,
        post_token=post_token,
    )
    with TestClient(app, base_url="https://testserver") as c:
        c.posted = posted
        yield c


def mcp_call(client, tool, arguments, headers):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    r = client.post("/mcp", headers={**MCP_HEADERS, **headers}, json=body)
    return r


def mcp_result(r):
    result = r.json()["result"]
    assert not result.get("isError"), result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def test_excel_and_claude_get_identical_rows(client):
    companies = [{"name": n} for n in DEMO]
    via_api = client.post(
        "/api/check", json={"companies": companies}, headers=fp.bearer()
    ).json()
    via_mcp = mcp_result(
        mcp_call(client, "check_lenders", {"companies": companies}, fp.bearer())
    )
    assert via_api["rows"] == via_mcp["rows"]
    assert len(via_api["rows"]) == 5
    assert all(
        r["as_of"] == "2026-06-30" and r["rule_version"] == "flag-v1"
        for r in via_api["rows"]
    )


def test_two_identical_calls_give_identical_rows(client):
    body = {"names": DEMO, "as_of": "2026-03-31"}
    first = client.post("/api/check", json=body, headers=fp.bearer()).json()
    assert first == client.post("/api/check", json=body, headers=fp.bearer()).json()
    assert first["as_of"] == "2026-03-31"


def test_unknown_quarter_names_the_quarters_held(client):
    r = client.post(
        "/api/check",
        json={"names": ["KnowBe4"], "as_of": "2020-12-31"},
        headers=fp.bearer(),
    )
    assert r.status_code == 400 and "2026-03-31, 2026-06-30" in r.json()["error"]


@pytest.mark.parametrize("path", PROTECTED)
def test_no_token_gets_401_pointing_at_the_metadata(client, path):
    r = client.post(path, json={})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == (
        f'Bearer resource_metadata="{fp.BASE}/.well-known/oauth-protected-resource/mcp"'
    )


@pytest.mark.parametrize("path", PROTECTED)
@pytest.mark.parametrize(
    "bad",
    [
        {"wrong_key": True},
        {"aud": "https://elsewhere.test/mcp"},
        {"iss": "https://evil.test"},
        {"expires_in": -60},
    ],
    ids=["bad signature", "wrong audience", "wrong issuer", "expired"],
)
def test_bad_tokens_get_401(client, path, bad):
    assert client.post(path, json={}, headers=fp.bearer(**bad)).status_code == 401


@pytest.mark.parametrize("path", PROTECTED)
def test_signed_in_but_not_invited_gets_403(client, path):
    r = client.post(path, json={}, headers=fp.bearer(sub="user_stranger"))
    assert r.status_code == 403 and "user_stranger" in r.json()["error"]


def test_metadata_and_status_need_no_sign_in_and_hold_no_user_data(client):
    meta = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert meta["resource"] == fp.AUDIENCE and meta["authorization_servers"] == [
        fp.ISSUER
    ]
    status = client.get("/api/status").json()
    assert status["auth_required"] is True and status["client_id"] == fp.EXCEL_CLIENT
    assert status["quarters"] == ["2026-03-31", "2026-06-30"]
    assert status["claude_available"] is False
    assert client.get("/health").json() == {"ok": True}


def test_hosted_tool_list_is_exactly_two(client):
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    r = client.post("/mcp", headers={**MCP_HEADERS, **fp.bearer()}, json=body)
    assert sorted(t["name"] for t in r.json()["result"]["tools"]) == [
        "check_lenders",
        "confirm_match",
    ]


def test_a_confirmation_is_kept_for_that_person_only(client):
    row = client.post(
        "/api/check", json={"names": ["Apex Group"]}, headers=fp.bearer()
    ).json()["rows"][0]
    item = row["to_confirm"][0]
    body = {"name": "Apex Group", "mention_key": item["mention_key"], "same": False}
    updated = client.post("/api/confirm", json=body, headers=fp.bearer()).json()
    assert all(x["mention_key"] != item["mention_key"] for x in updated["to_confirm"])
    # Same person through Claude: the answer holds. Someone else invited: still asked.
    again = mcp_result(
        mcp_call(
            client,
            "check_lenders",
            {"companies": [{"name": "Apex Group"}]},
            fp.bearer(),
        )
    )
    assert all(
        x["mention_key"] != item["mention_key"] for x in again["rows"][0]["to_confirm"]
    )
    theirs = client.post(
        "/api/check", json={"names": ["Apex Group"]}, headers=fp.bearer(sub="user_b")
    ).json()
    assert any(
        x["mention_key"] == item["mention_key"] for x in theirs["rows"][0]["to_confirm"]
    )


def test_more_than_fifty_names_is_refused(client):
    r = client.post("/api/check", json={"names": ["x"] * 51}, headers=fp.bearer())
    assert r.status_code == 400 and "50" in r.json()["error"]


def test_token_route_passes_only_the_add_ins_own_codes(client):
    ok = {
        "grant_type": "authorization_code",
        "client_id": fp.EXCEL_CLIENT,
        "code": "c",
        "code_verifier": "v",
    }
    assert client.post("/excel/token", data=ok).status_code == 200
    assert client.posted[-1][0] == f"{fp.ISSUER}/oauth2/token"
    assert (
        client.post(
            "/excel/token", data={**ok, "client_id": "someone_else"}
        ).status_code
        == 400
    )
    assert (
        client.post("/excel/token", data={**ok, "grant_type": "password"}).status_code
        == 400
    )


def test_logs_hold_no_company_name_code_or_token(engine):
    stream = io.StringIO()
    telemetry.configure(stream=stream)
    try:

        async def post_token(url, form):
            return 200, {
                "access_token": "secret-access",
                "refresh_token": "secret-refresh",
            }

        app = service.create_app(
            fp.config(),
            fp.BASE,
            Path(tempfile.mkdtemp()),
            engine=engine,
            post_token=post_token,
        )
        bearer = fp.bearer()
        with TestClient(app, base_url="https://testserver") as c:
            c.get("/excel/signin-callback.html?code=one-time-code-123&state=state-456")
            c.post(
                "/excel/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": fp.EXCEL_CLIENT,
                    "code": "one-time-code-123",
                },
            )
            c.post("/api/check", json={"names": ["KnowBe4", "Exabeam"]}, headers=bearer)
            mcp_call(
                c, "check_lenders", {"companies": [{"name": "Apex Group"}]}, bearer
            )
    finally:
        telemetry.configure()
    text = stream.getvalue()
    lines = [json.loads(x) for x in text.splitlines()]
    assert any(
        x["event"] == "request" and x.get("route") == "/api/check" for x in lines
    )
    for secret in [
        "KnowBe4",
        "Exabeam",
        "Apex",
        "one-time-code-123",
        "state-456",
        "secret-access",
        bearer["Authorization"][7:],
    ]:
        assert secret not in text, secret


def test_local_mode_has_no_sign_in_and_answers_are_local(engine):
    app = service.create_app(
        None, "http://localhost:8770", Path(tempfile.mkdtemp()), engine=engine
    )
    with TestClient(app) as c:
        assert c.get("/api/status").json()["auth_required"] is False
        assert c.post("/api/check", json={"names": ["KnowBe4"]}).status_code == 200
        assert c.get("/.well-known/oauth-protected-resource").status_code == 404


def test_local_mode_refuses_to_listen_beyond_this_computer():
    env = {"LW_HOST": "0.0.0.0", "PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
    r = subprocess.run(
        [sys.executable, "-m", "erm.service"],
        check=False,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert (
        r.returncode != 0
        and "Refusing to listen on 0.0.0.0 without sign-in" in r.stderr
    )
