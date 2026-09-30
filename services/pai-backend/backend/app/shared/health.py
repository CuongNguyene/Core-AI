from typing import Protocol, cast

from fastapi import APIRouter, Request

from app.shared.errors import APIError
from app.shared.schemas import ErrorResponse, HealthResponse

router = APIRouter(tags=["health"])


class ReadinessDatabase(Protocol):
    async def check_connection(self) -> bool: ...


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/live", response_model=HealthResponse)
async def live_health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse}},
)
async def ready_health(request: Request) -> HealthResponse:
    database = cast(ReadinessDatabase, request.app.state.database)
    if not await database.check_connection():
        raise APIError(503, "service_not_ready", "Service is not ready.")
    return HealthResponse(status="ready")
