"""Analyst Desk: a workbook with an assistant beside it, running on the real engine.
Run: make desk, then open http://127.0.0.1:8765

Local only. It binds to this computer, and no company name leaves it unless the person turns Claude on in the panel.
It reads the public sample until data/holdings_clean.parquet exists. Saved answers go to a temporary copy for the sample.
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import ssl
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote

import anthropic
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.desk import assistant
from erm import assist, telemetry
from erm.api import (
    LATEST,
    LOAN_COLUMNS,
    Engine,
    default_client,
    loan_rows,
    summary_row,
    write_workbook,
)

log = logging.getLogger("erm.desk")

STATIC = Path(__file__).parent / "static"
EXCEL = Path(__file__).parent / "excel"
FULL_HOLDINGS = ROOT / "data" / "holdings_clean.parquet"
PUBLIC_HOLDINGS = ROOT / "data" / "public" / "holdings.parquet"
PUBLIC_DECISIONS = ROOT / "data" / "public" / "decisions.sqlite"
DEMO_LIST = ROOT / "data" / "demo" / "sample_list.csv"
HOST, PORT = "127.0.0.1", 8765
MAX_BODY = 20_000_000
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".json": "application/json",
    ".xml": "application/xml",
    ".png": "image/png",
}

# Public filing text for the sample workbook: the demo companies, and two similar names that are different companies.
TAPE_SEARCH = [
    "KnowBe4",
    "Apex Group Treasury",
    "Apex Service Partners",
    "dba Foundation Software",
    "Foundation Risk Partners",
    "LogRhythm",
    "Anaplan",
]
ROWS_PER_NAME = 3


def build_engine() -> Engine:
    """The full data if it exists; otherwise the public sample with a private copy of the saved answers."""
    if FULL_HOLDINGS.exists():
        return Engine(client=None)
    folder = Path(tempfile.mkdtemp())
    shutil.copy(PUBLIC_DECISIONS, folder / "decisions.sqlite")
    return Engine(
        holdings_path=str(PUBLIC_HOLDINGS),
        store_path=str(folder / "decisions.sqlite"),
        index_cache=str(Path(tempfile.gettempdir()) / "erm_index.pkl"),
        client=None,
    )


def demo_workbook(holdings: pd.DataFrame) -> dict[str, list[list]]:
    """Five public companies, and a tab of real filing rows that name them the way lenders do."""
    listed = pd.read_csv(DEMO_LIST).head(5)
    portfolio = [list(listed.columns), *listed.values.tolist()]
    latest = holdings[(holdings.period == LATEST) & (holdings.excluded_reason == "")]
    tape = [
        [
            "Lender",
            "Borrower (as filed)",
            "Amount owed ($)",
            "Value (% of amount owed)",
            "Filing",
        ]
    ]
    for term in TAPE_SEARCH:
        rows = latest[latest.raw_text.str.contains(term, regex=False)]
        rows = rows.sort_values("principal", ascending=False).head(ROWS_PER_NAME)
        tape += [
            [
                str(r.lender).title(),
                r.raw_text,
                float(r.principal),
                round(float(r.pct_par), 1),
                r.inlineurl,
            ]
            for r in rows.itertuples()
        ]
    return {"Portfolio": portfolio, "Lender tape": tape}


class Desk:
    """Every action the page can take. Takes and returns plain data, so tests need no browser."""

    def __init__(self, engine: Engine, client=None):
        self.engine = engine
        self.client = client

    def status(self, _payload: dict) -> dict:
        return {
            "claude_available": self.client is not None,
            "data": "full" if FULL_HOLDINGS.exists() else "public sample",
        }

    def workbook(self, _payload: dict) -> dict:
        return {
            "sheets": demo_workbook(self.engine.holdings),
            "name": "Portfolio review",
        }

    def inspect(self, payload: dict) -> dict:
        return assist.inspect_sheets(
            payload["sheets"], int(payload.get("failed_lookups", 0))
        )

    def _list_rows(self, sheets: dict, sheet: str | None) -> list[dict]:
        for candidate in [sheet, *sheets]:
            if candidate in sheets:
                rows = assist.list_from_sheet(sheets[candidate])
                if rows:
                    return rows
        return []

    def _reconcile(self, rows: list[dict]) -> dict:
        return assist.reconcile_list(self.engine, rows, source="desk")

    def reconcile(self, payload: dict) -> dict:
        known = {
            r["name"].casefold(): r
            for r in self._list_rows(payload["sheets"], payload.get("sheet"))
        }
        rows = [
            known.get(
                str(n).casefold(), {"name": str(n), "sector": None, "sponsor": None}
            )
            for n in payload["names"]
        ]
        return self._reconcile(rows)

    def answer(self, payload: dict) -> dict:
        """A person's answer on an unclear match, then that company worked out again."""
        name = payload["name"]
        with telemetry.run("desk_answer", judge_on=False):
            self.engine.answer(name, payload["mention_key"], bool(payload["same"]))
        result = self._reconcile([{"name": name, "sector": None, "sponsor": None}])
        return result["rows"][0]

    def ask(self, payload: dict) -> dict:
        ctx = {
            "sheets": payload["sheets"],
            "failed_lookups": int(payload.get("failed_lookups", 0)),
            "list_rows": self._list_rows(payload["sheets"], payload.get("sheet")),
            "reconcile": self._reconcile,
        }
        message = str(payload["message"])
        if payload.get("use_claude") and self.client is not None:
            try:
                reply = assistant.claude_reply(
                    self.client, message, payload.get("history", []), ctx
                )
            except anthropic.APIError as e:
                log.warning("assistant_error", extra={"error_type": type(e).__name__})
                reply = assistant.local_reply(message, ctx)
                reply["note"] = (
                    "Claude couldn't be reached, so this is the local answer."
                )
        else:
            reply = assistant.local_reply(message, ctx)
        if "reconciled" in ctx:
            reply["reconciled"] = ctx["reconciled"]
        return reply

    def open_file(self, data: bytes, filename: str) -> dict:
        sheets = assist.read_workbook(data, filename)
        return {
            "sheets": {k: _jsonable(v) for k, v in sheets.items()},
            "name": Path(filename).stem,
            "inspection": assist.inspect_sheets(sheets),
        }

    def export(self, payload: dict) -> bytes:
        """The sheet's names as a real workbook: their columns, lender columns, and one row per loan."""
        rows = self._list_rows(payload["sheets"], payload.get("sheet"))
        table, loans = [], []
        with telemetry.run("desk_export", judge_on=False):
            for row in rows:
                out = self.engine.gather_facts(
                    row["name"], {"sector": row["sector"], "sponsor": row["sponsor"]}
                )
                table.append(
                    {
                        "Company": row["name"],
                        "Owner": row["sponsor"],
                        "Sector": row["sector"],
                        **summary_row(out),
                    }
                )
                loans += loan_rows(row["name"], out)
        buffer = io.BytesIO()
        write_workbook(
            pd.DataFrame(table), pd.DataFrame(loans, columns=LOAN_COLUMNS), buffer
        )
        return buffer.getvalue()


