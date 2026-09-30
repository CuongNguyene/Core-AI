from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from app.candidate.schemas import Candidate
from app.capability_analysis.errors import (
    CandidateProfileNotAnalyzableError,
    CapabilityAnalysisAccessDeniedError,
    CapabilityAnalysisIdempotencyConflictError,
    CapabilityAnalysisProductError,
    CurrentTargetNotUsableError,
    ExtractionProfileNotAcceptedError,
    FutureTargetNotUsableError,
    HumanAssistedReanalysisValidationError,
    SemanticPolicyNotConfiguredError,
    SemanticPolicyUnavailableError,
    SupersededCapabilityProfileError,
)
from app.capability_analysis.schemas import (
    CombinedGapPortfolio,
    HumanAssistedReanalysisRequest,
    TargetGap,
    TargetType,
)
from app.capability_analysis.service import (
    CandidateRoleAnalysisResult,
    CapabilityGapAnalysisService,
)
from app.authorization.schemas import ActorContext
from app.integration.actor_context import get_signed_actor_context
from app.integration.auth import verify_integration_api_key
from app.integration.capability_gap_schemas import (
    CandidateCapabilityAnalysisHistoryItemV1,
    CandidateCapabilityAnalysisHistoryResponseV1,
    CandidateEvidenceProjectionV1,
    CapabilityAnalysisCreateV1,
    CapabilityAnalysisProjectionV1,
    CapabilityCandidateProfileReferenceV1,
    CapabilityCandidateReferenceV1,
    CapabilityEvidenceItemV1,
    CapabilityEvidenceProjectionV1,
    CapabilityGapReviewProjectionV1,
    CapabilityGapSummaryV1,
    CapabilityGapV1,
    CapabilityRoleProfileReferenceV1,
    CapabilityRoleReferenceV1,
    HumanAssistedAnalysisV1,
    HumanAssistedSelectionV1,
    LearningDecisionProjectionV1,
    RecommendationV1,
)
from app.integration.schemas import IntegrationEnvelopeV1
from app.role_registry.schemas import Role as RoleRecord
from app.shared.errors import APIError

router = APIRouter(
    prefix="/api/v1/integration",
    tags=["integration-capability-analysis"],
    dependencies=[Depends(verify_integration_api_key)],
)


def _service(request: Request) -> CapabilityGapAnalysisService:
    service = getattr(request.app.state, "capability_gap_analysis_service", None)
    if service is None:
        raise APIError(503, "capability_gap_unavailable", "Capability analysis is not ready.")
    return cast(CapabilityGapAnalysisService, service)


def _error(exc: Exception) -> APIError:
    if isinstance(exc, CapabilityAnalysisProductError):
        messages = {
            "candidate_not_found": (404, "candidate_not_found", "Candidate was not found."),
            "candidate_profile_not_ready": (
                409,
                "candidate_profile_not_ready",
                "An accepted candidate profile is required before analysis.",
            ),
            "role_not_found": (404, "role_not_found", "Role was not found."),
            "role_profile_not_active": (
                409,
                "role_profile_not_active",
                "Activate an eligible role profile before analysis.",
            ),
            "candidate_role_organization_mismatch": (
                403,
                "candidate_role_organization_mismatch",
                "Candidate and role must belong to the same organization.",
            ),
        }
        status_code, code, message = messages.get(
            str(exc),
            (
                503,
                "capability_product_adapter_unavailable",
                "Capability product adapter is not ready.",
            ),
        )
        return APIError(status_code, code, message)
    if isinstance(exc, CapabilityAnalysisIdempotencyConflictError):
        return APIError(409, "capability_analysis_idempotency_conflict", "Analysis key conflict.")
    if isinstance(exc, HumanAssistedReanalysisValidationError):
        return APIError(
            409,
            "human_assisted_reanalysis_invalid",
            "Human-assisted evidence selection is not valid for this analysis.",
        )
    if isinstance(exc, CapabilityAnalysisAccessDeniedError):
        return APIError(
            403, "capability_gap_access_denied", "Capability analysis access is denied."
        )
    if isinstance(exc, CandidateProfileNotAnalyzableError):
        return APIError(
            409,
            "candidate_profile_not_analyzable",
            "The accepted CV profile has no analyzable capabilities.",
        )
    if isinstance(exc, (ExtractionProfileNotAcceptedError, SupersededCapabilityProfileError)):
        return APIError(
            409, "capability_gap_input_not_accepted", "The accepted CV profile is not ready."
        )
    if isinstance(exc, (CurrentTargetNotUsableError, FutureTargetNotUsableError)):
        return APIError(409, "target_profile_not_usable", "The target profile is not usable.")
    if isinstance(exc, SemanticPolicyNotConfiguredError):
        return APIError(409, "semantic_policy_not_configured", "Semantic policy is not configured.")
    if isinstance(exc, SemanticPolicyUnavailableError):
        return APIError(503, "semantic_policy_unavailable", "Semantic policy is unavailable.")
    return APIError(502, "capability_gap_integration_error", "Capability analysis failed.")


