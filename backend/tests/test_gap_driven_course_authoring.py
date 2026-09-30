from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.authorization.schemas import ActorContext
from app.capability_analysis.schemas import PreliminaryPriority
from app.course_authoring.gap_driven_composer import (
    GapDrivenTrainingBriefComposer,
    GapDrivenTrainingBriefProjectionResult,
)
from app.course_authoring.repository import InMemoryCourseAuthoringRepository
from app.course_authoring.schemas import (
    AudienceSnapshot,
    AudienceSnapshotSource,
    CourseAuthoringMode,
    CourseAuthoringStatus,
)
from app.course_authoring.service import CourseAuthoringService
from app.learning_need_profile.schemas import (
    LearnerContext,
    LearningNeedCompetency,
    LearningNeedCurrentState,
    LearningNeedEligibility,
    LearningNeedGap,
    LearningNeedProfile,
    LearningNeedProvenance,
    LearningNeedResolution,
    LearningNeedTargetState,
)

CANDIDATE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ACTOR_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def actor() -> ActorContext:
    return ActorContext(actor_id=ACTOR_ID, organization_id=CANDIDATE_ID, roles=frozenset())


def need(
    *,
    gap_id: str,
    eligibility: LearningNeedEligibility,
    resolution: LearningNeedResolution,
    competency_id: str,
    usage_mode: str = "preview",
) -> LearningNeedProfile:
    return LearningNeedProfile(
        id=f"learning-need:analysis-1:{gap_id}",
        candidate_reference=CANDIDATE_ID,
        target_reference="role-1@3",
        learner_context=LearnerContext(role=None, experience_level=None),
        competency=LearningNeedCompetency(id=competency_id, name=None, description=None),
        current_state=LearningNeedCurrentState(level=None, evidence_refs=[f"evidence:{gap_id}"]),
        target_state=LearningNeedTargetState(
            level="3", expected_behaviors=[f"behavior-{gap_id}"]
        ),
        gap=LearningNeedGap(type="skill_gap", description=f"gap-{gap_id}"),
        missing_knowledge=[],
        learning_constraints={},
        priority=PreliminaryPriority.HIGH,
        confidence=None,
        source_gap_refs=[gap_id],
        provenance=LearningNeedProvenance(
            analysis_id="analysis-1",
            analysis_version=2,
            target_id="role-1",
            target_version="3",
            source_profile_id="profile-1",
            source_profile_version=4,
            evidence_refs=[f"evidence:{gap_id}"],
            transformation="learning-need-profile-v1",
        ),
        assessment_status="insufficient",
        requirement_reference=competency_id,
        learning_eligibility=eligibility,
        resolution_type=resolution,
        usage_mode=usage_mode,
        warning_codes=["source_capability_analysis_preview"]
        if usage_mode == "preview"
        else [],
        projection_reason_code="test_reason",
    )


def eligible_result() -> GapDrivenTrainingBriefProjectionResult:
    return GapDrivenTrainingBriefComposer().compose(
        [
            need(
                gap_id="sql",
                eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
                resolution=LearningNeedResolution.LEARNING,
                competency_id="cap-sql",
            ),
            need(
                gap_id="degree",
                eligibility=LearningNeedEligibility.NEEDS_VERIFICATION,
                resolution=LearningNeedResolution.VERIFICATION,
                competency_id="degree",
            ),
            need(
                gap_id="pmp",
                eligibility=LearningNeedEligibility.UNRESOLVED,
                resolution=LearningNeedResolution.CREDENTIAL,
                competency_id="pmp",
            ),
            need(
                gap_id="production",
                eligibility=LearningNeedEligibility.UNRESOLVED,
                resolution=LearningNeedResolution.EXPERIENCE_EXPOSURE,
                competency_id="production",
            ),
            need(
                gap_id="power-bi",
                eligibility=LearningNeedEligibility.EVIDENCE_MISSING,
                resolution=LearningNeedResolution.VERIFICATION,
                competency_id="power-bi",
            ),
        ]
    )


