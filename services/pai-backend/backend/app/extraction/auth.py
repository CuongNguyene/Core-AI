from typing import cast
from uuid import UUID

from fastapi import Request

from app.authorization.repository import SubjectRepository
from app.authorization.schemas import ActorContext, Role
from app.authorization.service import DevelopmentIdentityAdapter
from app.shared.config import Settings
from app.shared.errors import APIError

DevelopmentActor = ActorContext


async def get_development_actor(request: Request) -> DevelopmentActor:
    settings = cast(Settings, request.app.state.settings)
    if settings.app_env != "development":
        raise APIError(
            403, "development_identity_unavailable", "Development identity is unavailable."
        )

    header_value = request.headers.get("X-PAI-Actor-ID")
    if not header_value:
        raise APIError(403, "development_identity_required", "Development identity is required.")
    try:
        actor_id = UUID(header_value)
    except ValueError as exc:
        raise APIError(
            401, "development_identity_invalid", "Development identity is invalid."
        ) from exc
    repository = getattr(request.app.state, "subject_repository", None)
    if repository is None:
        raise APIError(
            503, "development_identity_unavailable", "Development identity is unavailable."
        )
    try:
        return await DevelopmentIdentityAdapter(cast(SubjectRepository, repository)).resolve(
            actor_id
        )
    except PermissionError as exc:
        code = str(exc)
        status_code = 401 if code == "identity_unknown" else 403
        raise APIError(status_code, code, "Development identity is not authorized.") from exc


def require_reviewer(actor: DevelopmentActor) -> None:
    if Role.REVIEWER not in actor.roles:
        raise APIError(403, "reviewer_role_required", "Reviewer role is required.")
