import pytest

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.schemas import ReviewState
from app.matching.errors import (
    ExtractionProfileNotAcceptedError,
    PreliminaryMatchAccessDeniedError,
    RoleProfileNotActiveError,
    SupersededInputError,
)
from app.matching.repository import (
    InMemoryPreliminaryMatchRepository,
    InMemoryRoleProfileRepository,
)
from app.matching.service import PreliminaryMatchService
from tests.test_extraction_repository import pending_profile, queued_job
from tests.test_matching_repository import active_role


async def service_with_profile(
    state: ReviewState,
) -> tuple[
    PreliminaryMatchService,
    InMemoryExtractionRepository,
    InMemoryPreliminaryMatchRepository,
]:
    extraction = InMemoryExtractionRepository()
    await extraction.enqueue(queued_job())
    profile = pending_profile().model_copy(update={"review_state": state})
    if state is ReviewState.ACCEPTED:
        profile = profile.model_copy(
            update={
                "accepted_by": "reviewer-1",
                "accepted_at": __import__("datetime").datetime.now(__import__("datetime").UTC),
            }
        )
    await extraction.mark_succeeded("job-1", profile)
    matches = InMemoryPreliminaryMatchRepository()
    return (
        PreliminaryMatchService(
            extraction,
            InMemoryRoleProfileRepository([active_role()]),
            matches,
        ),
        extraction,
        matches,
    )


@pytest.mark.asyncio
async def test_service_rejects_unaccepted_cv_without_router() -> None:
    service, _, matches = await service_with_profile(ReviewState.PENDING_REVIEW)
    with pytest.raises(ExtractionProfileNotAcceptedError):
        await service.create("profile-1", "role-ai-engineer", LEARNER_ID, "corr-1")
    assert matches.audit_events[-1]["action"] == "MATCHING_REJECTED_INPUT_NOT_ACCEPTED"


@pytest.mark.asyncio
async def test_service_rejects_inactive_role_without_router() -> None:
    service, _, _ = await service_with_profile(ReviewState.ACCEPTED)
    with pytest.raises(RoleProfileNotActiveError):
        await service.create("profile-1", "missing-role", LEARNER_ID, "corr-1")


@pytest.mark.asyncio
async def test_service_rejects_superseded_cv_profile_without_router() -> None:
    service, extraction, _ = await service_with_profile(ReviewState.ACCEPTED)
    await extraction.create_correction("profile-1", REVIEWER_ID, pending_profile().output)

    with pytest.raises(SupersededInputError):
        await service.create("profile-1", "role-ai-engineer", LEARNER_ID, "corr-1")


@pytest.mark.asyncio
async def test_service_rejects_actor_who_does_not_own_cv_profile() -> None:
    service, _, _ = await service_with_profile(ReviewState.ACCEPTED)

    with pytest.raises(PreliminaryMatchAccessDeniedError):
        await service.create("profile-1", "role-ai-engineer", REVIEWER_ID, "corr-1")
