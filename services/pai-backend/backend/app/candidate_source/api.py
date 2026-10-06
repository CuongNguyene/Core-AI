from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.authorization.schemas import ActorContext, Role
from app.candidate_source.domain import CandidateSourceError, project_candidate_profile
from app.candidate_source.repository import SqlAlchemyCandidateSourceRepository
from app.candidate_source.schemas import (
    CandidateSourceProjectionV1,
    EmployeeLearningProjectionV1,
    StrictSourceModel,
)
from app.integration.actor_context import get_signed_actor_context
from app.integration.auth import verify_integration_api_key
from app.integration.schemas import IntegrationEnvelopeV1
from app.shared.errors import APIError

router = APIRouter(
    prefix="/api/v1/candidate-sources",
    tags=["candidate-sources"],
    dependencies=[Depends(verify_integration_api_key)],
)


class OrganizationMappingCreate(StrictSourceModel):
    source_system: str
    external_company_ref: str
    organization_id: UUID


class OrganizationMappingCreated(StrictSourceModel):
    mapping_id: UUID


class CandidateSourceIngestResult(StrictSourceModel):
    candidate_id: UUID
    snapshot_id: UUID
    source_revision: int
    fingerprint: str
    disposition: str
    current_snapshot_id: UUID | None
    projected_profile: dict[str, object]


def _repository(request: Request) -> SqlAlchemyCandidateSourceRepository:
    value = getattr(request.app.state, "candidate_source_repository", None)
    if value is None:
        raise APIError(
            503, "candidate_source_unavailable", "Candidate source ingestion is not ready."
        )
    return cast(SqlAlchemyCandidateSourceRepository, value)


@router.post(
    "/organization-mappings",
    response_model=IntegrationEnvelopeV1[OrganizationMappingCreated],
    status_code=201,
)
async def create_organization_mapping(
    body: IntegrationEnvelopeV1[OrganizationMappingCreate],
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[OrganizationMappingCreated]:
    mapping = body.data
    if Role.ADMIN not in actor.roles or mapping.organization_id != actor.organization_id:
        raise APIError(
            403, "organization_mapping_forbidden", "Organization mapping administration is denied."
        )
    try:
        mapping_id = await _repository(request).add_organization_mapping(
            organization_id=mapping.organization_id,
            source_system=mapping.source_system,
            external_company_ref=mapping.external_company_ref,
        )
    except CandidateSourceError as exc:
        raise APIError(
            409, exc.args[0], "Organization mapping conflicts with an existing mapping."
        ) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1", data=OrganizationMappingCreated(mapping_id=mapping_id)
    )


@router.post("/snapshots", response_model=IntegrationEnvelopeV1[CandidateSourceIngestResult])
async def ingest_candidate_snapshot(
    body: IntegrationEnvelopeV1[CandidateSourceProjectionV1],
    request: Request,
    response: Response,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CandidateSourceIngestResult]:
    return await _ingest_source(body.data, request, response, actor)


@router.post(
    "/learning-projections", response_model=IntegrationEnvelopeV1[CandidateSourceIngestResult]
)
async def ingest_learning_projection(
    body: IntegrationEnvelopeV1[EmployeeLearningProjectionV1],
    request: Request,
    response: Response,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CandidateSourceIngestResult]:
    return await _ingest_source(body.data, request, response, actor)


async def _ingest_source(
    source: CandidateSourceProjectionV1 | EmployeeLearningProjectionV1,
    request: Request,
    response: Response,
    actor: ActorContext,
) -> IntegrationEnvelopeV1[CandidateSourceIngestResult]:
    if not actor.roles.intersection({Role.ADMIN, Role.REVIEWER}):
        raise APIError(
            403, "candidate_source_writer_required", "Candidate source ingestion is not authorized."
        )
    envelope = source.to_candidate_source_envelope()
    try:
        repository = _repository(request)
        if isinstance(source, EmployeeLearningProjectionV1):
            result = await repository.ingest_learning_projection(source, actor=actor)
        else:
            result = await repository.ingest(envelope, actor=actor)
    except CandidateSourceError as exc:
        code = exc.args[0]
        status_code = (
            404
            if code == "organization_mapping_not_found"
            else (403 if code.endswith("forbidden") else 409)
        )
        raise APIError(
            status_code, code, "Candidate source snapshot could not be accepted."
        ) from exc
    result_body = CandidateSourceIngestResult(
        candidate_id=result.candidate_id,
        snapshot_id=result.snapshot_id,
        source_revision=result.source_revision,
        fingerprint=result.fingerprint,
        disposition=result.disposition,
        current_snapshot_id=result.current_snapshot_id,
        projected_profile=project_candidate_profile(envelope).model_dump(mode="json"),
    )
    response.status_code = 200 if result.disposition == "REPLAY" else 201
    return IntegrationEnvelopeV1(schema_version="v1", data=result_body)
