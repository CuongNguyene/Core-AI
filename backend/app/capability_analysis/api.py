from typing import cast

from fastapi import APIRouter, Depends, Request, status

from app.capability_analysis.errors import (
    CapabilityAnalysisAccessDeniedError,
    CurrentTargetNotUsableError,
    ExtractionProfileNotAcceptedError,
    FutureTargetNotUsableError,
    SemanticPolicyNotConfiguredError,
    SemanticPolicyUnavailableError,
    SupersededCapabilityProfileError,
)
from app.capability_analysis.schemas import CombinedGapPortfolio, CreateCapabilityGapAnalysisRequest
from app.capability_analysis.service import CapabilityGapAnalysisService
from app.extraction.auth import DevelopmentActor, get_development_actor
from app.shared.errors import APIError

router = APIRouter(tags=["capability-analysis"])


def _service(request: Request) -> CapabilityGapAnalysisService:
    service = getattr(request.app.state, "capability_gap_analysis_service", None)
    if service is None:
        raise APIError(503, "capability_gap_unavailable", "Capability analysis is not ready.")
    return cast(CapabilityGapAnalysisService, service)


@router.post(
    "/capability-gap-portfolios",
    response_model=CombinedGapPortfolio,
    status_code=status.HTTP_201_CREATED,
)
async def create_capability_gap_portfolio(
    body: CreateCapabilityGapAnalysisRequest,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CombinedGapPortfolio:
    try:
        return await _service(request).create(body, actor)
    except (ExtractionProfileNotAcceptedError, SupersededCapabilityProfileError) as exc:
        raise APIError(
            409,
            "capability_gap_input_not_accepted",
            "Capability analysis requires an accepted current CV profile.",
        ) from exc
    except CurrentTargetNotUsableError as exc:
        raise APIError(
            409,
            "current_target_not_usable",
            "The current role target is not usable for capability analysis.",
        ) from exc
    except FutureTargetNotUsableError as exc:
        raise APIError(
            409,
            "future_target_not_usable",
            "The future role target is not usable for capability analysis.",
        ) from exc
    except SemanticPolicyNotConfiguredError as exc:
        raise APIError(
            409,
            "semantic_policy_not_configured",
            "Semantic policy is not configured for this role profile version.",
        ) from exc
    except SemanticPolicyUnavailableError as exc:
        raise APIError(
            409,
            "semantic_policy_unavailable",
            "A referenced semantic policy pack is unavailable.",
        ) from exc
    except CapabilityAnalysisAccessDeniedError as exc:
        raise APIError(
            403, "capability_gap_access_denied", "Capability analysis access is denied."
        ) from exc


@router.get(
    "/capability-gap-portfolios/{portfolio_id}",
    response_model=CombinedGapPortfolio,
)
async def get_capability_gap_portfolio(
    portfolio_id: str,
    request: Request,
    actor: DevelopmentActor = Depends(get_development_actor),
) -> CombinedGapPortfolio:
    try:
        return await _service(request).get(portfolio_id, actor)
    except KeyError as exc:
        raise APIError(
            404, "capability_gap_not_found", "Capability gap portfolio was not found."
        ) from exc
    except CapabilityAnalysisAccessDeniedError as exc:
        raise APIError(
            403, "capability_gap_access_denied", "Capability analysis access is denied."
        ) from exc
