import asyncpg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    pool: asyncpg.Pool = request.app.state.pool
    try:
        await pool.fetchval("select 1")
    except (asyncpg.PostgresError, OSError):
        return JSONResponse(status_code=503, content={"status": "unhealthy"})
    return JSONResponse(content={"status": "ok"})
