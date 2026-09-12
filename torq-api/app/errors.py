from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def unauthorized(message: str = "missing or invalid token") -> AppError:
    return AppError(401, "unauthorized", message)


def forbidden(message: str = "shop account required") -> AppError:
    return AppError(403, "forbidden", message)


def not_found(message: str) -> AppError:
    return AppError(404, "not_found", message)


def conflict(message: str) -> AppError:
    return AppError(409, "conflict", message)


def invalid_state(message: str) -> AppError:
    return AppError(409, "invalid_state", message)


def validation_error(message: str) -> AppError:
    return AppError(422, "validation_error", message)


def _envelope(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"] if p != "body")
        return _envelope(422, "validation_error", f"{loc}: {first['msg']}")
