from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.authorization.schemas import ActorContext
from app.credential.schemas import Credential, CredentialRequest, CredentialVerification
from app.credential.service import CredentialService
from app.extraction.auth import get_development_actor
from app.shared.errors import APIError

router = APIRouter(tags=["credentials"])


class CredentialRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    source_reference_id: str | None = Field(default=None, max_length=512)
    correlation_id: UUID


class CredentialTransitionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_version: int = Field(ge=1)


def _service(request: Request) -> CredentialService:
    service = getattr(request.app.state, "credential_service", None)
    if service is None:
        raise APIError(503, "credential_service_unavailable", "Credential service is not ready.")
    return cast(CredentialService, service)


@router.post(
    "/credential-requests", response_model=CredentialRequest, status_code=status.HTTP_201_CREATED
)
async def create_request(
    body: CredentialRequestBody,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> CredentialRequest:
    try:
        return await _service(request).evaluate_and_request(
            actor=actor,
            policy_id=body.policy_id,
            policy_version=body.policy_version,
            source_reference_id=body.source_reference_id,
            correlation_id=body.correlation_id,
        )
    except PermissionError as exc:
        raise APIError(403, str(exc), "Credential request is not authorized.") from exc
    except ValueError as exc:
        raise APIError(422, str(exc), "Credential request cannot be evaluated.") from exc


@router.get("/credential-requests/{request_id}", response_model=CredentialRequest)
async def get_request(
    request_id: UUID,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> CredentialRequest:
    item = await _service(request)._require_request(request_id)
    if item.subject_id != actor.actor_id and item.organization_id != actor.organization_id:
        raise APIError(403, "credential_access_denied", "Credential access is denied.")
    return item


async def _transition(
    operation: str,
    request_id: UUID,
    body: CredentialTransitionBody,
    request: Request,
    actor: ActorContext,
) -> CredentialRequest | Credential:
    try:
        result = await getattr(_service(request), operation)(
            actor=actor, request_id=request_id, expected_version=body.expected_version
        )
        return cast(CredentialRequest | Credential, result)
    except KeyError as exc:
        raise APIError(404, "credential_not_found", "Credential request was not found.") from exc
    except PermissionError as exc:
        raise APIError(403, str(exc), "Credential action is not authorized.") from exc
    except ValueError as exc:
        raise APIError(409, str(exc), "Credential transition was rejected.") from exc


@router.post("/credential-requests/{request_id}/approve", response_model=CredentialRequest)
async def approve(
    request_id: UUID,
    body: CredentialTransitionBody,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> CredentialRequest:
    return cast(CredentialRequest, await _transition("approve", request_id, body, request, actor))


@router.post("/credential-requests/{request_id}/reject", response_model=CredentialRequest)
async def reject(
    request_id: UUID,
    body: CredentialTransitionBody,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> CredentialRequest:
    return cast(CredentialRequest, await _transition("reject", request_id, body, request, actor))


@router.post("/credential-requests/{request_id}/issue", response_model=Credential)
async def issue(
    request_id: UUID,
    body: CredentialTransitionBody,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> Credential:
    return cast(Credential, await _transition("issue", request_id, body, request, actor))


@router.post("/credentials/{credential_id}/revoke", response_model=Credential)
async def revoke(
    credential_id: UUID,
    body: CredentialTransitionBody,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> Credential:
    try:
        return await _service(request).revoke(
            actor=actor, credential_id=credential_id, expected_version=body.expected_version
        )
    except KeyError as exc:
        raise APIError(404, "credential_not_found", "Credential was not found.") from exc
    except (PermissionError, ValueError) as exc:
        raise APIError(409, str(exc), "Credential revoke was rejected.") from exc


@router.post("/credentials/{credential_id}/expire", response_model=Credential)
async def expire(
    credential_id: UUID,
    body: CredentialTransitionBody,
    request: Request,
    actor: ActorContext = Depends(get_development_actor),
) -> Credential:
    try:
        return await _service(request).expire_if_due(
            actor=actor, credential_id=credential_id, expected_version=body.expected_version
        )
    except KeyError as exc:
        raise APIError(404, "credential_not_found", "Credential was not found.") from exc
    except (PermissionError, ValueError) as exc:
        raise APIError(409, str(exc), "Credential expiry was rejected.") from exc


@router.get("/credentials/{credential_id}/verify", response_model=CredentialVerification)
async def verify(credential_id: UUID, request: Request) -> CredentialVerification:
    return await _service(request).verify_public(credential_id)
