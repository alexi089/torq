from datetime import datetime
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth import CurrentUser, current_user
from app.db import tx
from app.errors import not_found

router = APIRouter(prefix="/v1")


def _max_year() -> int:
    return datetime.now().year + 1


class VehicleCreate(BaseModel):
    year: int = Field(ge=1900)
    make: str = Field(min_length=1)
    model: str = Field(min_length=1)
    engine: str | None = None
    mileage: int | None = Field(default=None, ge=0)

    @field_validator("year")
    @classmethod
    def year_not_future(cls, v: int) -> int:
        if v > _max_year():
            raise ValueError(f"year must be <= {_max_year()}")
        return v


class VehiclePatch(BaseModel):
    year: int | None = Field(default=None, ge=1900)
    make: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    engine: str | None = None
    mileage: int | None = Field(default=None, ge=0)

    @field_validator("year")
    @classmethod
    def year_not_future(cls, v: int | None) -> int | None:
        if v is not None and v > _max_year():
            raise ValueError(f"year must be <= {_max_year()}")
        return v

    @model_validator(mode="after")
    def at_least_one(self) -> "VehiclePatch":
        if not self.model_fields_set:
            raise ValueError("provide at least one field")
        return self


def _row(r: asyncpg.Record) -> dict:
    return {
        "id": r["id"],
        "owner_id": str(r["owner_id"]),
        "year": r["year"],
        "make": r["make"],
        "model": r["model"],
        "engine": r["engine"],
        "mileage": r["mileage"],
        "archived_at": r["archived_at"].isoformat() if r["archived_at"] else None,
        "created_at": r["created_at"].isoformat(),
    }


COLS = "id, owner_id, year, make, model, engine, mileage, archived_at, created_at"


@router.post("/vehicles", status_code=201)
async def create_vehicle(
    body: VehicleCreate,
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    r = await conn.fetchrow(
        f"""
        insert into public.vehicles (owner_id, year, make, model, engine, mileage)
        values ($1, $2, $3, $4, $5, $6)
        returning {COLS}
        """,
        user.id,
        body.year,
        body.make,
        body.model,
        body.engine,
        body.mileage,
    )
    assert r is not None
    return _row(r)


@router.patch("/vehicles/{vehicle_id}")
async def patch_vehicle(
    vehicle_id: int,
    body: VehiclePatch,
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    r = await conn.fetchrow(
        f"""
        update public.vehicles
        set year = coalesce($3, year),
            make = coalesce($4, make),
            model = coalesce($5, model),
            engine = coalesce($6, engine),
            mileage = coalesce($7, mileage)
        where id = $1 and owner_id = $2
        returning {COLS}
        """,
        vehicle_id,
        user.id,
        body.year,
        body.make,
        body.model,
        body.engine,
        body.mileage,
    )
    if r is None:
        raise not_found("vehicle not found")
    return _row(r)


@router.post("/vehicles/{vehicle_id}/archive")
async def archive_vehicle(
    vehicle_id: int,
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    r = await conn.fetchrow(
        f"""
        update public.vehicles
        set archived_at = coalesce(archived_at, now())
        where id = $1 and owner_id = $2
        returning {COLS}
        """,
        vehicle_id,
        user.id,
    )
    if r is None:
        raise not_found("vehicle not found")
    return _row(r)
