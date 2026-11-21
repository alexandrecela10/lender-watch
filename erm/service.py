"""Lender Watch as one web service, for Claude and for the Excel add-in. Run: make service (local) or the hosted image.

Routes:
  /mcp                     Claude's connector. Sign-in required when hosted.
  /api/check, /api/confirm, /api/inspect   The Excel add-in's calls. Sign-in required when hosted.
  /api/status              Public: whether sign-in is needed and how, the quarters held, the data version.
  /excel/token             Public: passes the add-in's sign-in code to the provider, so the browser needs no
                           cross-site permission. Nothing about it is logged.
  /excel/*                 The add-in's files.
  /.well-known/oauth-protected-resource   Sign-in metadata for Claude.
  /health                  Health check.

Hosted mode (LW_AUTH_ISSUER set): public data only, no AI judge, no key, and nothing from a list is kept: only a
person's confirmation, under their own sign-in. Local mode: no sign-in, and it refuses to listen beyond 127.0.0.1.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from erm import assist, lender_tools, telemetry
from erm.api import Engine
from erm.auth import AuthConfig, Verifier
from erm.connectors.bdc import PROFILE
from erm.store import LOCAL, Store

ROOT = Path(__file__).resolve().parents[1]
EXCEL = ROOT / "app/desk/excel"
PUBLIC_HOLDINGS = ROOT / "data/public/holdings.parquet"
FULL_HOLDINGS = ROOT / "data/holdings_clean.parquet"
SEED = ROOT / "data/public/decisions.sqlite"
MAX_NAMES = 50
PROTECTED = ("/mcp", "/api/check", "/api/confirm", "/api/inspect")
LOCAL_HOSTS = ("127.0.0.1", "localhost")

log = logging.getLogger("erm.service")
_owner: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "owner", default=None
)


def current_owner() -> str:
    """The signed-in person for this request. Set by the sign-in check, never by the caller."""
    owner = _owner.get()
    if owner is None:
        raise PermissionError("No signed-in person for this request.")
    return owner


def build_engine(data_dir: Path, hosted: bool) -> Engine:
    """Hosted: public filings, saved answers on the persistent disk, nothing automated stored."""
    data_dir.mkdir(parents=True, exist_ok=True)
    store = data_dir / "decisions.sqlite"
    if not store.exists():
        shutil.copy(SEED, store)
    holdings = (
        PUBLIC_HOLDINGS if hosted or not FULL_HOLDINGS.exists() else FULL_HOLDINGS
    )
    engine = Engine(
        holdings_path=str(holdings),
        store_path=str(store),
        index_cache=str(data_dir / "index.pkl"),
        client=None,
        save_automated=not hosted,
    )
    engine.store = Store(store, wal=True)
    return engine


def create_app(
    auth: AuthConfig | None,
    base_url: str,
    data_dir: Path,
    engine: Engine | None = None,
    post_token=None,
) -> Starlette:
    """The whole service. `engine` and `post_token` are for tests."""
    hosted = auth is not None
    engine = engine or build_engine(data_dir, hosted)
    verifier = Verifier(auth) if hosted else None
    base_url = base_url.rstrip("/")
    resource = f"{base_url}/mcp"
    metadata_url = f"{base_url}/.well-known/oauth-protected-resource/mcp"

    mcp = MCPServer(lender_tools.SERVER_NAME)
    lender_tools.register(
        mcp,
        engine=lambda: engine,
        owner=current_owner,
        source="service_mcp",
        max_names=MAX_NAMES,
    )
    host = urlparse(base_url).netloc
    mcp_app = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[host, "127.0.0.1:*", "localhost:*", "testserver"]
        ),
    )

    async def health(_request: Request) -> Response:
        return JSONResponse({"ok": True})

    async def resource_metadata(_request: Request) -> Response:
        if not hosted:
            return JSONResponse(
                {"error": "Sign-in is off on this computer."}, status_code=404
            )
        return JSONResponse(
            {
                "resource": resource,
                "authorization_servers": [auth.issuer],
                "bearer_methods_supported": ["header"],
                "resource_name": "Lender Watch",
            }
        )

    async def status(_request: Request) -> Response:
        """Public: what the add-in needs before anyone signs in. No user data."""
        return JSONResponse(
            {
                "product": "Lender Watch",
                "mode": "hosted" if hosted else "local",
                "auth_required": hosted,
                "authorize_url": auth.authorize_url if hosted else None,
                "client_id": auth.excel_client_id if hosted else None,
                "resource": resource if hosted else None,
                "token_path": "/excel/token",
                "callback_path": "/excel/signin-callback.html",
                "quarters": engine.periods(),
                "data_version": engine.data_version,
                "max_names": MAX_NAMES,
                "claude_available": False,
            }
        )

    async def check(request: Request) -> Response:
        body = await request.json()
        companies = body.get("companies") or [
            {"name": str(n)} for n in body.get("names", [])
        ]
        try:
            out = assist.check_list(
                engine,
                companies,
                PROFILE,
                as_of=body.get("as_of"),
                owner=current_owner(),
                source="service_api",
                max_names=MAX_NAMES,
            )
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse(out)

    async def confirm(request: Request) -> Response:
        """A person's answer, then that company worked out again, so the panel can update its row."""
        body = await request.json()
        owner = current_owner()
        name = str(body["name"])
        with telemetry.run("service_api_answer", judge_on=False):
            engine.answer(
                name,
                str(body["mention_key"]),
                bool(body["same"]),
                str(body.get("reason", "")),
                owner=owner,
            )
        out = assist.check_list(
            engine,
            [{"name": name}],
            PROFILE,
            as_of=body.get("as_of"),
            owner=owner,
            source="service_api",
        )
        return JSONResponse(out["rows"][0])

    async def inspect(request: Request) -> Response:
        body = await request.json()
        return JSONResponse(
            assist.inspect_sheets(body["sheets"], int(body.get("failed_lookups", 0)))
        )

    async def token(request: Request) -> Response:
        """The add-in's sign-in code or refresh token, passed to the provider. Only the add-in's own client."""
        if not hosted:
            return JSONResponse(
                {"error": "Sign-in is off on this computer."}, status_code=404
            )
        form = dict(await request.form())
        if form.get("grant_type") not in ("authorization_code", "refresh_token"):
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
        if not auth.excel_client_id or form.get("client_id") != auth.excel_client_id:
            return JSONResponse({"error": "invalid_client"}, status_code=400)
        status_code, payload = await (post_token or _post_token)(auth.token_url, form)
        return JSONResponse(payload, status_code=status_code)

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with mcp_app.router.lifespan_context(mcp_app):
            log.info("service_ready", extra={"source": "hosted" if hosted else "local"})
            yield

    app = Starlette(
        routes=[
            Route("/health", health),
            Route("/.well-known/oauth-protected-resource", resource_metadata),
            Route("/.well-known/oauth-protected-resource/mcp", resource_metadata),
            Route("/api/status", status),
            Route("/api/check", check, methods=["POST"]),
            Route("/api/confirm", confirm, methods=["POST"]),
            Route("/api/inspect", inspect, methods=["POST"]),
            Route("/excel/token", token, methods=["POST"]),
            Mount("/excel", app=StaticFiles(directory=EXCEL, html=True)),
            Mount("/", app=mcp_app),
        ],
        lifespan=lifespan,
    )
    return RequestLog(SignIn(app, verifier, metadata_url))


