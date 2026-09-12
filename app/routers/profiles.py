from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, model_validator

from app.auth import CurrentUser, current_user
from app.db import tx

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
