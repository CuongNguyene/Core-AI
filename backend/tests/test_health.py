import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import create_app


class AvailableDatabase:
    async def check_connection(self) -> bool:
        return True


class UnavailableDatabase:
    async def check_connection(self) -> bool:
        return False


def make_client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_legacy_health_endpoint_is_available() -> None:
    async with make_client(create_app()) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_live_health_does_not_depend_on_database() -> None:
    async with make_client(create_app()) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_health_returns_ready_when_database_is_available() -> None:
    app = create_app()
    app.state.database = AvailableDatabase()
    async with make_client(app) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_ready_health_returns_safe_error_when_database_is_unavailable() -> None:
    app = create_app()
    app.state.database = UnavailableDatabase()
    async with make_client(app) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_not_ready"
    assert response.json()["error"]["message"] == "Service is not ready."
