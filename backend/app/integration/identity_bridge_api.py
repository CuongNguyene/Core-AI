from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.authorization.schemas import ActorContext
from app.integration.actor_context import get_signed_actor_context
from app.integration.auth import verify_integration_api_key
from app.integration.identity_bridge import (
    CandidateIdentityBridgeService,
    CandidateIdentityLink,
    IdentityBridgeError,
)
from app.integration.schemas import IntegrationEnvelopeV1
from app.shared.errors import APIError

router = APIRouter(
    prefix="/api/v1/integration",
    tags=["candidate-identity-bridge"],
    dependencies=[Depends(verify_integration_api_key)],
)


class CandidateLmsUserLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lms_user_id: str = Field(min_length=1, max_length=256)


class CandidateLmsUserLinkProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_id: UUID
    candidate_id: UUID
    source_system: str
    source_subject_ref: str
    organization_scope: UUID
    status: str


def _service(request: Request) -> CandidateIdentityBridgeService:
    service = getattr(request.app.state, "candidate_identity_bridge_service", None)
    if service is None:
        raise APIError(503, "candidate_identity_bridge_unavailable", "Identity bridge is not ready.")
    return cast(CandidateIdentityBridgeService, service)


def _projection(link: CandidateIdentityLink) -> CandidateLmsUserLinkProjection:
    return CandidateLmsUserLinkProjection(
        link_id=link.id,
        candidate_id=link.candidate_id,
        source_system=link.source_system,
        source_subject_ref=link.source_subject_ref,
        organization_scope=link.organization_scope,
        status=link.status,
    )


def _error(exc: IdentityBridgeError) -> APIError:
    messages = {
        "candidate_not_found": "Candidate was not found.",
        "lms_user_not_found": "LMS User was not found.",
        "candidate_not_linked": "Candidate is not linked to an LMS User.",
        "candidate_already_linked": "Candidate already has a different active LMS User link.",
        "user_already_linked": "LMS User already has a different active Candidate link.",
        "organization_mismatch": "Candidate and LMS User organizations do not match.",
        "lms_user_ineligible": "LMS User is not active or eligible.",
        "identity_link_forbidden": "Actor is not authorized to manage identity links.",
        "lms_identity_context_unavailable": "LMS identity context is unavailable.",
    }
    return APIError(exc.status_code, exc.code, messages.get(exc.code, "Identity link request was rejected."))


@router.post(
    "/candidates/{candidate_id}/lms-user-link",
    response_model=IntegrationEnvelopeV1[CandidateLmsUserLinkProjection],
)
async def create_link(
    candidate_id: UUID,
    body: IntegrationEnvelopeV1[CandidateLmsUserLinkRequest],
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CandidateLmsUserLinkProjection]:
    try:
        link = await _service(request).link(candidate_id, body.data.lms_user_id, actor)
    except IdentityBridgeError as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=_projection(link))


@router.get(
    "/candidates/{candidate_id}/lms-user-link",
    response_model=IntegrationEnvelopeV1[CandidateLmsUserLinkProjection],
)
async def get_link(
    candidate_id: UUID,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CandidateLmsUserLinkProjection]:
    try:
        link = await _service(request).get_link(candidate_id, actor)
    except IdentityBridgeError as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=_projection(link))
