from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.authorization.fixtures import REVIEWER_ID
from app.matching.repository import InMemoryPreliminaryMatchRepository
from app.matching.schemas import (
    CriterionDimension,
    CriterionResult,
    CriterionStatus,
    EvidenceAllocation,
    MandatoryStatus,
    PreliminaryMatch,
    PreliminaryMatchStatus,
    PreliminarySkillGap,
    RequirementClassification,
)


def match_fixture() -> PreliminaryMatch:
    return PreliminaryMatch(
        id="match-review-1",
        cv_profile_id="cv-1",
        cv_profile_version=1,
        jd_profile_id="jd-1",
        jd_profile_version=1,
        role_profile_id="role-1",
        role_profile_version="1.0",
        rule_set_version="rules-1",
        policy_version="policy-1",
        actor_id=uuid4(),
        correlation_id=str(uuid4()),
        status=PreliminaryMatchStatus.COMPLETED,
        criterion_results=[
            CriterionResult(
                requirement_id="python",
                criterion_dimension=CriterionDimension.SKILL,
                classification=RequirementClassification.ROLE_CRITICAL,
                status=CriterionStatus.PARTIAL,
                source_evidence=[],
                confidence=0.8,
                mandatory_status=MandatoryStatus.UNRESOLVED,
                recommended_next_assessment="practical",
            )
        ],
        evidence_allocations=[EvidenceAllocation(evidence_id="e-1", requirement_id="python")],
        preliminary_skill_gaps=[
            PreliminarySkillGap(
                requirement_id="python",
                criterion_dimension=CriterionDimension.SKILL,
                status=CriterionStatus.PARTIAL,
                mandatory_status=MandatoryStatus.UNRESOLVED,
                recommended_next_assessment="practical",
            )
        ],
    )


@pytest.mark.asyncio
async def test_reviewer_approval_moves_completed_match_to_reviewed() -> None:
    repository = InMemoryPreliminaryMatchRepository()
    await repository.create(match_fixture())

    reviewed = await repository.review(
        "match-review-1",
        reviewer_id=REVIEWER_ID,
        approved_gap_ids=["python"],
        expected_version=1,
        reviewed_at=datetime.now(UTC),
    )

    assert reviewed.status is PreliminaryMatchStatus.REVIEWED
    assert reviewed.approved_gap_ids == ["python"]
    assert reviewed.reviewed_by == REVIEWER_ID


@pytest.mark.asyncio
async def test_review_rejects_stale_version() -> None:
    repository = InMemoryPreliminaryMatchRepository()
    await repository.create(match_fixture())

    with pytest.raises(ValueError, match="version_conflict"):
        await repository.review(
            "match-review-1",
            reviewer_id=REVIEWER_ID,
            approved_gap_ids=[],
            expected_version=2,
            reviewed_at=datetime.now(UTC),
        )
