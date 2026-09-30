from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.authorization.schemas import ActorContext, Role
from app.competency.repository import InMemoryCompetencyRepository
from app.competency.schemas import CompetencyLevelStatus, CompetencyRecord
from app.learning.errors import LearningPathValidationError
from app.learning.repository import InMemoryLearningPathRepository
from app.learning.schemas import LearningPathRequest
from app.learning.service import LearningPathService
from app.matching.repository import (
    InMemoryPreliminaryMatchRepository,
    InMemoryRoleProfileRepository,
)
from app.matching.schemas import (
    CriterionDimension,
    CriterionResult,
    CriterionStatus,
    MandatoryStatus,
    PreliminaryMatch,
    PreliminaryMatchStatus,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)

ORG_ID = uuid4()
SUBJECT_ID = uuid4()


def actor() -> ActorContext:
    return ActorContext(
        actor_id=SUBJECT_ID, organization_id=ORG_ID, roles=frozenset({Role.LEARNER})
    )


def target_profile() -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id="role-1",
        version="1.0",
        status=RoleProfileStatus.ACTIVE,
        source_jd_profile_id="jd-1",
        source_jd_profile_version=1,
        rule_set_version="rules-1",
        policy_version="policy-1",
        requirements=[
            RoleRequirement(
                id="python",
                criterion_dimension=CriterionDimension.SKILL,
                classification=RequirementClassification.ROLE_CRITICAL,
                evidence_terms=["python"],
                confidence_threshold=0.7,
                assessment_recommendation="practical",
                rubric_version="rubric-1",
            )
        ],
    )


def reviewed_match(confidence: float = 0.9) -> PreliminaryMatch:
    return PreliminaryMatch(
        id="match-1",
        cv_profile_id="cv-1",
        cv_profile_version=1,
        jd_profile_id="jd-1",
        jd_profile_version=1,
        role_profile_id="role-1",
        role_profile_version="1.0",
        rule_set_version="rules-1",
        policy_version="policy-1",
        actor_id=SUBJECT_ID,
        correlation_id="corr-1",
        status=PreliminaryMatchStatus.REVIEWED,
        criterion_results=[
            CriterionResult(
                requirement_id="python",
                criterion_dimension=CriterionDimension.SKILL,
                classification=RequirementClassification.ROLE_CRITICAL,
                status=CriterionStatus.PARTIAL,
                source_evidence=[],
                confidence=confidence,
                mandatory_status=MandatoryStatus.UNRESOLVED,
                recommended_next_assessment="practical",
            )
        ],
        evidence_allocations=[],
        preliminary_skill_gaps=[],
        approved_gap_ids=["python"],
        reviewed_by=uuid4(),
        reviewed_at=datetime.now(UTC),
        version=2,
    )


def verified_record(
    status: CompetencyLevelStatus = CompetencyLevelStatus.VERIFIED,
) -> CompetencyRecord:
    return CompetencyRecord(
        id=uuid4(),
        subject_id=SUBJECT_ID,
        organization_id=ORG_ID,
        competency_id="python",
        status=status,
        level=1,
        version=1,
        valid_until=datetime.now(UTC) + timedelta(days=180),
        reassessment_due_at=datetime.now(UTC) + timedelta(days=120),
    )


def request(record_id) -> LearningPathRequest:
    return LearningPathRequest(
        subject_id=SUBJECT_ID,
        target_profile_id="role-1",
        target_profile_version="1.0",
        preliminary_match_id="match-1",
        verified_competency_record_ids=[record_id],
        approved_gap_ids=["python"],
        development_goal="Become job-ready",
        target_completion_date=date(2026, 12, 1),
        correlation_id="corr-learning-1",
    )


def service(record: CompetencyRecord, match: PreliminaryMatch) -> LearningPathService:
    return LearningPathService(
        competency_records=InMemoryCompetencyRepository([record]),
        role_profiles=InMemoryRoleProfileRepository([target_profile()]),
        matches=InMemoryPreliminaryMatchRepositoryWithMatch(match),
        paths=InMemoryLearningPathRepository(),
    )


class InMemoryPreliminaryMatchRepositoryWithMatch(InMemoryPreliminaryMatchRepository):
    def __init__(self, match: PreliminaryMatch) -> None:
        super().__init__()
        self._matches[match.id] = match


@pytest.mark.asyncio
async def test_learning_path_requires_verified_competency_and_reviewed_gap() -> None:
    record = verified_record()
    path = await service(record, reviewed_match()).create(actor=actor(), request=request(record.id))

    assert path.subject_id == SUBJECT_ID
    assert path.organization_id == ORG_ID
    assert path.approved_gap_ids == ["python"]


@pytest.mark.asyncio
async def test_learning_path_rejects_unverified_competency() -> None:
    record = verified_record(CompetencyLevelStatus.ASSESSED)

    with pytest.raises(LearningPathValidationError, match="verified"):
        await service(record, reviewed_match()).create(actor=actor(), request=request(record.id))


@pytest.mark.asyncio
async def test_learning_path_rejects_low_confidence_gap() -> None:
    record = verified_record()

    with pytest.raises(LearningPathValidationError, match="confidence"):
        await service(record, reviewed_match(confidence=0.4)).create(
            actor=actor(), request=request(record.id)
        )