class SignIn:
    """Checks the token on protected routes and puts the signed-in person on the request. Local mode: "local"."""

    def __init__(self, app, verifier: Verifier | None, metadata_url: str):
        self.app, self.verifier, self.metadata_url = app, verifier, metadata_url

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        if self.verifier is None:
            owner = LOCAL
        elif path.startswith(PROTECTED):
            headers = dict(scope["headers"])
            raw = headers.get(b"authorization")
            verdict = self.verifier.check(raw.decode("latin-1") if raw else None)
            if verdict.status != 200:
                extra = {}
                if verdict.status == 401:
                    extra["WWW-Authenticate"] = (
                        f'Bearer resource_metadata="{self.metadata_url}"'
                    )
                response = JSONResponse(
                    {"error": verdict.reason}, status_code=verdict.status, headers=extra
                )
                return await response(scope, receive, send)
            owner = verdict.owner
        else:
            owner = None
        token = _owner.set(owner)
        try:
            await self.app(scope, receive, send)
        finally:
            _owner.reset(token)


class RequestLog:
    """One JSON line per request: route, method, status, milliseconds. Never the query string, a body or a header."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        start, seen = time.monotonic(), {}

        async def record(message):
            if message["type"] == "http.response.start":
                seen["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, record)
        finally:
            log.info(
                "request",
                extra={
                    "route": scope["path"],
                    "method": scope["method"],
                    "status": seen.get("status", 500),
                    "duration_ms": round((time.monotonic() - start) * 1000),
                },
            )


async def _post_token(url: str, form: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, data=form, headers={"Accept": "application/json"})
    try:
        return r.status_code, r.json()
    except ValueError:
        return 502, {"error": "The sign-in provider gave an unreadable answer."}


def main() -> None:
    import uvicorn

    telemetry.configure()
    auth = AuthConfig.from_env()
    host = os.environ.get("LW_HOST", "127.0.0.1")
    port = int(os.environ.get("LW_PORT", "8770"))
    if auth is None and host not in LOCAL_HOSTS:
        raise SystemExit(
            f"Refusing to listen on {host} without sign-in. Set LW_AUTH_ISSUER, or use 127.0.0.1."
        )
    tls = os.environ.get(
        "LW_TLS_DIR"
    )  # Excel only loads add-ins over HTTPS, even on this computer
    scheme = "https" if tls else "http"
    base_url = os.environ.get("LW_BASE_URL", f"{scheme}://localhost:{port}")
    data_dir = Path(os.environ.get("LW_DATA_DIR", str(Path.home() / ".erm/service")))
    app = create_app(auth, base_url, data_dir)
    ssl = {}
    if tls and not (Path(tls) / "localhost.crt").exists():
        raise SystemExit(
            f"No certificate in {tls}. Run: npx office-addin-dev-certs install"
        )
    if tls:
        ssl = {
            "ssl_certfile": str(Path(tls) / "localhost.crt"),
            "ssl_keyfile": str(Path(tls) / "localhost.key"),
        }
    print(f"Lender Watch is ready: {base_url}", flush=True)
    uvicorn.run(app, host=host, port=port, access_log=False, log_config=None, **ssl)


if __name__ == "__main__":
    main()
