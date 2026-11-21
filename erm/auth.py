"""Sign-in checks for the hosted service. The provider signs people in; this module only checks its tokens.

A token passes when its signature, issuer, audience and expiry are right, and the person it names is on the invite
list. Nothing here logs a token, a code or an email.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt

ALGORITHMS = ("RS256", "ES256")


@dataclass(frozen=True)
class AuthConfig:
    issuer: str
    audiences: tuple[str, ...]
    invited: frozenset[str]
    authorize_url: str
    token_url: str
    jwks_url: str
    excel_client_id: str = ""
    # Tests pass a function that returns the public key for a token. Real use fetches the provider's public keys.
    key_for: Callable[[str], Any] | None = field(default=None, compare=False)

    @classmethod
    def from_env(cls, env=os.environ) -> AuthConfig | None:
        """None when no provider is set, which means local mode: no sign-in, this computer only."""
        issuer = env.get("LW_AUTH_ISSUER", "").rstrip("/")
        if not issuer:
            return None
        meta = discover(issuer)
        audiences = tuple(a for a in env.get("LW_AUTH_AUDIENCE", "").split(",") if a)
        if not audiences:
            raise SystemExit("LW_AUTH_AUDIENCE must be set when LW_AUTH_ISSUER is.")
        return cls(
            issuer=issuer,
            audiences=audiences,
            invited=frozenset(i for i in env.get("LW_INVITED", "").split(",") if i),
            authorize_url=meta["authorization_endpoint"],
            token_url=meta["token_endpoint"],
            jwks_url=meta["jwks_uri"],
            excel_client_id=env.get("LW_EXCEL_CLIENT_ID", ""),
        )


def discover(issuer: str) -> dict:
    """The provider's addresses, from its published metadata (RFC 8414, or OpenID as a fallback)."""
    for path in (
        "/.well-known/oauth-authorization-server",
        "/.well-known/openid-configuration",
    ):
        r = httpx.get(issuer + path, timeout=10)
        if r.status_code == 200:
            return r.json()
    raise SystemExit(f"Can't read the sign-in provider's metadata at {issuer}.")


@dataclass(frozen=True)
class Verdict:
    status: int  # 200 allowed, 401 not signed in, 403 signed in but not invited
    owner: str | None = None
    reason: str = ""


class Verifier:
    def __init__(self, config: AuthConfig):
        self.config = config
        self._jwks = (
            None
            if config.key_for
            else jwt.PyJWKClient(config.jwks_url, cache_keys=True)
        )

    def _key(self, token: str):
        if self.config.key_for:
            return self.config.key_for(token)
        return self._jwks.get_signing_key_from_jwt(token).key

    def check(self, authorization: str | None) -> Verdict:
        if not authorization or not authorization.startswith("Bearer "):
            return Verdict(401, reason="Sign in to use Lender Watch.")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            claims = jwt.decode(
                token,
                self._key(token),
                algorithms=list(ALGORITHMS),
                audience=list(self.config.audiences),
                issuer=self.config.issuer,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except (jwt.PyJWTError, httpx.HTTPError, ValueError):
            return Verdict(
                401, reason="Your sign-in isn't valid any more. Sign in again."
            )
        if claims["sub"] not in self.config.invited:
            return Verdict(
                403,
                owner=None,
                reason=(
                    "You're signed in, but not invited yet. Send this id to the person who invited you: "
                    + claims["sub"]
                ),
            )
        return Verdict(200, owner=claims["sub"])
