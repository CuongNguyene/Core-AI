import inspect
from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from app.authorization.schemas import Role
from app.extraction.auth import DevelopmentActor, get_development_actor, require_reviewer
from app.extraction.errors import ExtractionProfileStateConflict, ExtractionProfileVersionConflict
from app.extraction.fixtures import DocumentSource
from app.extraction.jd_requirement_validation import (
    bind_jd_requirement_source_document,
    validate_requirement_v2_output,
)
from app.extraction.jd_review_projection import (
    JDReviewProjection,
    apply_jd_review_correction,
    build_jd_review_projection,
)
from app.extraction.repository import ExtractionRepository
from app.extraction.schemas import (
    CVExtractionOutput,
    CVFullExtractionOutputV2,
    DocumentKind,
    ExtractionJob,
    ExtractionProfile,
    JDExtractionOutput,
    JDRequirementExtractionOutputV2,
    JDReviewCorrectionRequest,
    JobStatus,
    ReviewState,
)
from app.shared.errors import APIError, correlation_id_for

router = APIRouter(tags=["extraction"])


class CreateExtractionJobRequest(BaseModel):
    document_id: str
    document_kind: DocumentKind


class SubmitCorrectionRequest(BaseModel):
    output: dict[str, object]


class AcceptExtractionProfileRequest(BaseModel):
    expected_version: int = Field(ge=1)


def _repository(request: Request) -> ExtractionRepository:
    repository = getattr(request.app.state, "extraction_repository", None)
    if repository is None:
        raise APIError(503, "extraction_repository_unavailable", "Extraction service is not ready.")
    return cast(ExtractionRepository, repository)


def _document_source(request: Request) -> DocumentSource:
    return cast(
        DocumentSource,
        getattr(request.app.state, "document_source", request.app.state.fixture_document_source),
    )


def _can_read(actor: DevelopmentActor, owner_actor_id: UUID) -> bool:
    return actor.actor_id == owner_actor_id or Role.REVIEWER in actor.roles


