"""The Excel add-in's files and workbook code, and the web connector's limits. Real Excel is not used here."""

import json
import re
import shutil
import ssl
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.desk import server

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


def test_the_formula_is_lw_check_with_an_optional_quarter():
    described = json.loads((ADDIN / "functions.json").read_text())["functions"]
    assert [f["id"] for f in described] == ["CHECK"]
    assert [p["name"] for p in described[0]["parameters"]] == ["names", "as_of"]
    assert described[0]["parameters"][1]["optional"] is True
    assert 'associate("CHECK"' in (ADDIN / "functions.js").read_text()
    assert 'DefaultValue="LW"' in (ADDIN / "manifest.xml").read_text()


def test_the_local_manifest_is_the_template_filled_in():
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_manifest

    assert (ADDIN / "manifest.xml").read_text() == make_manifest.render(
        "https://localhost:3000"
    )
    hosted = make_manifest.render("https://lw.example", "https://auth.example/oauth2")
    ET.fromstring(hosted.encode())
    assert "localhost" not in hosted
    assert "<AppDomain>https://auth.example</AppDomain>" in hosted
    with pytest.raises(SystemExit):
        make_manifest.render("http://lw.example")


def test_the_panel_has_no_claude_switch_and_never_calls_ask():
    text = (ADDIN / "taskpane.js").read_text() + (ADDIN / "taskpane.html").read_text()
    assert "/api/ask" not in text and "use-claude" not in text
    assert "/api/check" in (ADDIN / "api.js").read_text()


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
