from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import CurrentUser, current_user
from app.db import tx
from app.errors import conflict, invalid_state, not_found

router = APIRouter(prefix="/v1")

TagStr = Annotated[str, Field(min_length=1, max_length=40)]


class ReviewCreate(BaseModel):
    stars: int = Field(ge=1, le=5)
    tags: list[TagStr] = Field(default_factory=list, max_length=10)
    comment: str | None = None


@router.post("/requests/{request_id}/review", status_code=201)
async def create_review(
    request_id: int,
    body: ReviewCreate,
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    req = await conn.fetchrow(
        """
        select r.status, q.shop_id
        from public.requests r
        left join public.quotes q on q.id = r.accepted_quote_id
        where r.id = $1 and r.driver_id = $2
        """,
        request_id,
        user.id,
    )
    if req is None:
        raise not_found("request not found")
    if req["status"] != "completed" or req["shop_id"] is None:
        raise invalid_state("request is not completed")
    try:
        r = await conn.fetchrow(
            """
            insert into public.reviews (request_id, shop_id, driver_id, stars, tags, comment)
            values ($1, $2, $3, $4, $5, $6)
            returning id, request_id, shop_id, driver_id, stars, tags, comment, created_at
            """,
            request_id,
            req["shop_id"],
            user.id,
            body.stars,
            body.tags,
            body.comment,
        )
    except asyncpg.UniqueViolationError:
        raise conflict("this request is already reviewed") from None
    assert r is not None
    return {
        "id": r["id"],
        "request_id": r["request_id"],
        "shop_id": r["shop_id"],
        "driver_id": str(r["driver_id"]),
        "stars": r["stars"],
        "tags": list(r["tags"]),
        "comment": r["comment"],
        "created_at": r["created_at"].isoformat(),
    }
