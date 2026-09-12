from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings, parse_cors_origins
from app.db import create_pool
from app.errors import register_handlers
from app.routers import health, profiles, quotes, requests, reviews, shops, vehicles


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.pool = await create_pool(get_settings())
        yield
        await app.state.pool.close()

    app = FastAPI(title="torq-api", lifespan=lifespan)
    register_handlers(app)

    origins = parse_cors_origins(get_settings().cors_origins)
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,  # bearer tokens, not cookies
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    app.include_router(health.router)
    app.include_router(profiles.router)
    app.include_router(vehicles.router)
    app.include_router(shops.router)
    app.include_router(requests.router)
    app.include_router(quotes.router)
    app.include_router(reviews.router)
    return app
