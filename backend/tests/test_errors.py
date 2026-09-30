from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.shared.errors import APIError


@pytest.mark.asyncio
async def test_response_generates_correlation_id() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert UUID(response.headers["X-Request-ID"])


@pytest.mark.asyncio
async def test_response_keeps_valid_client_correlation_id() -> None:
    app = create_app()
    correlation_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health/live", headers={"X-Request-ID": correlation_id})

    assert response.headers["X-Request-ID"] == correlation_id


@pytest.mark.asyncio
async def test_validation_error_does_not_echo_invalid_input() -> None:
    app: FastAPI = create_app()

    @app.get("/test-validation")
    async def test_validation(quantity: int) -> dict[str, int]:
        return {"quantity": quantity}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/test-validation", params={"quantity": "not-a-number"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_failed"
    assert response.json()["error"]["message"] == "Request validation failed."
    assert "not-a-number" not in response.text
    assert response.json()["error"]["correlation_id"] == response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_validation_error_uses_vietnamese_message_for_vi_locale() -> None:
    app: FastAPI = create_app()

    @app.get("/test-validation-vi")
    async def test_validation(quantity: int) -> dict[str, int]:
        return {"quantity": quantity}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/test-validation-vi",
            params={"quantity": "not-a-number"},
            headers={"Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_failed"
    assert response.json()["error"]["message"] == "Dữ liệu yêu cầu không hợp lệ."


@pytest.mark.asyncio
async def test_api_error_uses_vietnamese_catalog_and_keeps_code() -> None:
    app: FastAPI = create_app()

    @app.get("/test-api-error-vi")
    async def test_api_error() -> None:
        raise APIError(503, "capability_gap_unavailable", "Capability analysis is not ready.")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/test-api-error-vi", headers={"Accept-Language": "vi"}
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "capability_gap_unavailable"
    assert response.json()["error"]["message"] == "Phân tích khoảng cách năng lực chưa sẵn sàng."