def _projection(
    portfolio: CombinedGapPortfolio,
    review: CapabilityGapReviewProjectionV1 | None = None,
    candidate: Candidate | None = None,
    role: RoleRecord | None = None,
) -> CapabilityAnalysisProjectionV1:
    tracks = [portfolio.current_role] + ([portfolio.future_role] if portfolio.future_role else [])
    gaps = [gap for track in tracks if track is not None for gap in track.gaps]
    recommendations = [
        RecommendationV1(
            recommendation_reference=f"recommendation:{gap.id}",
            gap_reference=gap.id,
            title=gap.recommendation,
        )
        for gap in gaps
        if gap.recommendation
    ]
    projected_gaps = [
        _gap_projection(
            gap,
            "current_role" if track.target_type is TargetType.CURRENT_ROLE else "future_role",
        )
        for track in tracks
        for gap in track.gaps
    ]
    target = f"{portfolio.current_role.target_id}@{portfolio.current_target_version}"
    warning_codes = list(portfolio.current_role.warning_codes)
    if portfolio.future_role:
        warning_codes.extend(portfolio.future_role.warning_codes)
    if portfolio.candidate_id is None:
        raise ValueError("capability_analysis_missing_candidate")
    return CapabilityAnalysisProjectionV1(
        analysis_id=portfolio.id,
        status=portfolio.analysis_status.value,
        analysis_version=portfolio.analysis_version,
        candidate_reference=portfolio.candidate_id,
        target_reference=target,
        snapshot_schema_version=portfolio.snapshot_schema_version,
        summary=CapabilityGapSummaryV1(
            gap_count=len(projected_gaps),
            warning_codes=warning_codes,
        ),
        gaps=projected_gaps,
        recommendations=recommendations,
        evidence_available=any(gap.matched_evidence_refs for gap in gaps),
        candidate=(
            CapabilityCandidateReferenceV1(
                candidate_id=candidate.candidate_id,
                candidate_code=candidate.candidate_code,
                display_name=candidate.display_name,
            )
            if candidate is not None
            else None
        ),
        candidate_profile=CapabilityCandidateProfileReferenceV1(
            profile_id=portfolio.cv_profile_id,
            profile_version=portfolio.cv_profile_version,
            review_state="ACCEPTED",
        ),
        role_profile=CapabilityRoleProfileReferenceV1(
            profile_id=portfolio.current_role.target_id,
            profile_version=portfolio.current_target_version,
            status=review.role_profile_state if review is not None else "SNAPSHOT",
        ),
        role=(
            CapabilityRoleReferenceV1(
                role_id=role.id,
                role_code=role.role_code,
                title=role.title,
            )
            if role is not None
            else None
        ),
        review=review,
    )


def _learning_decision_projection(
    portfolio: CombinedGapPortfolio,
    review: CapabilityGapReviewProjectionV1,
    candidate: Candidate | None,
    role: RoleRecord | None,
) -> LearningDecisionProjectionV1:
    return LearningDecisionProjectionV1(
        analysis_id=portfolio.id,
        candidate=(
            CapabilityCandidateReferenceV1(
                candidate_id=candidate.candidate_id,
                candidate_code=candidate.candidate_code,
                display_name=candidate.display_name,
            )
            if candidate is not None
            else None
        ),
        candidate_profile=CapabilityCandidateProfileReferenceV1(
            profile_id=portfolio.cv_profile_id,
            profile_version=portfolio.cv_profile_version,
            review_state="ACCEPTED",
        ),
        role=(
            CapabilityRoleReferenceV1(
                role_id=role.id,
                role_code=role.role_code,
                title=role.title,
            )
            if role is not None
            else None
        ),
        role_profile=CapabilityRoleProfileReferenceV1(
            profile_id=portfolio.current_role.target_id,
            profile_version=portfolio.current_target_version,
            status=review.role_profile_state,
        ),
        usage_mode=portfolio.current_role.usage_mode.value,
        learning_readiness=review.learning_readiness,
    )


