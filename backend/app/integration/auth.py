import secrets
from typing import cast

from fastapi import Request

from app.shared.config import Settings
from app.shared.errors import APIError


def verify_integration_api_key(request: Request) -> None:
    settings = cast(Settings, request.app.state.settings)
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    expected = settings.integration_api_key.get_secret_value()
    if scheme.lower() != "bearer" or not expected or not secrets.compare_digest(token, expected):
        raise APIError(401, "integration_authentication_failed", "Integration authentication failed.")
