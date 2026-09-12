from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import create_pool
from app.errors import register_handlers
from app.routers import health, profiles, shops, vehicles


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.pool = await create_pool(get_settings())
        yield
        await app.state.pool.close()

    app = FastAPI(title="torq-api", lifespan=lifespan)
    register_handlers(app)
    app.include_router(health.router)
    app.include_router(profiles.router)
    app.include_router(vehicles.router)
    app.include_router(shops.router)
    return app
