from collections.abc import AsyncIterator

import asyncpg
from fastapi import Request

from app.config import Settings


async def create_pool(settings: Settings) -> asyncpg.Pool:
    # session pooler; statement_cache_size=0 so a later move to transaction
    # mode does not silently break prepared statements
    return await asyncpg.create_pool(
        settings.database_url, min_size=1, max_size=10, statement_cache_size=0
    )


async def tx(request: Request) -> AsyncIterator[asyncpg.pool.PoolConnectionProxy]:
    # pool.acquire() yields a PoolConnectionProxy, not asyncpg.Connection directly;
    # it proxies every Connection method/attribute at runtime (asyncpg's own design:
    # see asyncpg.pool.PoolConnectionProxy), so callers may still type it as
    # asyncpg.Connection -- that annotation is unchecked against this one because
    # FastAPI's Depends() return type is `Any`.
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as conn, conn.transaction():
        yield conn
