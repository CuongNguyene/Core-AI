from datetime import date
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.authorization.schemas import ActorContext, Role
from app.capability_analysis.schemas import (
    AnalysisStatus,
    CombinedGapPortfolio,
    PreliminaryPriority,
    TargetGap,
    TargetGapAnalysis,
    TargetType,
    TargetUsageMode,
)
from app.learning.mapper import map_learning_need_to_objective
from app.learning.repository import InMemoryLearningPathRepository
from app.learning.schemas import (
    CapabilityAnalysisLearningPathRequest,
    LearningObjective,
    LearningPathSourceType,
)
from app.learning.service import LearningPathService
from app.learning_need_profile.schemas import (
    LearnerContext,
    LearningNeedCompetency,
    LearningNeedCurrentState,
    LearningNeedGap,
    LearningNeedProfile,
    LearningNeedProvenance,
    LearningNeedTargetState,
)
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleProfileStatus,
    RoleRequirement,
)

OBJECTIVE_ACTOR_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
OBJECTIVE_ORG_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


class AnalysisReader:
    def __init__(self, source: CombinedGapPortfolio) -> None:
        self.source = source

    async def get(self, analysis_id: str) -> CombinedGapPortfolio | None:
        if analysis_id == self.source.id:
            return self.source
        return None


def capability_analysis() -> CombinedGapPortfolio:
    source_gap = TargetGap(
        id="gap-python",
        target_id="role-1",
        target_type=TargetType.CURRENT_ROLE,
        requirement_id="python",
        matched_evidence_refs=["evidence:python:1"],
        missing_signals=[],
        rationale="Requires Python practice.",
        preliminary_priority=PreliminaryPriority.HIGH,
        missing_priority_inputs=[],
        recommendation="practice-python",
    )
    return CombinedGapPortfolio(
        id="analysis-1",
        cv_profile_id="profile-1",
        cv_profile_version=2,
        current_target_version="1.0",
        owner_actor_id=OBJECTIVE_ACTOR_ID,
        organization_id=OBJECTIVE_ORG_ID,
        correlation_id="analysis-1",
        candidate_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        analysis_status=AnalysisStatus.READY,
        current_role=TargetGapAnalysis(
            target_id="role-1",
            target_type=TargetType.CURRENT_ROLE,
            usage_mode=TargetUsageMode.OFFICIAL,
            assessments=[],
            gaps=[source_gap],
        ),
    )


def learning_need() -> LearningNeedProfile:
    return LearningNeedProfile(
        id="learning-need:analysis-001:gap-python-cleaning",
        candidate_reference=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        target_reference="role-data-analyst@2",
        learner_context=LearnerContext(role=None, experience_level=None),
        competency=LearningNeedCompetency(
            id="cap-python-cleaning", name=None, description=None
        ),
        current_state=LearningNeedCurrentState(
            level=None, evidence_refs=["evidence:cv:page-2"]
        ),
        target_state=LearningNeedTargetState(
            level="3", expected_behaviors=["Handle invalid values in tabular data"]
        ),
        gap=LearningNeedGap(
            type="skill_gap", description="Handle invalid values in tabular data"
        ),
        missing_knowledge=["data_cleaning_depth"],
        learning_constraints={},
        priority=PreliminaryPriority.HIGH,
        confidence=None,
        source_gap_refs=["gap-python-cleaning"],
        provenance=LearningNeedProvenance(
            analysis_id="analysis-001",
            analysis_version=1,
            target_id="role-data-analyst",
            target_version="2",
            source_profile_id="profile-001",
            source_profile_version=4,
            evidence_refs=["evidence:cv:page-2"],
            transformation="learning-need-profile-v1",
        ),
    )


def test_maps_learning_need_to_objective_without_inventing_instructional_metadata() -> None:
    result = map_learning_need_to_objective(learning_need=learning_need(), sequence=1)

    assert isinstance(result, LearningObjective)
    assert result.id == "objective-learning-need:analysis-001:gap-python-cleaning"
    assert result.learning_need_ref == "learning-need:analysis-001:gap-python-cleaning"
    assert result.statement == "Handle invalid values in tabular data"
    assert result.competency_id == "cap-python-cleaning"
    assert result.current_level is None
    assert result.target_level == 3
    assert result.measurable_outcome == "Handle invalid values in tabular data"
    assert result.gap_id == "gap-python-cleaning"
    assert result.sequence == 1
    assert result.bloom_level is None
    assert result.evidence_required is None


def test_existing_learning_objective_constructor_remains_compatible() -> None:
    result = LearningObjective(
        id="objective-python",
        competency_id="python",
        current_level=1,
        target_level=2,
        measurable_outcome="Write functions",
        gap_id="gap-python",
        sequence=1,
    )

    assert result.learning_need_ref is None
    assert result.statement is None
    assert result.bloom_level is None
    assert result.evidence_required is None


def test_mapping_preserves_existing_outcome_when_supplied() -> None:
    result = map_learning_need_to_objective(
        learning_need=learning_need(),
        sequence=1,
        measurable_outcome="Practice handling invalid tabular values with Python.",
    )

    assert result.statement == "Handle invalid values in tabular data"
    assert result.measurable_outcome == "Practice handling invalid tabular values with Python."


def test_missing_evidence_does_not_create_evidence_requirements() -> None:
    source = learning_need().model_copy(
        update={
            "current_state": LearningNeedCurrentState(level=None, evidence_refs=[]),
            "provenance": learning_need().provenance.model_copy(update={"evidence_refs": []}),
        }
    )

    result = map_learning_need_to_objective(learning_need=source, sequence=1)

    assert result.bloom_level is None
    assert result.evidence_required is None


@pytest.mark.asyncio
async def test_capability_analysis_flow_links_objective_to_learning_need() -> None:
    requirement = RoleRequirement(
        id="python",
        criterion_dimension=CriterionDimension.SKILL,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=["python"],
        confidence_threshold=0.7,
        assessment_recommendation="practical",
        rubric_version="rubric-1",
        target_level="1",
    )
    profile = SimpleNamespace(
        id="role-1",
        version="1.0",
        status=RoleProfileStatus.ACTIVE,
        policy_version="policy-1",
        requirements=[requirement],
    )

    class Roles:
        async def get_version(self, *_args):
            return profile

    service = LearningPathService(
        competency_records=None,  # type: ignore[arg-type]
        role_profiles=Roles(),  # type: ignore[arg-type]
        matches=None,  # type: ignore[arg-type]
        paths=InMemoryLearningPathRepository(),
        capability_analyses=AnalysisReader(capability_analysis()),
    )

    result = await service.create_from_capability_analysis(
        actor=ActorContext(
            actor_id=OBJECTIVE_ACTOR_ID,
            organization_id=OBJECTIVE_ORG_ID,
            roles=frozenset({Role.LEARNER}),
        ),
        request=CapabilityAnalysisLearningPathRequest(
            capability_analysis_id="analysis-1",
            development_goal="Become job-ready",
            target_completion_date=date(2026, 12, 1),
        ),
    )

    assert result.source_type is LearningPathSourceType.CAPABILITY_ANALYSIS
    assert result.objectives[0].learning_need_ref == "learning-need:analysis-1:gap-python"
    assert result.objectives[0].statement == "practical"
