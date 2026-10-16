"""Application errors and the single response envelope (PRD §12.6).

Every error response has the same shape:

    {"error": {"code", "message", "request_id", "details"}}

`request_id` is always present (even for errors raised before the middleware
runs) and is echoed in the `X-Request-ID` response header so a report from a
user can be traced to a log line.
"""

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("sofia.errors")

UNKNOWN_REQUEST_ID = "unknown"


class SofiaError(Exception):
    """Application error carrying a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(SofiaError):
    def __init__(self, entity: str, identifier: str) -> None:
        super().__init__(
            "NOT_FOUND",
            f"{entity} not found: {identifier}",
            status_code=404,
            details={"entity": entity},
        )


class ValidationError(SofiaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("VALIDATION_ERROR", message, status_code=422, details=details)


class UnauthorizedError(SofiaError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__("UNAUTHORIZED", message, status_code=401)


class ForbiddenError(SofiaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("FORBIDDEN", message, status_code=403, details=details)


class ConflictError(SofiaError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("CONFLICT", message, status_code=409, details=details)


class ProviderError(SofiaError):
    def __init__(self, provider: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            "PROVIDER_ERROR",
            f"[{provider}] {message}",
            status_code=502,
            details={"provider": provider, **(details or {})},
        )


def request_id_of(request: Request) -> str:
    """Correlation id for the current request.

    Falls back to a sentinel rather than None so the envelope shape is stable
    even for errors raised before the middleware touches request.state.
    """
    return getattr(request.state, "request_id", None) or UNKNOWN_REQUEST_ID


def error_body(
    request: Request,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    *,
    status_code: int = 400,
) -> dict:
    from app.core.security import sanitize

    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id_of(request),
            # PRD §16: details are sanitized before leaving the process so a
            # stack trace or key can never ride along in an error response.
            "details": sanitize(details or {}),
            "status": status_code,
        }
    }


def error_response(
    request: Request,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    headers = {"X-Request-ID": request_id_of(request)}
    return JSONResponse(
        status_code=status_code,
        content=error_body(request, code, message, details, status_code=status_code),
        headers=headers,
    )


async def sofia_error_handler(request: Request, exc: SofiaError) -> JSONResponse:
    return error_response(request, exc.code, exc.message, exc.status_code, exc.details)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    errors = exc.errors() if hasattr(exc, "errors") else []
    # pydantic error payloads can contain the offending input, which may be a
    # secret the caller just submitted. Drop `input` and `ctx`.
    safe = [{k: v for k, v in e.items() if k not in ("input", "ctx")} for e in errors]
    return error_response(
        request,
        "VALIDATION_ERROR",
        "request validation failed",
        422,
        {"errors": safe},
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", None) or str(exc)
    code = {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "RATE_LIMITED",
    }.get(status_code, "HTTP_ERROR")
    if status_code < 500:
        return error_response(request, code, str(detail), status_code)
    return unhandled_error_handler(request, exc)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last resort handler.

    Must never raise: a crash inside this handler turns a 500 into a broken
    connection and hides the original failure.
    """
    try:
        log.exception(
            "unhandled error request_id=%s path=%s",
            request_id_of(request),
            getattr(request, "url", None),
            exc_info=exc,
        )
    except Exception:  # noqa: BLE001
        pass
    return error_response(request, "INTERNAL_ERROR", "Internal server error", 500, {})


def register_exception_handlers(app) -> None:  # noqa: ANN001
    """Install every handler so main.py stays declarative."""
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    app.add_exception_handler(SofiaError, sofia_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)