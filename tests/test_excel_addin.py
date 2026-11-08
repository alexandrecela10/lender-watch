"""The Excel add-in's files and workbook code, and the web connector's limits. Real Excel is not used here."""

import json
import re
import shutil
import ssl
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.desk import server
from erm import mcp_remote

ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "app/desk/excel"


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_workbook_code_against_a_stand_in_for_excel():
    done = subprocess.run(
        ["node", str(ROOT / "tests/excel_addin_check.cjs")],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr


def test_every_file_the_manifest_names_exists():
    text = (ADDIN / "manifest.xml").read_text()
    ET.fromstring(text)  # well-formed
    urls = re.findall(r"https://localhost:3000/excel/([\w.-]+)", text)
    assert len(urls) > 5
    assert all((ADDIN / name).is_file() for name in urls)


def test_manifest_uses_one_shared_runtime_for_functions_and_panel():
    text = (ADDIN / "manifest.xml").read_text()
    assert '<Runtime resid="Taskpane.Url" lifetime="long" />' in text
    assert '<Set Name="SharedRuntime"' in text
    assert '<FunctionFile resid="Taskpane.Url" />' in text


def test_the_formula_is_registered_under_the_same_name_it_is_described():
    described = json.loads((ADDIN / "functions.json").read_text())["functions"]
    assert [f["id"] for f in described] == ["RECONCILE"]
    assert 'associate("RECONCILE"' in (ADDIN / "functions.js").read_text()
    assert 'DefaultValue="ERM"' in (ADDIN / "manifest.xml").read_text()


def test_tls_context_explains_a_missing_certificate(tmp_path):
    with pytest.raises(SystemExit, match="office-addin-dev-certs"):
        server.tls_context(tmp_path)


def test_tls_context_loads_a_certificate(tmp_path):
    if shutil.which("openssl") is None:
        pytest.skip("needs openssl")
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-keyout",
            str(tmp_path / "localhost.key"),
            "-out",
            str(tmp_path / "localhost.crt"),
        ],
        check=True,
        capture_output=True,
    )
    assert isinstance(server.tls_context(tmp_path), ssl.SSLContext)


def test_web_connector_has_no_tool_that_touches_files_or_saved_answers():
    names = {t.name for t in mcp_remote.mcp._tool_manager.list_tools()}
    assert names == {
        "inspect_sheets",
        "how_to_reconcile",
        "reconcile_list",
        "resolve_entity",
    }


def test_web_connector_refuses_an_oversized_list():
    with pytest.raises(ValueError):
        mcp_remote.reconcile_list([{"name": "x"}] * (mcp_remote.MAX_NAMES + 1))
