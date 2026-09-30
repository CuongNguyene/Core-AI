from typing import NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.candidate.errors import CandidateDomainError
from app.candidate.schemas import (
    CandidateCreateRequest,
    CandidateCVVersionListResponse,
    CandidateCVVersionRequest,
    CandidateCVVersionResponse,
    CandidateDetail,
    CandidateDocumentRequest,
    CandidateEvidenceResponse,
    CandidateEvidenceResponseItem,
    CandidateExactReviewRequest,
    CandidateExtractionStatus,
    CandidateListResponse,
    CandidateProfileHistoryResponse,
    CandidateProfileLinkRequest,
    CandidateReviewRequest,
    CandidateStatus,
    CandidateSummary,
)
from app.candidate.service import CandidateService
from app.extraction.auth import DevelopmentActor, get_development_actor
from app.shared.errors import APIError

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])


def _service(request: Request) -> CandidateService:
    service = getattr(request.app.state, "candidate_service", None)
    if service is None:
        raise APIError(503, "candidate_service_unavailable", "Candidate service is not ready.")
    return cast(CandidateService, service)


def _raise(exc: CandidateDomainError) -> NoReturn:
    raise APIError(exc.status_code, exc.code, "Candidate operation could not be completed.") from exc


def _summary(candidate: object) -> CandidateSummary:
    from app.candidate.schemas import Candidate

    if not isinstance(candidate, Candidate):
        raise TypeError("candidate type mismatch")
    return CandidateSummary(
        candidate_id=candidate.candidate_id,
        candidate_code=candidate.candidate_code,
        display_name=candidate.display_name,
        email=candidate.primary_email,
        phone=candidate.primary_phone,
        status=candidate.status,
        review_state=candidate.review_state,
        version=candidate.current_profile_version,
        current_profile_id=candidate.current_profile_id,
        updated_at=candidate.updated_at,
    )