def empty_result() -> GapDrivenTrainingBriefProjectionResult:
    result = GapDrivenTrainingBriefComposer().compose(
        [
            need(
                gap_id="missing",
                eligibility=LearningNeedEligibility.EVIDENCE_MISSING,
                resolution=LearningNeedResolution.VERIFICATION,
                competency_id="missing",
            )
        ]
    )
    assert result.training_brief is None
    return result


class RecordingAuthoringService:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ActorContext]] = []

    async def create(self, body: object, actor_context: ActorContext) -> object:
        self.calls.append((body, actor_context))
        return SimpleNamespace(
            request_id="course-authoring-request-test",
            status=CourseAuthoringStatus.DRAFT,
            audience_snapshot_id="audience-snapshot-test",
        )


class ValidReferences:
    async def get_learning_need(self, artifact_id: str, _actor: ActorContext) -> object:
        return SimpleNamespace(id=artifact_id)

    async def get_learning_objective(self, artifact_id: str, _actor: ActorContext) -> object:
        return SimpleNamespace(id=artifact_id, learning_need_ref="learning-need:analysis-1:sql")

    async def get_instructional_blueprint(
        self, artifact_id: str, _actor: ActorContext
    ) -> object:
        return SimpleNamespace(
            id=artifact_id,
            objective_refs=[],
            learning_need_ref="learning-need:analysis-1:sql",
        )


class PipelineReferences(ValidReferences):
    async def get_learning_objective(self, artifact_id: str, _actor: ActorContext) -> object:
        from app.learning_authoring.schemas import LearningObjectiveProjection

        return LearningObjectiveProjection(
            id=artifact_id,
            learning_need_ref="learning-need:analysis-1:sql",
            statement="Develop SQL capability",
            bloom_level=None,
            evidence_required=None,
            competency_id="cap-sql",
            current_level=None,
            target_level=3,
            measurable_outcome="behavior-sql",
            gap_id="sql",
            sequence=1,
        )


def test_valid_projection_maps_to_gap_driven_request_without_resolution_actions() -> None:
    from app.course_authoring.gap_driven_request import GapDrivenCourseAuthoringAdapter

    request = GapDrivenCourseAuthoringAdapter().to_request(eligible_result())

    assert request.mode is CourseAuthoringMode.GAP_DRIVEN
    assert request.learning_need_refs == ("learning-need:analysis-1:sql",)
    assert request.objective_refs == ("objective-learning-need:analysis-1:sql",)
    assert request.training_brief.desired_outcomes == ("behavior-sql",)
    assert request.constraints["source_usage_mode"] == "preview"
    assert request.constraints["gap_driven_training_brief_policy"] == "gap_driven_training_brief@0.1"
    for excluded in ("degree", "pmp", "production", "power-bi"):
        assert excluded not in request.training_brief.goal
        assert excluded not in request.learning_need_refs


def test_adapter_fails_closed_when_training_brief_is_absent() -> None:
    from app.course_authoring.gap_driven_request import GapDrivenCourseAuthoringAdapter

    with pytest.raises(ValueError, match="gap_driven_training_brief_required"):
        GapDrivenCourseAuthoringAdapter().to_request(empty_result())


@pytest.mark.asyncio
async def test_empty_projection_does_not_call_course_authoring_service() -> None:
    from app.course_authoring.gap_driven_request import GapDrivenCourseAuthoringIntegration

    service = RecordingAuthoringService()
    result = await GapDrivenCourseAuthoringIntegration(service).create(empty_result(), actor())

    assert result.request_created is False
    assert result.reason_code == "no_learning_eligible_needs"
    assert service.calls == []


@pytest.mark.asyncio
async def test_eligible_projection_uses_existing_service_and_preserves_preview_boundary() -> None:
    from app.course_authoring.gap_driven_request import GapDrivenCourseAuthoringIntegration

    service = RecordingAuthoringService()
    result = await GapDrivenCourseAuthoringIntegration(service).create(eligible_result(), actor())

    assert result.request_created is True
    assert len(service.calls) == 1
    request, called_actor = service.calls[0]
    assert called_actor == actor()
    assert request.mode is CourseAuthoringMode.GAP_DRIVEN
    assert request.constraints["source_usage_mode"] == "preview"
    assert request.constraints["official_training_assignment"] == "false"
    assert request.learning_need_refs == ("learning-need:analysis-1:sql",)


