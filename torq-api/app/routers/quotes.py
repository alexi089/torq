from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from app.auth import CurrentUser, Shop, current_user, require_shop
from app.db import tx
from app.errors import conflict, invalid_state, not_found
from app.routers.requests import REQ_COLS, request_row

router = APIRouter(prefix="/v1")

QUOTE_COLS = (
    "id, request_id, shop_id, price_min_cents, price_max_cents, "
    "eta_minutes, message, status, created_at"
)


def quote_row(r: asyncpg.Record) -> dict:
    return {
        "id": r["id"],
        "request_id": r["request_id"],
        "shop_id": r["shop_id"],
        "price_min_cents": r["price_min_cents"],
        "price_max_cents": r["price_max_cents"],
        "eta_minutes": r["eta_minutes"],
        "message": r["message"],
        "status": r["status"],
        "created_at": r["created_at"].isoformat(),
    }


class QuoteCreate(BaseModel):
    price_min_cents: int = Field(ge=0)
    price_max_cents: int = Field(ge=0)
    eta_minutes: int = Field(gt=0)
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def max_gte_min(self) -> "QuoteCreate":
        if self.price_max_cents < self.price_min_cents:
            raise ValueError("price_max_cents must be >= price_min_cents")
        return self


@router.post("/requests/{request_id}/quotes", status_code=201)
async def create_quote(
    request_id: int,
    body: QuoteCreate,
    shop: Annotated[Shop, Depends(require_shop)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    # for share: blocks against a concurrent accept flipping status mid-insert,
    # without blocking other shops' concurrent quote inserts against each other.
    req = await conn.fetchrow(
        """
        select r.status,
               (r.expires_at is null or r.expires_at > now()) as not_expired,
               exists(select 1 from public.request_notifications rn
                      where rn.request_id = r.id and rn.shop_id = $2) as notified
        from public.requests r where r.id = $1 for share of r
        """,
        request_id,
        shop.id,
    )
    if req is None or not req["notified"]:
        raise not_found("request not found")
    if req["status"] != "open":
        raise invalid_state(f"request is {req['status']}")
    if not req["not_expired"]:
        raise invalid_state("request has expired")
    try:
        r = await conn.fetchrow(
            f"""
            insert into public.quotes
                (request_id, shop_id, price_min_cents, price_max_cents, eta_minutes, message)
            values ($1, $2, $3, $4, $5, $6)
            returning {QUOTE_COLS}
            """,
            request_id,
            shop.id,
            body.price_min_cents,
            body.price_max_cents,
            body.eta_minutes,
            body.message,
        )
    except asyncpg.UniqueViolationError:
        raise conflict("your shop already quoted this request") from None
    assert r is not None
    return quote_row(r)


@router.post("/quotes/{quote_id}/accept")
async def accept_quote(
    quote_id: int,
    user: Annotated[CurrentUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(tx)],
) -> dict:
    # Lock the REQUEST row (not the quote row): both accepts for sibling
    # quotes on the same request join through to, and lock, the same r.id, so
    # a concurrent accept blocks here until the first commits, then re-reads
    # the now-current status and loses the guard below -- exactly one winner.
    row = await conn.fetchrow(
        """
        select q.id as quote_id, q.status as quote_status, r.id as request_id,
               r.status as request_status
        from public.quotes q
        join public.requests r on r.id = q.request_id
        where q.id = $1 and r.driver_id = $2
        for update of r
        """,
        quote_id,
        user.id,
    )
    if row is None:
        raise not_found("quote not found")
    if row["request_status"] != "open" or row["quote_status"] != "pending":
        raise invalid_state("request is no longer open")

    # Belt-and-braces: re-state the guard on each write. Under the row lock
    # just taken, the state we read above cannot have changed, so these must
    # affect exactly the row we expect -- 0 is an invariant violation, not a
    # racing writer, and must not be silently swallowed.
    quote_updated = await conn.execute(
        "update public.quotes set status = 'accepted' where id = $1 and status = 'pending'",
        quote_id,
    )
    if quote_updated != "UPDATE 1":
        raise invalid_state("quote was not pending")

    await conn.execute(
        "update public.quotes set status = 'rejected' "
        "where request_id = $1 and id <> $2 and status = 'pending'",
        row["request_id"],
        quote_id,
    )

    req = await conn.fetchrow(
        f"""
        update public.requests set status = 'accepted', accepted_quote_id = $2
        where id = $1 and status = 'open'
        returning {REQ_COLS}
        """,
        row["request_id"],
        quote_id,
    )
    if req is None:
        raise invalid_state("request was not open")

    quote = await conn.fetchrow(f"select {QUOTE_COLS} from public.quotes where id = $1", quote_id)
    assert quote is not None
    return {**request_row(req), "accepted_quote": quote_row(quote)}