@router.post("", response_model=CandidateSummary, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    body: CandidateCreateRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateSummary:
    try:
        return _summary(await _service(request).create(actor, display_name=body.display_name, email=body.email, phone=body.phone))
    except CandidateDomainError as exc:
        _raise(exc)


@router.get("", response_model=CandidateListResponse)
async def list_candidates(
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
    status_filter: CandidateStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    sort: str = Query(default="updated_at_desc", pattern=r"^(updated_at|created_at)_(asc|desc)$"),
) -> CandidateListResponse:
    try:
        items, next_cursor = await _service(request).list(
            actor, status=status_filter, limit=limit, cursor=cursor, sort=sort, query=q
        )
        return CandidateListResponse(
            items=[_summary(item) for item in items], next_cursor=next_cursor
        )
    except CandidateDomainError as exc:
        _raise(exc)


@router.get("/{candidate_id}", response_model=CandidateDetail)
async def get_candidate(
    candidate_id: UUID,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateDetail:
    try:
        service = _service(request)
        candidate = await service.get(candidate_id, actor)
        claims = await service.detail_claims(candidate_id, actor)
        profile_reference = await service.current_profile_reference(candidate_id, actor)
        extraction_review = await service.extraction_review(candidate_id, actor)
        return CandidateDetail(
            **_summary(candidate).model_dump(),
            profile=(
                {
                    "reference": profile_reference.candidate_profile_id,
                    "version": candidate.current_profile_version,
                }
                if profile_reference is not None
                else None
            ),
            claims=list(claims),
            extraction_review=extraction_review,
            cv={"versions": len(await service.cv_versions(candidate_id, actor))},
        )
    except CandidateDomainError as exc:
        _raise(exc)


@router.post("/{candidate_id}/cv/versions", response_model=CandidateCVVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate_cv_version(
    candidate_id: UUID,
    body: CandidateCVVersionRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateCVVersionResponse:
    try:
        item = await _service(request).create_cv_version(candidate_id, body.document_id, actor)
        return CandidateCVVersionResponse.model_validate(item)
    except CandidateDomainError as exc:
        _raise(exc)


@router.get("/{candidate_id}/cv/versions", response_model=CandidateCVVersionListResponse)
async def list_candidate_cv_versions(
    candidate_id: UUID,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateCVVersionListResponse:
    try:
        items = await _service(request).cv_versions(candidate_id, actor)
        return CandidateCVVersionListResponse(
            items=[CandidateCVVersionResponse.model_validate(item) for item in items]
        )
    except CandidateDomainError as exc:
        _raise(exc)


@router.get("/{candidate_id}/profiles", response_model=CandidateProfileHistoryResponse)
async def list_candidate_profiles(
    candidate_id: UUID,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateProfileHistoryResponse:
    try:
        items = await _service(request).profile_history(candidate_id, actor)
        return CandidateProfileHistoryResponse.model_validate({"items": list(items)})
    except CandidateDomainError as exc:
        _raise(exc)


@router.post("/{candidate_id}/documents", response_model=dict[str, object], status_code=status.HTTP_201_CREATED)
async def attach_candidate_document(
    candidate_id: UUID,
    body: CandidateDocumentRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> dict[str, object]:
    try:
        relation = await _service(request).attach_document(
            candidate_id, body.document_id, body.is_primary, actor
        )
        return {
            "candidate_id": relation.candidate_id,
            "document_id": relation.document_id,
            "candidate_document_id": relation.candidate_document_id,
        }
    except CandidateDomainError as exc:
        _raise(exc)


@router.post("/{candidate_id}/profiles", response_model=dict[str, object], status_code=status.HTTP_201_CREATED)
async def link_candidate_profile(
    candidate_id: UUID,
    body: CandidateProfileLinkRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> dict[str, object]:
    try:
        relation = await _service(request).link_profile(candidate_id, body.profile_id, actor)
        return {
            "candidate_profile_id": relation.candidate_profile_id,
            "profile_version": relation.profile_version,
            "governance_version": relation.governance_version,
            "review_state": relation.review_state,
        }
    except CandidateDomainError as exc:
        _raise(exc)


@router.get("/{candidate_id}/extraction-status", response_model=CandidateExtractionStatus)
async def extraction_status(
    candidate_id: UUID,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateExtractionStatus:
    try:
        return await _service(request).extraction_status(candidate_id, actor)
    except CandidateDomainError as exc:
        _raise(exc)


@router.get("/{candidate_id}/claims/{claim_id}/evidence", response_model=CandidateEvidenceResponse)
async def claim_evidence(
    candidate_id: UUID,
    claim_id: UUID,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateEvidenceResponse:
    try:
        service = _service(request)
        items = await service.evidence(candidate_id, claim_id, actor)
        response_items = [
            CandidateEvidenceResponseItem(
                evidence_id=item.evidence_id,
                source_document_reference=await service.evidence_document_reference(
                    candidate_id, item.document_id, actor
                ),
                source_locator=item.source_locator,
                excerpt=item.excerpt,
                evidence_type=item.evidence_type,
                context=item.context,
                confidence=item.confidence,
                provenance=item.provenance,
            )
            for item in items
        ]
        return CandidateEvidenceResponse(
            candidate_id=candidate_id, claim_id=claim_id, items=response_items
        )
    except CandidateDomainError as exc:
        _raise(exc)


async def _review(
    candidate_id: UUID,
    body: CandidateReviewRequest,
    request: Request,
    actor: DevelopmentActor,
    action: str,
) -> CandidateSummary:
    try:
        result = await _service(request).review(
            candidate_id,
            actor,
            action,
            body.expected_profile_version,
            body.reason,
            body.idempotency_key,
        )
        return _summary(result)
    except CandidateDomainError as exc:
        _raise(exc)


@router.post("/{candidate_id}/accept", response_model=CandidateSummary)
async def accept_candidate(
    candidate_id: UUID,
    body: CandidateReviewRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateSummary:
    return await _review(candidate_id, body, request, actor, "accept")


@router.post("/{candidate_id}/request-revision", response_model=CandidateSummary)
async def request_candidate_revision(
    candidate_id: UUID,
    body: CandidateReviewRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateSummary:
    return await _review(candidate_id, body, request, actor, "request_revision")


@router.post("/{candidate_id}/reject", response_model=CandidateSummary)
async def reject_candidate(
    candidate_id: UUID,
    body: CandidateReviewRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateSummary:
    return await _review(candidate_id, body, request, actor, "reject")


async def _review_exact(
    candidate_id: UUID,
    profile_id: str,
    body: CandidateExactReviewRequest,
    request: Request,
    actor: DevelopmentActor,
    action: str,
) -> CandidateSummary:
    try:
        result = await _service(request).review_exact(
            candidate_id,
            profile_id,
            body.expected_governance_version,
            actor,
            action,
            body.reason,
            body.idempotency_key,
        )
        return _summary(result)
    except CandidateDomainError as exc:
        _raise(exc)


@router.post("/{candidate_id}/profiles/{profile_id}/accept", response_model=CandidateSummary)
async def accept_candidate_profile(
    candidate_id: UUID,
    profile_id: str,
    body: CandidateExactReviewRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateSummary:
    return await _review_exact(candidate_id, profile_id, body, request, actor, "accept")


@router.post("/{candidate_id}/profiles/{profile_id}/reject", response_model=CandidateSummary)
async def reject_candidate_profile(
    candidate_id: UUID,
    profile_id: str,
    body: CandidateExactReviewRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CandidateSummary:
    return await _review_exact(candidate_id, profile_id, body, request, actor, "reject")
