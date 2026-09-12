import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import asyncpg
import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.main import create_app

TABLES = (
    "public.reviews",
    "public.request_notifications",
    "public.quotes",
    "public.request_photos",
    "public.requests",
    "public.shops",
    "public.vehicles",
    "public.profiles",
)


@pytest.fixture(scope="session")
def supabase_url() -> str:
    return os.environ["SUPABASE_URL"]


@pytest.fixture(scope="session")
def service_key() -> str:
    return os.environ["SUPABASE_SERVICE_ROLE_KEY"]


@pytest.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(os.environ["DATABASE_URL"], statement_cache_size=0)
    yield conn
    await conn.close()


@pytest.fixture(autouse=True)
async def clean_db(db: asyncpg.Connection) -> None:
    # auth.users delete cascades profiles -> vehicles/shops; requests/reviews
    # anonymize (set null), so truncate the public tables explicitly too.
    await db.execute(f"truncate {', '.join(TABLES)} restart identity cascade")
    await db.execute("delete from auth.users")


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


UserFactory = Callable[..., Awaitable[dict[str, str]]]


@pytest.fixture
def make_user(supabase_url: str, service_key: str) -> UserFactory:
    async def _make(full_name: str = "Test Driver") -> dict[str, str]:
        email = f"{uuid.uuid4().hex}@torq.test"
        password = "torq-test-password-1"
        headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
        async with httpx.AsyncClient(base_url=supabase_url, headers=headers) as sb:
            created = await sb.post(
                "/auth/v1/admin/users",
                json={
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"full_name": full_name},
                },
            )
            created.raise_for_status()
            user_id = created.json()["id"]
            signin = await sb.post(
                "/auth/v1/token",
                params={"grant_type": "password"},
                json={"email": email, "password": password},
            )
            signin.raise_for_status()
            token = signin.json()["access_token"]
        return {"id": user_id, "email": email, "token": token}

    return _make
