from uuid import UUID, uuid4

import structlog
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.shared.i18n import localize_error_message, resolve_locale
from app.shared.schemas import ErrorDetail, ErrorResponse

REQUEST_ID_HEADER = "X-Request-ID"
logger = structlog.get_logger(__name__)


class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = _request_correlation_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = str(correlation_id)
        return response


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return _error_response(
        request, exc.status_code, exc.code, exc.message, details=exc.details
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return _error_response(
        request, exc.status_code, "http_error", "Request could not be completed."
    )


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(request, 422, "request_validation_failed", "Request validation failed.")


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_request_exception",
        correlation_id=str(correlation_id_for(request)),
        method=request.method,
        path=request.url.path,
        exc_info=True,
    )
    return _error_response(request, 500, "internal_server_error", "An unexpected error occurred.")


def correlation_id_for(request: Request) -> UUID:
    correlation_id = getattr(request.state, "correlation_id", None)
    if isinstance(correlation_id, UUID):
        return correlation_id
    return uuid4()


def _request_correlation_id(request_id: str | None) -> UUID:
    if request_id is None:
        return uuid4()
    try:
        return UUID(request_id)
    except ValueError:
        return uuid4()


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    localized_message = localize_error_message(
        code=code,
        message=message,
        locale=resolve_locale(request.headers.get("Accept-Language")),
    )
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=localized_message,
            correlation_id=correlation_id_for(request),
            details=details,
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))
