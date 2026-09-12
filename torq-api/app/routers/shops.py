from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from app.auth import CurrentUser, Shop, current_user, require_shop
from app.db import tx
from app.errors import conflict
from app.geo import Point

router = APIRouter(prefix="/v1")

COLS = """
    id, owner_id, name, phone, address,
    extensions.st_y(location::extensions.geometry) as lat,
    extensions.st_x(location::extensions.geometry) as lng,
    alert_radius_mi, is_online, rating_avg, rating_count, created_at
"""


def _row(r: asyncpg.Record) -> dict:
    return {
        "id": r["id"],
        "owner_id": str(r["owner_id"]),
        "name": r["name"],
        "phone": r["phone"],
        "address": r["address"],
        "location": {"lat": r["lat"], "lng": r["lng"]},
        "alert_radius_mi": r["alert_radius_mi"],
        "is_online": r["is_online"],
        "rating_avg": float(r["rating_avg"]) if r["rating_avg"] is not None else None,
        "rating_count": r["rating_count"],
        "created_at": r["created_at"].isoformat(),
    }


class ShopCreate(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    address: str = Field(min_length=1)
    location: Point
    alert_radius_mi: int = Field(ge=2, le=30)


class ShopPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    phone: str | None = Field(default=None, min_length=1)
    address: str | None = Field(default=None, min_length=1)
    location: Point | None = None
    alert_radius_mi: int | None = Field(default=None, ge=2, le=30)
    is_online: bool | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "ShopPatch":
        if not self.model_fields_set:
            raise ValueError("provide at least one field")
        return self


@router.post("/shops", status_code=201)
async def create_shop(
    body: ShopCreate,
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    try:
        r = await conn.fetchrow(
            f"""
            insert into public.shops (owner_id, name, phone, address, location, alert_radius_mi)
            values ($1, $2, $3, $4,
                    extensions.st_setsrid(
                        extensions.st_makepoint($6, $5), 4326
                    )::extensions.geography,
                    $7)
            returning {COLS}
            """,
            user.id,
            body.name,
            body.phone,
            body.address,
            body.location.lat,
            body.location.lng,
            body.alert_radius_mi,
        )
    except asyncpg.UniqueViolationError:
        raise conflict("you already have a shop") from None
    assert r is not None
    return _row(r)


@router.patch("/shops/me")
async def patch_my_shop(
    body: ShopPatch,
    shop: Annotated[Shop, Depends(require_shop)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    r = await conn.fetchrow(
        f"""
        update public.shops
        set name = coalesce($2, name),
            phone = coalesce($3, phone),
            address = coalesce($4, address),
            location = coalesce(
                case when $5::float8 is null then null
                     else extensions.st_setsrid(
                         extensions.st_makepoint($6, $5), 4326
                     )::extensions.geography
                end, location),
            alert_radius_mi = coalesce($7, alert_radius_mi),
            is_online = coalesce($8, is_online)
        where id = $1
        returning {COLS}
        """,
        shop.id,
        body.name,
        body.phone,
        body.address,
        body.location.lat if body.location else None,
        body.location.lng if body.location else None,
        body.alert_radius_mi,
        body.is_online,
    )
    assert r is not None
    return _row(r)