def _jsonable(rows: list[list]) -> list[list]:
    return [
        [v if isinstance(v, int | float | type(None)) else str(v) for v in r]
        for r in rows
    ]


def make_handler(desk: Desk):
    class Handler(BaseHTTPRequestHandler):
        def log_message(
            self, *_args
        ):  # request lines can carry nothing useful and would bypass the JSON log
            return

        def _send(self, body: bytes, content_type: str, status: int = 200, extra=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, status: int = 200):
            self._send(
                json.dumps(data, default=str).encode(), "application/json", status
            )

        def _local_only(self) -> bool:
            """Refuse pages from other sites that try to reach this server by a made-up host name."""
            host = self.headers.get("Host", "").split(":")[0]
            if host in ("127.0.0.1", "localhost"):
                return True
            self._json({"error": "This desk only answers on this computer."}, 403)
            return False

        def do_GET(self):
            if not self._local_only():
                return
            path = unquote(self.path.split("?")[0])
            if path.startswith("/api/"):
                action = {
                    "/api/status": desk.status,
                    "/api/workbook": desk.workbook,
                }.get(path)
                return (
                    self._json(action({}))
                    if action
                    else self._json({"error": "Not found"}, 404)
                )
            root, relative = STATIC, path.lstrip("/") or "index.html"
            if path.startswith("/excel/"):
                root, relative = EXCEL, path.removeprefix("/excel/")
            target = (root / relative).resolve()
            if root.resolve() not in target.parents or not target.is_file():
                return self._json({"error": "Not found"}, 404)
            self._send(target.read_bytes(), TYPES.get(target.suffix, "text/plain"))

        def do_POST(self):
            if not self._local_only():
                return
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY:
                return self._json({"error": "That file is too large."}, 413)
            body = self.rfile.read(length)
            path = self.path.split("?")[0]
            try:
                if path == "/api/open":
                    return self._json(
                        desk.open_file(
                            body, unquote(self.headers.get("X-Filename", ""))
                        )
                    )
                payload = json.loads(body or b"{}")
                if path == "/api/export":
                    return self._send(
                        desk.export(payload),
                        XLSX,
                        extra={
                            "Content-Disposition": 'attachment; filename="reconciled.xlsx"'
                        },
                    )
                action = {
                    "/api/inspect": desk.inspect,
                    "/api/reconcile": desk.reconcile,
                    "/api/answer": desk.answer,
                    "/api/ask": desk.ask,
                }.get(path)
                if action is None:
                    return self._json({"error": "Not found"}, 404)
                self._json(action(payload))
            except (ValueError, KeyError, TypeError) as e:
                log.warning("desk_bad_request", extra={"error_type": type(e).__name__})
                self._json({"error": "That request couldn't be read."}, 400)

    return Handler


def tls_context(folder: Path) -> ssl.SSLContext:
    """HTTPS from Microsoft's development certificate. Installing and trusting it is the person's own step."""
    cert, key = folder / "localhost.crt", folder / "localhost.key"
    if not cert.exists() or not key.exists():
        raise SystemExit(
            f"No certificate in {folder}. Run: npx office-addin-dev-certs install"
        )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    return context


def main() -> None:
    telemetry.configure()
    client = default_client()
    desk = Desk(build_engine(), client)
    port = int(os.environ.get("ERM_DESK_PORT", PORT))
    server = HTTPServer((HOST, port), make_handler(desk))
    scheme = "http"
    if os.environ.get("ERM_DESK_TLS"):  # Excel only loads add-ins over HTTPS
        server.socket = tls_context(Path(os.environ["ERM_DESK_TLS"])).wrap_socket(
            server.socket, server_side=True
        )
        scheme = "https"
    logging.getLogger("erm.desk").info("desk_ready")
    print(
        f"Analyst Desk is ready: {scheme}://{HOST}:{port}", file=sys.stderr, flush=True
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
