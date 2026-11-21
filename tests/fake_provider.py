"""A stand-in sign-in provider for tests: its own keys, tokens made on demand, no network."""

from __future__ import annotations

import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from erm.auth import AuthConfig

ISSUER = "https://auth.test"
BASE = "https://lw.test"
AUDIENCE = f"{BASE}/mcp"
INVITED = "user_invited"
EXCEL_CLIENT = "client_excel"

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def config(invited=(INVITED,)) -> AuthConfig:
    return AuthConfig(
        issuer=ISSUER,
        audiences=(AUDIENCE,),
        invited=frozenset(invited),
        authorize_url=f"{ISSUER}/oauth2/authorize",
        token_url=f"{ISSUER}/oauth2/token",
        jwks_url=f"{ISSUER}/oauth2/jwks",
        excel_client_id=EXCEL_CLIENT,
        key_for=lambda _token: _key.public_key(),
    )


def token(
    sub=INVITED, aud=AUDIENCE, iss=ISSUER, expires_in=600, wrong_key=False
) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": aud, "iss": iss, "iat": now, "exp": now + expires_in}
    return jwt.encode(claims, _other_key if wrong_key else _key, algorithm="RS256")


def bearer(**kw) -> dict:
    return {"Authorization": f"Bearer {token(**kw)}"}
