import uuid
from dataclasses import dataclass
from typing import Annotated

import asyncpg
import jwt
from fastapi import Depends, Request

from app.config import get_settings
from app.db import tx
from app.errors import forbidden, unauthorized

_jwks_client: jwt.PyJWKClient | None = None


def _jwks() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        url = get_settings().supabase_url + "/auth/v1/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(url, cache_keys=True, lifespan=300)
    return _jwks_client


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID


@dataclass(frozen=True)
class Shop:
    id: int
    owner_id: uuid.UUID


def _decode(token: str) -> dict:
    settings = get_settings()
    try:
        key = _jwks().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            key.key,
            algorithms=["ES256"],
            audience="authenticated",
            issuer=settings.supabase_url + "/auth/v1",
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except (jwt.PyJWKClientError, jwt.InvalidTokenError) as e:
        raise unauthorized() from e


async def current_user(request: Request) -> CurrentUser:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthorized()
    claims = _decode(token)
    try:
        user_id = uuid.UUID(claims["sub"])
    except ValueError as e:
        # PyJWT's built-in "sub" validation only requires it be present and a
        # string, not UUID-shaped -- a validly-signed token with a non-UUID
        # sub must still fail as an auth error, not surface as a 500.
        raise unauthorized() from e
    return CurrentUser(id=user_id)


async def require_shop(
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> Shop:
    row = await conn.fetchrow("select id, owner_id from public.shops where owner_id = $1", user.id)
    if row is None:
        raise forbidden()
    return Shop(id=row["id"], owner_id=row["owner_id"])