@router.post("/extraction-jobs", response_model=ExtractionJob, status_code=status.HTTP_201_CREATED)
async def create_extraction_job(
    body: CreateExtractionJobRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> ExtractionJob:
    try:
        result = _document_source(request).get(body.document_id, body.document_kind)
        if inspect.isawaitable(result):
            await result
    except (KeyError, ValueError) as exc:
        raise APIError(
            404, "document_not_found_or_ineligible", "Document was not found or is not eligible."
        ) from exc
    job = ExtractionJob(
        id=str(uuid4()),
        document_id=body.document_id,
        document_kind=body.document_kind,
        owner_actor_id=actor.actor_id,
        correlation_id=str(correlation_id_for(request)),
        status=JobStatus.QUEUED,
    )
    return await _repository(request).enqueue(job)


@router.get("/extraction-jobs/{job_id}", response_model=ExtractionJob)
async def get_extraction_job(
    job_id: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> ExtractionJob:
    job = await _repository(request).get_job(job_id)
    if job is None:
        raise APIError(404, "extraction_job_not_found", "Extraction job was not found.")
    if not _can_read(actor, job.owner_actor_id):
        raise APIError(403, "extraction_access_denied", "Extraction access is denied.")
    return job


@router.delete("/extraction-jobs/{job_id}", response_model=ExtractionJob)
async def cancel_extraction_job(
    job_id: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> ExtractionJob:
    job = await _repository(request).get_job(job_id)
    if job is None:
        raise APIError(404, "extraction_job_not_found", "Extraction job was not found.")
    if not _can_read(actor, job.owner_actor_id):
        raise APIError(403, "extraction_access_denied", "Extraction access is denied.")
    try:
        return await _repository(request).cancel(job_id)
    except ValueError as exc:
        raise APIError(409, "extraction_job_not_cancellable", "Extraction job is no longer active.") from exc


@router.get("/extraction-profiles/{profile_id}", response_model=ExtractionProfile)
async def get_extraction_profile(
    profile_id: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> ExtractionProfile:
    profile = await _repository(request).get_profile(profile_id)
    if profile is None:
        raise APIError(404, "extraction_profile_not_found", "Extraction profile was not found.")
    if not _can_read(actor, profile.owner_actor_id):
        raise APIError(403, "extraction_access_denied", "Extraction access is denied.")
    return profile


@router.delete("/extraction-profiles/{profile_id}")
async def delete_extraction_profile(
    profile_id: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> dict[str, str]:
    profile = await _repository(request).get_profile(profile_id)
    if profile is None:
        raise APIError(404, "extraction_profile_not_found", "Extraction profile was not found.")
    if not _can_read(actor, profile.owner_actor_id):
        raise APIError(403, "extraction_access_denied", "Extraction access is denied.")
    require_reviewer(actor)
    try:
        await _repository(request).delete_profile(profile_id)
    except ExtractionProfileStateConflict as exc:
        raise APIError(
            409,
            "extraction_profile_delete_blocked",
            "Extraction profile cannot be deleted while it has dependent records.",
        ) from exc
    return {"profile_id": profile_id}


@router.get("/jd-extraction-profiles", response_model=list[JDReviewProjection])
async def list_jd_review_projections(
    request: Request,
    document_kind: DocumentKind = Query(default=DocumentKind.JD),
    actor: DevelopmentActor = Depends(get_development_actor),
) -> list[JDReviewProjection]:
    if document_kind is not DocumentKind.JD:
        return []
    projections: list[JDReviewProjection] = []
    for profile in await _repository(request).list_profiles(DocumentKind.JD):
        if not _can_read(actor, profile.owner_actor_id):
            continue
        try:
            # The projection derives PDF/text from the persisted source locators.
            # Do not read every source document while building a list response.
            projections.append(build_jd_review_projection(profile))
        except ValueError:
            continue
    return projections


@router.get("/extraction-profiles/{profile_id}/review", response_model=JDReviewProjection)
async def get_jd_review_projection(
    profile_id: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> JDReviewProjection:
    profile = await _repository(request).get_profile(profile_id)
    if profile is None:
        raise APIError(404, "extraction_profile_not_found", "Extraction profile was not found.")
    if not _can_read(actor, profile.owner_actor_id):
        raise APIError(403, "extraction_access_denied", "Extraction access is denied.")
    try:
        document_result = _document_source(request).get(profile.document_id, profile.document_kind)
        document = (
            await document_result if inspect.isawaitable(document_result) else document_result
        )
        return build_jd_review_projection(
            profile,
            source_format="pdf" if document.content_type == "application/pdf" else "text",
        )
    except ValueError as exc:
        raise APIError(
            422, "jd_review_projection_unavailable", "JD review projection is unavailable."
        ) from exc


@router.post(
    "/extraction-profiles/{profile_id}/review-corrections",
    response_model=ExtractionProfile,
    status_code=status.HTTP_201_CREATED,
)
async def submit_jd_review_correction(
    profile_id: str,
    body: JDReviewCorrectionRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> ExtractionProfile:
    require_reviewer(actor)
    repository = _repository(request)
    previous = await repository.get_profile(profile_id)
    if previous is None:
        raise APIError(404, "extraction_profile_not_found", "Extraction profile was not found.")
    if previous.version != body.expected_version:
        raise APIError(409, "extraction_profile_version_conflict", "Extraction profile is stale.")
    if previous.review_state not in {ReviewState.PENDING_REVIEW, ReviewState.CORRECTED}:
        raise APIError(409, "extraction_profile_not_editable", "Extraction profile is read-only.")
    try:
        output = apply_jd_review_correction(previous, body)
        document_result = _document_source(request).get(
            previous.document_id, previous.document_kind
        )
        document = (
            await document_result if inspect.isawaitable(document_result) else document_result
        )
        output = bind_jd_requirement_source_document(
            output,
            document_id=previous.document_id,
            parsed_text=document.content,
            is_pdf=document.content_type == "application/pdf",
            page_texts=document.page_texts,
        )
        validate_requirement_v2_output(
            output,
            expected_document_id=previous.document_id,
            document_text=document.content,
            page_texts=document.page_texts,
        )
        return await repository.create_correction(profile_id, actor.actor_id, output)
    except ExtractionProfileStateConflict as exc:
        raise APIError(
            409,
            "extraction_profile_not_current",
            "Correction must start from the current profile version.",
        ) from exc
    except (KeyError, ValueError) as exc:
        raise APIError(
            422, "invalid_jd_review_correction", "JD review correction is invalid."
        ) from exc


@router.post(
    "/extraction-profiles/{profile_id}/corrections",
    response_model=ExtractionProfile,
    status_code=status.HTTP_201_CREATED,
)
async def submit_correction(
    profile_id: str,
    body: SubmitCorrectionRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> ExtractionProfile:
    require_reviewer(actor)
    previous = await _repository(request).get_profile(profile_id)
    if previous is None:
        raise APIError(404, "extraction_profile_not_found", "Extraction profile was not found.")
    try:
        output = (
            (
                CVFullExtractionOutputV2.model_validate(body.output, strict=False)
                if "capabilities" in body.output
                else CVExtractionOutput.model_validate(body.output, strict=False)
            )
            if previous.document_kind is DocumentKind.CV
            else (
                JDRequirementExtractionOutputV2.model_validate(body.output, strict=False)
                if "requirements" in body.output
                else JDExtractionOutput.model_validate(body.output, strict=False)
            )
        )
    except ValueError as exc:
        raise APIError(422, "invalid_correction_output", "Correction output is invalid.") from exc
    if isinstance(output, JDRequirementExtractionOutputV2):
        try:
            document_result = _document_source(request).get(
                previous.document_id, previous.document_kind
            )
            document = (
                await document_result if inspect.isawaitable(document_result) else document_result
            )
            output = bind_jd_requirement_source_document(
                output,
                document_id=previous.document_id,
                parsed_text=document.content,
                is_pdf=document.content_type == "application/pdf",
                page_texts=document.page_texts,
            )
            validate_requirement_v2_output(
                output,
                expected_document_id=previous.document_id,
                document_text=document.content,
                page_texts=document.page_texts,
            )
        except (KeyError, ValueError) as exc:
            raise APIError(
                422, "invalid_correction_output", "Correction output is invalid."
            ) from exc
    try:
        return await _repository(request).create_correction(profile_id, actor.actor_id, output)
    except ExtractionProfileStateConflict as exc:
        raise APIError(
            409,
            "extraction_profile_not_current",
            "Correction must start from the current profile version.",
        ) from exc


@router.post("/extraction-profiles/{profile_id}/accept", response_model=ExtractionProfile)
async def accept_extraction_profile(
    profile_id: str,
    body: AcceptExtractionProfileRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> ExtractionProfile:
    require_reviewer(actor)
    repository = _repository(request)
    existing = await repository.get_profile(profile_id)
    if existing is None:
        raise APIError(404, "extraction_profile_not_found", "Extraction profile was not found.")
    try:
        return await repository.accept_profile(profile_id, actor.actor_id, body.expected_version)
    except ExtractionProfileVersionConflict as exc:
        raise APIError(
            409,
            "extraction_profile_version_conflict",
            "Extraction profile version is no longer current.",
        ) from exc
    except ExtractionProfileStateConflict as exc:
        raise APIError(
            409,
            "extraction_profile_not_acceptable",
            "Extraction profile cannot be accepted in its current state.",
        ) from exc
    except KeyError as exc:
        raise APIError(
            409,
            "extraction_source_ineligible",
            "Extraction source is not eligible for acceptance.",
        ) from exc


async def _transition_review_state(
    profile_id: str,
    body: AcceptExtractionProfileRequest,
    request: Request,
    actor: DevelopmentActor,
    transition: str,
) -> ExtractionProfile:
    require_reviewer(actor)
    repository = _repository(request)
    if await repository.get_profile(profile_id) is None:
        raise APIError(404, "extraction_profile_not_found", "Extraction profile was not found.")
    try:
        if transition == "request_revision":
            return await repository.request_revision(
                profile_id, actor.actor_id, body.expected_version
            )
        return await repository.reject_profile(profile_id, actor.actor_id, body.expected_version)
    except ExtractionProfileVersionConflict as exc:
        raise APIError(
            409, "extraction_profile_version_conflict", "Extraction profile version is stale."
        ) from exc
    except ExtractionProfileStateConflict as exc:
        raise APIError(
            409,
            "extraction_profile_state_conflict",
            "Extraction profile transition is not allowed.",
        ) from exc


@router.post("/extraction-profiles/{profile_id}/request-revision", response_model=ExtractionProfile)
async def request_profile_revision(
    profile_id: str,
    body: AcceptExtractionProfileRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> ExtractionProfile:
    return await _transition_review_state(profile_id, body, request, actor, "request_revision")


@router.post("/extraction-profiles/{profile_id}/reject", response_model=ExtractionProfile)
async def reject_extraction_profile(
    profile_id: str,
    body: AcceptExtractionProfileRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> ExtractionProfile:
    return await _transition_review_state(profile_id, body, request, actor, "reject_profile")