@pytest.mark.asyncio
async def test_eligible_projection_is_accepted_by_existing_course_authoring_service() -> None:
    from app.course_authoring.gap_driven_request import GapDrivenCourseAuthoringIntegration

    authoring = CourseAuthoringService(
        repository=InMemoryCourseAuthoringRepository(),
        references=ValidReferences(),
    )
    result = await GapDrivenCourseAuthoringIntegration(authoring).create(
        eligible_result(), actor()
    )

    assert result.request_created is True
    assert result.accepted is not None
    assert result.accepted.status is CourseAuthoringStatus.DRAFT
    request = await authoring.get(result.accepted.request_id, actor())
    assert request.mode is CourseAuthoringMode.GAP_DRIVEN
    assert request.learning_need_refs == ("learning-need:analysis-1:sql",)


@pytest.mark.asyncio
async def test_gap_driven_request_reaches_existing_curriculum_planning_pipeline() -> None:
    from app.content_generation.repository import InMemoryContentGenerationRepository
    from app.course_authoring.gap_driven_request import GapDrivenCourseAuthoringIntegration
    from app.course_generation.context import CourseGenerationContextBuilder
    from app.curriculum_planning.planner import DeterministicCurriculumPlanner
    from app.curriculum_planning.service import CurriculumPlanningService

    authoring = CourseAuthoringService(
        repository=InMemoryCourseAuthoringRepository(),
        references=PipelineReferences(),
    )
    created = await GapDrivenCourseAuthoringIntegration(authoring).create(
        eligible_result(), actor()
    )
    assert created.accepted is not None

    planning = CurriculumPlanningService(
        authoring=authoring,
        context_builder=CourseGenerationContextBuilder(PipelineReferences()),
        planner=DeterministicCurriculumPlanner(),
        repository=InMemoryContentGenerationRepository(),
    )
    plan = await planning.plan(created.accepted.request_id, actor())

    assert plan.authoring_request_ref == created.accepted.request_id
    assert plan.learning_objectives[0].statement == "Develop SQL capability"
    assert len(plan.modules) == 1
    assert plan.modules[0].lessons[0].title == "Develop SQL capability"


@pytest.mark.asyncio
async def test_gap_driven_planning_derives_objective_from_learning_need_when_omitted() -> None:
    from app.course_authoring.schemas import CourseAuthoringRequest
    from app.course_generation.context import CourseGenerationContextBuilder

    request = CourseAuthoringRequest(
        id="course-authoring-request-learning-need-only",
        title="Python foundations",
        training_brief=eligible_result().training_brief,
        audience_snapshot=AudienceSnapshot(
            id="audience-test",
            learner_refs=(),
            learner_count=0,
            captured_at=datetime.now(UTC),
            source=AudienceSnapshotSource.MANUAL_SELECTION,
            metadata={},
        ),
        learning_need_refs=("learning-need:analysis-1:sql",),
        objective_refs=(),
        constraints={},
        mode=CourseAuthoringMode.GAP_DRIVEN,
        status=CourseAuthoringStatus.DRAFT,
        created_by_actor_ref=actor().actor_id,
        created_at=datetime.now(UTC),
    )

    context = await CourseGenerationContextBuilder(PipelineReferences()).build(
        request, actor()
    )

    assert [item.id for item in context.learning_objectives] == [
        "objective-learning-need:analysis-1:sql"
    ]


def test_adapter_mapping_is_deterministic_and_contains_no_raw_artifacts() -> None:
    from app.course_authoring.gap_driven_request import GapDrivenCourseAuthoringAdapter

    first = GapDrivenCourseAuthoringAdapter().to_request(eligible_result())
    second = GapDrivenCourseAuthoringAdapter().to_request(eligible_result())

    assert first == second
    payload = first.model_dump_json()
    for forbidden in ("raw CV", "raw JD", "provider response", "prompt"):
        assert forbidden not in payload
