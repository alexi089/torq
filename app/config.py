from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_service_role_key: str
    roadside_ttl_minutes: int = 120
    cors_origins: str = ""  # comma-separated origins for the web frontend; empty = no CORS headers


def parse_cors_origins(raw: str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]  # fields come from env