def _product_projection(
    result: object,
    review: CapabilityGapReviewProjectionV1 | None = None,
) -> CapabilityAnalysisProjectionV1:
    product = cast(CandidateRoleAnalysisResult, result)
    projection = _projection(product.portfolio, review)
    return projection.model_copy(
        update={
            "candidate": CapabilityCandidateReferenceV1(
                candidate_id=product.candidate.candidate_id,
                candidate_code=product.candidate.candidate_code,
                display_name=product.candidate.display_name,
            ),
            "candidate_profile": CapabilityCandidateProfileReferenceV1(
                profile_id=product.candidate_profile_id,
                profile_version=product.candidate_profile_version,
                review_state=product.candidate.review_state.value,
            ),
            "role": CapabilityRoleReferenceV1(
                role_id=product.role.id,
                role_code=product.role.role_code,
                title=product.role.title,
            ),
            "role_profile": CapabilityRoleProfileReferenceV1(
                profile_id=product.role_profile.id,
                profile_version=product.role_profile.version,
                governance_version=product.role_profile.governance_version,
                status=product.role_profile.status.value,
            ),
        }
    )


def _gap_projection(
    gap: TargetGap, target_type: Literal["current_role", "future_role"]
) -> CapabilityGapV1:
    return CapabilityGapV1(
        gap_reference=gap.id,
        target_type=target_type,
        requirement_reference=gap.requirement_id,
        status=gap.evidence_status.value,
        priority=gap.preliminary_priority.value,
        confidence=gap.decision_details.observed_confidence,
        missing_signals=gap.missing_signals,
        evidence_references=gap.matched_evidence_refs,
        rationale=gap.rationale,
        verification_required=gap.decision_details.verification_required,
    )


