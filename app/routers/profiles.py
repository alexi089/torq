from typing import Annotated

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, model_validator

from app.auth import CurrentUser, current_user
from app.config import get_settings
from app.db import tx
from app.errors import AppError, invalid_state

router = APIRouter(prefix="/v1")


class ProfilePatch(BaseModel):
    full_name: str | None = None
    phone: str | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "ProfilePatch":
        if self.full_name is None and self.phone is None:
            raise ValueError("provide at least one of full_name, phone")
        return self


@router.patch("/me")
async def patch_me(
    body: ProfilePatch,
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    row = await conn.fetchrow(
        """
        update public.profiles
        set full_name = coalesce($2, full_name),
            phone = coalesce($3, phone)
        where id = $1
        returning id, full_name, phone, created_at
        """,
        user.id,
        body.full_name,
        body.phone,
    )
    assert row is not None  # signup trigger guarantees the row
    return {
        "id": str(row["id"]),
        "full_name": row["full_name"],
        "phone": row["phone"],
        "created_at": row["created_at"].isoformat(),
    }


@router.delete("/me", status_code=204)
async def delete_me(
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> Response:
    blocked = await conn.fetchval(
        """
        select exists (
            select 1 from public.requests
            where driver_id = $1 and status in ('open', 'accepted')
        ) or exists (
            select 1
            from public.requests r
            join public.quotes q on q.id = r.accepted_quote_id
            join public.shops s on s.id = q.shop_id
            where s.owner_id = $1 and r.status = 'accepted'
        )
        """,
        user.id,
    )
    if blocked:
        raise invalid_state("finish or cancel active requests before deleting your account")

    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.supabase_url) as sb:
        resp = await sb.delete(
            f"/auth/v1/admin/users/{user.id}",
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
            },
        )
    if resp.status_code >= 400:
        raise AppError(502, "upstream_error", "account deletion failed; try again")
    return Response(status_code=204)
