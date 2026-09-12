import re
from typing import Annotated, Literal

import asyncpg
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field, model_validator

from app.auth import CurrentUser, Shop, current_user, require_shop
from app.config import get_settings
from app.db import tx
from app.errors import invalid_state, not_found, validation_error
from app.geo import Point
from app.services.fanout import fan_out

router = APIRouter(prefix="/v1")

SLOTS = ("engine_bay", "dashboard", "wide")

REQ_COLS = """
    id, driver_id, vehicle_id, mode, issue, notes, location_hint,
    extensions.st_y(location::extensions.geometry) as lat,
    extensions.st_x(location::extensions.geometry) as lng,
    search_radius_mi, status, accepted_quote_id, created_at, expires_at
"""


def request_row(r: asyncpg.Record) -> dict:
    return {
        "id": r["id"],
        "driver_id": str(r["driver_id"]) if r["driver_id"] else None,
        "vehicle_id": r["vehicle_id"],
        "mode": r["mode"],
        "issue": r["issue"],
        "notes": r["notes"],
        "location_hint": r["location_hint"],
        "location": {"lat": r["lat"], "lng": r["lng"]},
        "search_radius_mi": r["search_radius_mi"],
        "status": r["status"],
        "accepted_quote_id": r["accepted_quote_id"],
        "created_at": r["created_at"].isoformat(),
        "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
    }


class PhotoIn(BaseModel):
    slot: Literal["engine_bay", "dashboard", "wide"]
    storage_path: str = Field(min_length=1)


class RequestCreate(BaseModel):
    vehicle_id: int
    mode: Literal["roadside", "planned"]
    issue: Literal["wont_start", "flat_tire", "battery", "brakes", "overheating", "other"]
    notes: str | None = None
    location_hint: str | None = None
    location: Point
    search_radius_mi: int = Field(ge=2, le=25)
    photos: list[PhotoIn]

    @model_validator(mode="after")
    def photos_cover_slots(self) -> "RequestCreate":
        if sorted(p.slot for p in self.photos) != sorted(SLOTS):
            raise ValueError("photos must have exactly three entries, one per slot")
        return self


def _validate_paths(photos: list[PhotoIn], sub: str) -> None:
    prefix = f"{sub}/"
    for p in photos:
        rest = p.storage_path.removeprefix(prefix)
        if (
            not p.storage_path.startswith(prefix)
            or not rest
            or re.search(r"(^|/)\.\.(/|$)", p.storage_path)
        ):
            raise validation_error("storage_path must be <your-uid>/<name>")


@router.post("/requests", status_code=201)
async def create_request(
    body: RequestCreate,
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    _validate_paths(body.photos, str(user.id))

    vehicle = await conn.fetchrow(
        "select id, archived_at from public.vehicles where id = $1 and owner_id = $2",
        body.vehicle_id,
        user.id,
    )
    if vehicle is None:
        raise not_found("vehicle not found")
    if vehicle["archived_at"] is not None:
        raise invalid_state("vehicle is archived")

    ttl = get_settings().roadside_ttl_minutes if body.mode == "roadside" else None
    r = await conn.fetchrow(
        f"""
        insert into public.requests
            (driver_id, vehicle_id, mode, issue, notes, location_hint, location,
             search_radius_mi, expires_at)
        values ($1, $2, $3::public.request_mode, $4::public.request_issue, $5, $6,
                extensions.st_setsrid(extensions.st_makepoint($8, $7), 4326)::extensions.geography,
                $9,
                case when $10::int is null then null
                     else now() + make_interval(mins => $10::int) end)
        returning {REQ_COLS}
        """,
        user.id,
        body.vehicle_id,
        body.mode,
        body.issue,
        body.notes,
        body.location_hint,
        body.location.lat,
        body.location.lng,
        body.search_radius_mi,
        ttl,
    )
    assert r is not None

    await conn.executemany(
        "insert into public.request_photos (request_id, storage_path, slot) "
        "values ($1, $2, $3::public.photo_slot)",
        [(r["id"], p.storage_path, p.slot) for p in body.photos],
    )
    notified = await fan_out(
        conn, r["id"], body.location.lat, body.location.lng, body.search_radius_mi
    )

    return {
        **request_row(r),
        "photos": [{"slot": p.slot, "storage_path": p.storage_path} for p in body.photos],
        "notified_count": notified,
    }


@router.post("/requests/{request_id}/cancel")
async def cancel_request(
    request_id: int,
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    existing = await conn.fetchrow(
        "select status from public.requests where id = $1 and driver_id = $2 for update",
        request_id,
        user.id,
    )
    if existing is None:
        raise not_found("request not found")
    if existing["status"] not in ("open", "accepted"):
        raise invalid_state(f"cannot cancel a {existing['status']} request")
    r = await conn.fetchrow(
        f"update public.requests set status = 'cancelled' where id = $1 returning {REQ_COLS}",
        request_id,
    )
    assert r is not None
    return request_row(r)


@router.post("/requests/{request_id}/seen", status_code=204)
async def mark_seen(
    request_id: int,
    shop: Annotated[Shop, Depends(require_shop)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> Response:
    updated = await conn.execute(
        """
        update public.request_notifications
        set seen_at = coalesce(seen_at, now())
        where request_id = $1 and shop_id = $2
        """,
        request_id,
        shop.id,
    )
    if updated == "UPDATE 0":
        raise not_found("request not found")
    return Response(status_code=204)