@router.post(
    "/candidates/{candidate_id}/capability-analyses",
    response_model=IntegrationEnvelopeV1[CapabilityAnalysisProjectionV1],
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis(
    body: IntegrationEnvelopeV1[CapabilityAnalysisCreateV1],
    candidate_id: UUID,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> IntegrationEnvelopeV1[CapabilityAnalysisProjectionV1]:
    if not idempotency_key:
        raise APIError(400, "idempotency_key_required", "Idempotency-Key is required.")
    try:
        service = _service(request)
        portfolio = await service.create_for_candidate(
            candidate_id=candidate_id,
            current_target_reference=body.data.current_target_reference,
            future_target_reference=body.data.future_target_reference,
            idempotency_key=idempotency_key,
            actor=actor,
        )
    except Exception as exc:
        raise _error(exc) from exc
    review = await service.review_projection(portfolio)
    candidate, role = await service.identity_projection(portfolio)
    return IntegrationEnvelopeV1(
        schema_version="v1", data=_projection(portfolio, review, candidate, role)
    )


@router.post(
    "/candidates/{candidate_id}/roles/{role_id}/capability-analyses",
    response_model=IntegrationEnvelopeV1[CapabilityAnalysisProjectionV1],
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis_for_candidate_role(
    candidate_id: UUID,
    role_id: UUID,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> IntegrationEnvelopeV1[CapabilityAnalysisProjectionV1]:
    if not idempotency_key:
        raise APIError(400, "idempotency_key_required", "Idempotency-Key is required.")
    try:
        service = _service(request)
        product_result = await service.create_for_candidate_role(
            candidate_id=candidate_id,
            role_id=role_id,
            idempotency_key=idempotency_key,
            actor=actor,
        )
    except Exception as exc:
        raise _error(exc) from exc
    review = await service.review_projection(product_result.portfolio)
    return IntegrationEnvelopeV1(
        schema_version="v1", data=_product_projection(product_result, review)
    )


@router.get(
    "/capability-analyses/{analysis_id}",
    response_model=IntegrationEnvelopeV1[CapabilityAnalysisProjectionV1],
)
async def get_analysis(
    analysis_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CapabilityAnalysisProjectionV1]:
    try:
        service = _service(request)
        portfolio = await service.get(analysis_id, actor)
    except KeyError as exc:
        raise APIError(404, "capability_analysis_not_found", "Analysis was not found.") from exc
    except CapabilityAnalysisAccessDeniedError as exc:
        raise _error(exc) from exc
    review = await service.review_projection(portfolio)
    candidate, role = await service.identity_projection(portfolio)
    return IntegrationEnvelopeV1(
        schema_version="v1", data=_projection(portfolio, review, candidate, role)
    )


@router.get(
    "/candidates/{candidate_id}/capability-analyses",
    response_model=IntegrationEnvelopeV1[CandidateCapabilityAnalysisHistoryResponseV1],
)
async def list_candidate_analyses(
    candidate_id: UUID,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CandidateCapabilityAnalysisHistoryResponseV1]:
    try:
        service = _service(request)
        portfolios = await service.list_for_candidate(candidate_id, actor)
        items: list[CandidateCapabilityAnalysisHistoryItemV1] = []
        for portfolio in portfolios:
            candidate, role = await service.identity_projection(portfolio)
            review = await service.review_projection(portfolio)
            items.append(
                CandidateCapabilityAnalysisHistoryItemV1(
                    analysis_id=portfolio.id,
                    analysis_version=portfolio.analysis_version,
                    status=portfolio.analysis_status.value,
                    usage_mode=portfolio.current_role.usage_mode.value,
                    candidate_profile_id=portfolio.cv_profile_id,
                    candidate_profile_version=portfolio.cv_profile_version,
                    candidate_code=candidate.candidate_code if candidate is not None else None,
                    candidate_display_name=candidate.display_name
                    if candidate is not None
                    else None,
                    role_id=role.id if role is not None else None,
                    role_code=role.role_code if role is not None else None,
                    role_title=role.title if role is not None else None,
                    role_profile_id=portfolio.current_role.target_id,
                    role_profile_version=portfolio.current_target_version,
                    readiness=review.summary,
                )
            )
    except CapabilityAnalysisProductError as exc:
        raise _error(exc) from exc
    except KeyError as exc:
        raise APIError(404, "candidate_not_found", "Candidate was not found.") from exc
    except CapabilityAnalysisAccessDeniedError as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=CandidateCapabilityAnalysisHistoryResponseV1(items=items),
    )


@router.get(
    "/capability-analyses/{analysis_id}/learning-decision",
    response_model=IntegrationEnvelopeV1[LearningDecisionProjectionV1],
)
async def get_learning_decision(
    analysis_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[LearningDecisionProjectionV1]:
    try:
        service = _service(request)
        portfolio = await service.get(analysis_id, actor)
        review = await service.review_projection(portfolio)
        candidate, role = await service.identity_projection(portfolio)
        projection = _learning_decision_projection(portfolio, review, candidate, role)
    except KeyError as exc:
        raise APIError(404, "capability_analysis_not_found", "Analysis was not found.") from exc
    except CapabilityAnalysisAccessDeniedError as exc:
        raise _error(exc) from exc
    except ValueError as exc:
        raise APIError(
            409,
            "learning_decision_projection_invalid",
            "Learning decision projection is unavailable.",
        ) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=projection)


@router.get(
    "/roles/{role_id}/capability-analyses",
    response_model=IntegrationEnvelopeV1[CandidateCapabilityAnalysisHistoryResponseV1],
)
async def list_role_analyses(
    role_id: UUID,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CandidateCapabilityAnalysisHistoryResponseV1]:
    try:
        service = _service(request)
        portfolios = await service.list_for_role(role_id, actor)
        items: list[CandidateCapabilityAnalysisHistoryItemV1] = []
        for portfolio in portfolios:
            candidate, role = await service.identity_projection(portfolio)
            review = await service.review_projection(portfolio)
            items.append(
                CandidateCapabilityAnalysisHistoryItemV1(
                    analysis_id=portfolio.id,
                    analysis_version=portfolio.analysis_version,
                    status=portfolio.analysis_status.value,
                    usage_mode=portfolio.current_role.usage_mode.value,
                    candidate_profile_id=portfolio.cv_profile_id,
                    candidate_profile_version=portfolio.cv_profile_version,
                    candidate_code=candidate.candidate_code if candidate is not None else None,
                    candidate_display_name=candidate.display_name
                    if candidate is not None
                    else None,
                    role_id=role.id if role is not None else role_id,
                    role_code=role.role_code if role is not None else None,
                    role_title=role.title if role is not None else None,
                    role_profile_id=portfolio.current_role.target_id,
                    role_profile_version=portfolio.current_target_version,
                    readiness=review.summary,
                )
            )
    except CapabilityAnalysisProductError as exc:
        raise _error(exc) from exc
    except KeyError as exc:
        raise APIError(404, "role_not_found", "Role was not found.") from exc
    except CapabilityAnalysisAccessDeniedError as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=CandidateCapabilityAnalysisHistoryResponseV1(items=items),
    )


@router.get(
    "/capability-analyses/{analysis_id}/candidate-evidence",
    response_model=IntegrationEnvelopeV1[CandidateEvidenceProjectionV1],
)
async def get_candidate_evidence(
    analysis_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CandidateEvidenceProjectionV1]:
    try:
        service = _service(request)
        portfolio = await service.get(analysis_id, actor)
        projection = await service.candidate_evidence_projection(portfolio)
    except KeyError as exc:
        raise APIError(404, "capability_analysis_not_found", "Analysis was not found.") from exc
    except CapabilityAnalysisAccessDeniedError as exc:
        raise _error(exc) from exc
    except HumanAssistedReanalysisValidationError as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=projection)


@router.post(
    "/capability-analyses/{analysis_id}/reanalyse-with-evidence",
    response_model=IntegrationEnvelopeV1[CapabilityAnalysisProjectionV1],
    status_code=status.HTTP_201_CREATED,
)
async def reanalyse_with_evidence(
    analysis_id: str,
    body: IntegrationEnvelopeV1[HumanAssistedReanalysisRequest],
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> IntegrationEnvelopeV1[CapabilityAnalysisProjectionV1]:
    if not idempotency_key:
        raise APIError(400, "idempotency_key_required", "Idempotency-Key is required.")
    try:
        result = await _service(request).create_human_assisted_reanalysis(
            source_analysis_id=analysis_id,
            evidence_selections=body.data.evidence_selections,
            actor=actor,
            idempotency_key=idempotency_key,
        )
        review = await _service(request).review_projection(result.analysis)
    except KeyError as exc:
        raise APIError(404, "capability_analysis_not_found", "Analysis was not found.") from exc
    except Exception as exc:
        raise _error(exc) from exc
    projected = _projection(result.analysis, review)
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=projected.model_copy(
            update={
                "human_assisted": HumanAssistedAnalysisV1(
                    origin=result.provenance.origin,
                    source_analysis_id=result.provenance.source_analysis_id,
                    evidence_selections=[
                        HumanAssistedSelectionV1.model_validate(item.model_dump(mode="json"))
                        for item in result.provenance.evidence_selections
                    ],
                )
            }
        ),
    )


@router.get(
    "/capability-analyses/{analysis_id}/gaps/{gap_id}/evidence",
    response_model=IntegrationEnvelopeV1[CapabilityEvidenceProjectionV1],
)
async def get_gap_evidence(
    analysis_id: str,
    gap_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CapabilityEvidenceProjectionV1]:
    try:
        portfolio = await _service(request).get(analysis_id, actor)
        items = await _service(request).evidence_for_gap(portfolio, gap_id)
    except KeyError as exc:
        raise APIError(404, "capability_gap_not_found", "Gap was not found.") from exc
    except CapabilityAnalysisAccessDeniedError as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=CapabilityEvidenceProjectionV1(
            analysis_id=analysis_id,
            gap_reference=gap_id,
            items=[
                CapabilityEvidenceItemV1(
                    reference=item.evidence_ref,
                    excerpt=item.source_excerpt,
                    section=item.source_locator.section,
                    start_offset=item.source_locator.start_offset,
                    end_offset=item.source_locator.end_offset,
                    context=item.context,
                    confidence=item.confidence,
                )
                for item in items
                if item.source_locator is not None
            ],
        ),
    )
