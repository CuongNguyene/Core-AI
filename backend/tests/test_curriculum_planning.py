from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.content_generation.prompts import (
    CURRICULUM_PLANNING_HISTORICAL_VERSIONS,
    MICROLEARNING_CURRICULUM_PLANNING_PROMPT_VERSION,
    curriculum_planning_prompt_template,
)
from app.content_generation.repository import InMemoryContentGenerationRepository
from app.content_generation.schemas import (
    CurriculumPlanningAttempt,
    CurriculumPlanningAttemptStatus,
)
from app.course_authoring.brief_revision_repository import InMemoryAuthoringBriefRevisionRepository
from app.course_authoring.brief_revision_schemas import (
    AuthoringBriefRevision,
    AuthoringBriefRevisionStatus,
    BriefRevisionPayload,
)
from app.course_authoring.schemas import (
    AudienceSnapshot,
    AudienceSnapshotSource,
    CourseAuthoringMode,
    CourseAuthoringRequest,
    CourseAuthoringStatus,
    TrainingBrief,
)
from app.curriculum_planning.duration import (
    DurationUnit,
    WeeklyEffortSource,
    normalize_training_duration,
)
from app.curriculum_planning.microlearning import (
    MICROLEARNING_POLICY_VERSION,
    parse_expected_learning_effort_hours,
)
from app.curriculum_planning.planner import (
    CurriculumPlanningCandidateValidationError,
    DeterministicCurriculumPlanner,
    ModelGatewayCurriculumPlanner,
    _finalize_curriculum_plan,
)
from app.curriculum_planning.policy import CurriculumScopePolicy
from app.curriculum_planning.revision import (
    CURRICULUM_REVIEW_WORKFLOW_VERSION,
    apply_curriculum_patch,
    validate_patch_scope,
    validate_revised_plan,
)
from app.curriculum_planning.schemas import (
    CurriculumLessonPlan,
    CurriculumModulePlan,
    CurriculumObjective,
    CurriculumPlan,
    CurriculumPlanningContext,
    CurriculumPlanningOutput,
    NormalizedTrainingDuration,
)
from app.curriculum_planning.service import CurriculumPlanningService
from app.curriculum_planning.validation import (
    CurriculumPlanValidationError,
    collect_curriculum_plan_validation,
    replay_curriculum_planning_attempt,
    validate_curriculum_plan,
)
from app.curriculum_planning.workload import (
    allocate_curriculum_plan_workload,
    representable_effort_range,
)


def request(*, duration: str | None, mode: CourseAuthoringMode = CourseAuthoringMode.GOAL_DRIVEN) -> CourseAuthoringRequest:
    return CourseAuthoringRequest(
        id="request-planning-001",
        title="Python Backend Developer",
        training_brief=TrainingBrief(
            goal="Build production-ready backend engineering capability",
            duration_constraint=duration,
            language="en",
        ),
        audience_snapshot=AudienceSnapshot(
            id="audience-001",
            learner_refs=("learner-1", "learner-2"),
            learner_count=2,
            captured_at=datetime.now(UTC),
            source=AudienceSnapshotSource.MANUAL_SELECTION,
        ),
        mode=mode,
        status=CourseAuthoringStatus.DRAFT,
        created_by_actor_ref=UUID("11111111-1111-1111-1111-111111111111"),
        created_at=datetime.now(UTC),
    )


def small_plan(*, lessons: int = 2, modules: int = 1) -> CurriculumPlan:
    objective = CurriculumObjective(
        id="goal-driven-objective:request-planning-001:001",
        statement="Build production-ready backend engineering capability",
        measurable_outcome="Deliver a tested backend service that meets defined acceptance criteria.",
        sequence=1,
        origin="GOAL_DRIVEN_TRAINING_BRIEF",
    )
    module_plans = [
        CurriculumModulePlan(
            id=f"curriculum-module:{index}",
            title=f"Backend module {index}",
            order=index,
            objective_refs=[objective.id],
            estimated_hours=lessons / modules,
            lessons=[
                CurriculumLessonPlan(
                    id=f"curriculum-lesson:{index}:{lesson_index}",
                    title=f"Backend skill {lesson_index}",
                    order=lesson_index,
                    objective_refs=[objective.id],
                    estimated_minutes=60,
                    lesson_type="skill_practice",
                )
                for lesson_index in range(1, lessons // modules + 1)
            ],
        )
        for index in range(1, modules + 1)
    ]
    return CurriculumPlan(
        id="curriculum-plan:001",
        authoring_request_ref="request-planning-001",
        version=1,
        supersedes_plan_ref=None,
        course_title="Python Backend Developer",
        course_description="A structured backend engineering curriculum.",
        normalized_duration=NormalizedTrainingDuration(
            original="12 months",
            duration_value=12,
            duration_unit=DurationUnit.MONTHS,
            estimated_total_weeks=52,
            weekly_effort_hours=3,
            weekly_effort_source=WeeklyEffortSource.DEFAULT,
            estimated_total_learning_hours=156,
        ),
        learning_objectives=[objective],
        modules=module_plans,
        estimated_total_learning_hours=lessons,
        planning_metadata={"policy_version": "sep-02.3-v1"},
    )


def test_normalizes_explicit_months_and_marks_default_effort() -> None:
    normalized = normalize_training_duration("12 months")

    assert normalized.duration_value == 12
    assert normalized.duration_unit is DurationUnit.MONTHS
    assert normalized.estimated_total_weeks == 52
    assert normalized.weekly_effort_hours == 3
    assert normalized.weekly_effort_source is WeeklyEffortSource.DEFAULT
    assert normalized.estimated_total_learning_hours == 156


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        ("6 months", DurationUnit.MONTHS),
        ("3w", DurationUnit.WEEKS),
        ("2d", DurationUnit.DAYS),
        ("2h", DurationUnit.HOURS),
        ("40 hours", DurationUnit.HOURS),
    ],
)
def test_normalizes_supported_duration_formats(value: str, unit: DurationUnit) -> None:
    assert normalize_training_duration(value).duration_unit is unit


def test_microlearning_effort_is_not_derived_from_long_horizon() -> None:
    horizon = normalize_training_duration("12 months")

    assert parse_expected_learning_effort_hours("36 hours") == 36
    assert horizon.estimated_total_learning_hours == 156
    assert MICROLEARNING_POLICY_VERSION == "sep-08b-v1"


def test_microlearning_envelope_rejects_thirty_six_hour_twelve_unit_shape() -> None:
    plan = small_plan(lessons=12, modules=4).model_copy(update={
        "estimated_total_learning_hours": 36,
        "planning_metadata": {"planning_strategy": MICROLEARNING_POLICY_VERSION},
    })

    envelope = representable_effort_range(plan)

    assert envelope.minimum_minutes > 0
    assert envelope.maximum_minutes == 720
    assert envelope.maximum_minutes < 36 * 60 * 0.8


def test_nonrepresentable_target_is_rejected_before_workload_allocation() -> None:
    plan = small_plan(lessons=12, modules=4).model_copy(update={
        "estimated_total_learning_hours": 36,
        "planning_metadata": {"planning_strategy": MICROLEARNING_POLICY_VERSION},
    })

    with pytest.raises(CurriculumPlanValidationError) as raised:
        _finalize_curriculum_plan(plan, policy=CurriculumScopePolicy())

    issue = next(item for item in raised.value.report.issues if item.code == "candidate_effort_not_representable")
    assert issue.actual == {"minimum_minutes": 360, "maximum_minutes": 720}
    assert issue.expected == {"target_minutes": 2160, "allowed_min_minutes": 1728, "allowed_max_minutes": 2592}


def test_representable_microlearning_shape_preserves_target_through_allocation() -> None:
    plan = small_plan(lessons=36, modules=4).model_copy(update={
        "estimated_total_learning_hours": 36,
        "planning_metadata": {"planning_strategy": MICROLEARNING_POLICY_VERSION},
    })

    finalized = _finalize_curriculum_plan(plan, policy=CurriculumScopePolicy())

    assert sum(module.estimated_hours for module in finalized.modules) == 36
    assert sum(lesson.estimated_minutes for module in finalized.modules for lesson in module.lessons) == 36 * 60


def test_microlearning_scope_bounds_ignore_horizon() -> None:
    policy = CurriculumScopePolicy()

    bounds = policy.bounds_for(
        normalize_training_duration("12 months"), strategy="sep-08b-v1"
    )

    assert bounds.minimum_modules == 1
    assert bounds.maximum_modules == 8
    assert bounds.minimum_lessons == 1
    assert bounds.maximum_lessons == 100


def test_microlearning_gateway_payload_separates_horizon_and_effort() -> None:
    context = CurriculumPlanningContext(
        authoring_request_ref="request-microlearning",
        mode=CourseAuthoringMode.GOAL_DRIVEN,
        course_title="Focused backend skills",
        training_goal="Build a backend service",
        audience_summary={"learner_count": 1},
        duration=normalize_training_duration("12 months"),
        learning_horizon="12 months",
        expected_learning_effort="36 hours",
        planning_strategy=MICROLEARNING_POLICY_VERSION,
    )
    planner = ModelGatewayCurriculumPlanner(
        gateway=SimpleNamespace(), requested_provider="fake", correlation_id="micro"
    )

    payload = planner._planning_payload(context)

    assert payload["learning_horizon"] == "12 months"
    assert payload["expected_learning_effort"] == "36 hours"
    assert payload["estimated_total_learning_hours"] == 36
    assert payload["required_scope"] == {
        "modules": {"min": 1, "max": 8},
        "lessons": {"min": 1, "max": 100},
    }
    assert payload["target_learning_effort_minutes"] == 2160
    assert payload["workload_policy"]["concept"] == {
        "minimum_minutes": 20,
        "maximum_minutes": 30,
    }
    assert "representable" in payload["representability_guidance"]


def test_microlearning_prompt_contract_is_scope_first_and_ref_safe() -> None:
    prompt = curriculum_planning_prompt_template(
        MICROLEARNING_CURRICULUM_PLANNING_PROMPT_VERSION
    )

    text = f"{prompt.system_instruction} {prompt.user_instruction}"
    assert "learning horizon is a pacing window" in text.lower()
    assert "never put an objective statement" in text
    assert "foundation, concept, applied, practice, integration, assessment, capstone" in text
    assert "enough focused units" in text


def test_microlearning_allocator_keeps_units_in_minutes() -> None:
    plan = small_plan(lessons=2, modules=1).model_copy(update={
        "estimated_total_learning_hours": 2,
        "planning_metadata": {"planning_strategy": MICROLEARNING_POLICY_VERSION},
    })

    allocated = allocate_curriculum_plan_workload(plan)

    assert all(lesson.estimated_minutes <= 60 for lesson in allocated.modules[0].lessons)
    assert all(lesson.estimated_minutes >= 30 for lesson in allocated.modules[0].lessons)


def test_curriculum_revision_updates_immutable_copy_and_preserves_source() -> None:
    source = small_plan(lessons=2, modules=1).model_copy(update={
        "planning_metadata": {
            "planning_strategy": MICROLEARNING_POLICY_VERSION,
            "curriculum_review_workflow_version": CURRICULUM_REVIEW_WORKFLOW_VERSION,
        },
    })
    target = source.modules[0].lessons[0].id
    revised = apply_curriculum_patch(source, [{
        "op": "UPDATE_UNIT_EFFORT",
        "target_ref": target,
        "fields": {"estimated_minutes": 45},
    }])
    assert source.modules[0].lessons[0].estimated_minutes != 45
    assert revised.modules[0].lessons[0].estimated_minutes == 45
    validate_revised_plan(revised)


def test_curriculum_revision_rejects_scope_expansion() -> None:
    brief = BriefRevisionPayload(
        training_goal="Build backend services",
        desired_outcomes=("Build REST APIs",),
    )
    with pytest.raises(ValueError, match="SCOPE_EXPANSION_REQUIRES_BRIEF_REVISION"):
        validate_patch_scope([{
            "op": "ADD_UNIT",
            "target_ref": "new",
            "fields": {"title": "Kubernetes deployment"},
        }], brief)


def test_curriculum_revision_rejects_out_of_range_microlearning_unit() -> None:
    source = small_plan(lessons=2, modules=1).model_copy(update={
        "planning_metadata": {"planning_strategy": MICROLEARNING_POLICY_VERSION},
    })
    target = source.modules[0].lessons[0].id
    revised = apply_curriculum_patch(source, [{
        "op": "UPDATE_UNIT_EFFORT",
        "target_ref": target,
        "fields": {"estimated_minutes": 240},
    }])
    with pytest.raises(ValueError, match="curriculum_revision_invalid"):
        validate_revised_plan(revised)


def test_explicit_weekly_effort_is_distinguished_from_default() -> None:
    normalized = normalize_training_duration("12 months", weekly_effort_hours=6)

    assert normalized.weekly_effort_hours == 6
    assert normalized.weekly_effort_source is WeeklyEffortSource.USER_PROVIDED
    assert normalized.estimated_total_learning_hours == 312


def test_unsupported_duration_is_preserved_but_not_parsed() -> None:
    normalized = normalize_training_duration("as long as needed")

    assert normalized.original == "as long as needed"
    assert normalized.duration_value is None
    assert normalized.estimated_total_weeks is None
    assert normalized.estimated_total_learning_hours is None


def test_scope_policy_rejects_legacy_three_module_six_lesson_year_plan() -> None:
    policy = CurriculumScopePolicy()
    bounds = policy.bounds_for(normalize_training_duration("12 months"))

    assert bounds.minimum_modules >= 5
    assert bounds.minimum_lessons >= 18
    with pytest.raises(CurriculumPlanValidationError, match="under_scoped"):
        validate_curriculum_plan(small_plan(), policy=policy)


def test_scope_policy_accepts_a_longer_plan_with_objective_coverage() -> None:
    plan = small_plan(lessons=40, modules=8)

    validate_curriculum_plan(plan, policy=CurriculumScopePolicy())


def test_unknown_objective_reference_is_rejected() -> None:
    plan = small_plan(lessons=2, modules=1)
    lesson = plan.modules[0].lessons[0].model_copy(update={"objective_refs": ["unknown"]})
    updated_module = plan.modules[0].model_copy(update={"lessons": [lesson, plan.modules[0].lessons[1]]})
    invalid = plan.model_copy(update={"modules": [updated_module]})

    with pytest.raises(CurriculumPlanValidationError, match="unknown_objective"):
        validate_curriculum_plan(invalid, policy=None)


def test_validator_reports_all_scope_reference_and_coverage_failures() -> None:
    plan = small_plan(lessons=6, modules=3)
    invalid_modules = [
        module.model_copy(update={
            "lessons": [
                lesson.model_copy(update={"objective_refs": ["unknown-objective"]})
                for lesson in module.lessons
            ]
        })
        for module in plan.modules
    ]
    invalid = plan.model_copy(update={"modules": invalid_modules})

    report = collect_curriculum_plan_validation(invalid, policy=CurriculumScopePolicy())

    assert report.valid is False
    assert set(report.issue_codes) >= {
        "module_count_out_of_bounds",
        "lesson_count_out_of_bounds",
        "unknown_objective_ref",
        "objective_not_covered",
    }
    assert report.module_count == 3
    assert report.lesson_count == 6
    assert report.uncovered_objective_refs == [
        "goal-driven-objective:request-planning-001:001"
    ]
    assert report.unknown_objective_refs == ["unknown-objective"]


@pytest.mark.asyncio
async def test_failed_planning_attempt_is_recoverable_without_becoming_an_official_plan() -> None:
    plan = small_plan(lessons=6, modules=3)
    report = collect_curriculum_plan_validation(plan, policy=CurriculumScopePolicy())
    attempt = CurriculumPlanningAttempt(
        id="curriculum-planning-attempt:001",
        authoring_request_ref=plan.authoring_request_ref,
        correlation_id="correlation-001",
        provider="gemini",
        model="gemini-test",
        prompt_id="curriculum_planning",
        prompt_version="sep-02.3-v1",
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        status=CurriculumPlanningAttemptStatus.FAILED,
        original_duration_constraint="12 months",
        normalized_duration=plan.normalized_duration,
        weekly_effort_hours=3,
        weekly_effort_source=WeeklyEffortSource.DEFAULT,
        estimated_total_learning_hours=156,
        min_modules=5,
        max_modules=10,
        min_lessons=18,
        max_lessons=40,
        objective_count=report.objective_count,
        module_count=report.module_count,
        lesson_count=report.lesson_count,
        estimated_candidate_hours=report.estimated_total_hours,
        covered_objective_count=report.covered_objective_count,
        validation_issues=report.issues,
        uncovered_objective_refs=report.uncovered_objective_refs,
        unknown_objective_refs=report.unknown_objective_refs,
        sanitized_parsed_candidate=plan.model_dump(mode="json"),
    )
    repository = InMemoryContentGenerationRepository()

    await repository.create_curriculum_planning_attempt(attempt)

    restored = await repository.get_curriculum_planning_attempt(attempt.id)
    assert restored is not None
    assert restored.issue_codes == report.issue_codes
    assert restored.sanitized_parsed_candidate["modules"] == plan.model_dump(mode="json")["modules"]
    assert await repository.list_curriculum_plans(plan.authoring_request_ref) == []


@pytest.mark.asyncio
async def test_planning_failure_persists_diagnostic_and_replay_does_not_call_gateway() -> None:
    plan = small_plan(lessons=6, modules=3)
    report = collect_curriculum_plan_validation(plan, policy=CurriculumScopePolicy())

    class Authoring:
        async def get(self, _request_id: str, _actor: object) -> CourseAuthoringRequest:
            return request(duration="12 months")

    class ContextBuilder:
        async def build(self, _request: CourseAuthoringRequest, _actor: object) -> object:
            return SimpleNamespace(
                learning_objectives=[],
                learning_need_refs=[],
                instructional_blueprint=None,
                audience_summary=SimpleNamespace(
                    model_dump=lambda mode: {"learner_count": 2, "source": "MANUAL_SELECTION"}
                ),
            )

    class Planner:
        async def plan(self, _context: CurriculumPlanningContext) -> CurriculumPlan:
            raise CurriculumPlanningCandidateValidationError(
                candidate_plan=plan,
                report=report,
                audit=SimpleNamespace(
                    provider="gemini",
                    model="gemini-test",
                    prompt_template_id="curriculum_planning",
                    prompt_template_version="sep-02.3-v1",
                    correlation_id="planning-correlation-001",
                ),
            )

    repository = InMemoryContentGenerationRepository()
    service = CurriculumPlanningService(
        authoring=Authoring(),
        context_builder=ContextBuilder(),
        planner=Planner(),
        repository=repository,
    )

    with pytest.raises(CurriculumPlanValidationError):
        await service.plan("request-planning-001", object())

    attempts = await repository.list_curriculum_planning_attempts("request-planning-001")
    assert len(attempts) == 1
    assert attempts[0].issue_codes == report.issue_codes
    assert await repository.list_curriculum_plans("request-planning-001") == []

    replayed = replay_curriculum_planning_attempt(attempts[0], policy=CurriculumScopePolicy())
    assert replayed.issue_codes == report.issue_codes


@pytest.mark.asyncio
async def test_goal_driven_year_plan_is_decomposed_beyond_legacy_three_six_shape() -> None:
    context = CurriculumPlanningContext(
        authoring_request_ref="request-planning-001",
        mode=CourseAuthoringMode.GOAL_DRIVEN,
        course_title="Python Backend Developer",
        training_goal="Build production-ready backend engineering capability",
        language="en",
        audience_summary={"learner_count": 10, "source": "MANUAL_SELECTION"},
        duration=normalize_training_duration("12 months"),
    )

    plan = await DeterministicCurriculumPlanner().plan(context)

    assert len(plan.learning_objectives) >= 4
    assert len(plan.modules) >= 5
    assert sum(len(module.lessons) for module in plan.modules) >= 18
    assert all(
        objective.origin == "GOAL_DRIVEN_TRAINING_BRIEF"
        for objective in plan.learning_objectives
    )
    validate_curriculum_plan(plan, policy=CurriculumScopePolicy())


def test_gap_driven_plan_keeps_canonical_objective_ids() -> None:
    canonical = CurriculumObjective(
        id="objective-canonical-001",
        statement="Apply the canonical skill",
        measurable_outcome="Produce the expected work sample.",
        sequence=1,
        origin="CANONICAL_LEARNING_OBJECTIVE",
    )
    context = CurriculumPlanningContext(
        authoring_request_ref="request-gap-001",
        mode=CourseAuthoringMode.GAP_DRIVEN,
        course_title="Canonical skill course",
        training_goal="Close a known skill gap",
        audience_summary={"learner_count": 1, "source": "MANUAL_SELECTION"},
        duration=normalize_training_duration("2 hours"),
        existing_learning_objectives=[canonical],
    )

    plan = DeterministicCurriculumPlanner().plan_gap(context)

    assert [item.id for item in plan.learning_objectives] == [canonical.id]
    assert plan.modules[0].lessons[0].objective_refs == [canonical.id]


@pytest.mark.asyncio
async def test_new_goal_driven_planning_rejects_without_latest_confirmed_revision() -> None:
    class Authoring:
        async def get(self, _request_id: str, _actor: object) -> CourseAuthoringRequest:
            return request(duration="12 months").model_copy(update={
                "authoring_workflow_version": "sep-08a-v1"
            })

    class ContextBuilder:
        async def build(self, *_args: object) -> object:
            raise AssertionError("context builder must not run before confirmation")

    class Planner:
        async def plan(self, _context: CurriculumPlanningContext) -> CurriculumPlan:
            raise AssertionError("planner must not run before confirmation")

    service = CurriculumPlanningService(
        authoring=Authoring(),
        context_builder=ContextBuilder(),
        planner=Planner(),
        repository=InMemoryContentGenerationRepository(),
        brief_revisions=InMemoryAuthoringBriefRevisionRepository(),
    )

    with pytest.raises(ValueError, match="authoring_brief_not_confirmed"):
        await service.plan("request-planning-001", object())


@pytest.mark.asyncio
async def test_new_goal_driven_planning_uses_latest_confirmed_revision() -> None:
    revision_repository = InMemoryAuthoringBriefRevisionRepository()
    revision = AuthoringBriefRevision(
        id="authoring-brief-revision:confirmed",
        request_id="request-planning-001",
        version=1,
        status=AuthoringBriefRevisionStatus.CONFIRMED,
        payload=BriefRevisionPayload(
            training_goal="Confirmed goal",
            desired_outcomes=("Deliver a tested service",),
            learning_horizon="2 months",
            expected_learning_effort="48 hours",
        ),
        created_at=datetime.now(UTC),
        created_by=UUID("11111111-1111-1111-1111-111111111111"),
    )
    await revision_repository.create(revision)
    received: list[CurriculumPlanningContext] = []

    class Authoring:
        async def get(self, _request_id: str, _actor: object) -> CourseAuthoringRequest:
            return request(duration="1 month").model_copy(update={
                "authoring_workflow_version": "sep-08a-v1"
            })

    class ContextBuilder:
        async def build(self, authoring_request: CourseAuthoringRequest, _actor: object) -> object:
            assert authoring_request.training_brief.goal == "Confirmed goal"
            return SimpleNamespace(
                learning_objectives=[],
                learning_need_refs=[],
                instructional_blueprint=None,
                audience_summary=SimpleNamespace(
                    model_dump=lambda mode: {"learner_count": 2, "source": "MANUAL_SELECTION"}
                ),
            )

    class Planner:
        async def plan(self, context: CurriculumPlanningContext) -> CurriculumPlan:
            received.append(context)
            return small_plan(lessons=40, modules=8)

    service = CurriculumPlanningService(
        authoring=Authoring(),
        context_builder=ContextBuilder(),
        planner=Planner(),
        repository=InMemoryContentGenerationRepository(),
        brief_revisions=revision_repository,
    )

    plan = await service.plan("request-planning-001", object())
    assert received[0].training_goal == "Confirmed goal"
    assert received[0].learning_horizon == "2 months"
    assert received[0].duration.original == "2 months"
    assert plan.planning_metadata["authoring_brief_revision_ref"] == revision.id


@pytest.mark.asyncio
async def test_model_gateway_planner_uses_versioned_contract_and_stable_goal_refs() -> None:
    calls: list[object] = []

    class Gateway:
        async def infer_structured(self, inference: object, schema: object) -> object:
            calls.append((inference, schema))
            return SimpleNamespace(
                parsed=CurriculumPlanningOutput.model_validate({
                    "objectives": [{
                        "statement": "Apply the target capability",
                        "measurable_outcome": "Deliver a work sample that meets acceptance criteria.",
                        "sequence": 1,
                    }],
                    "modules": [{
                        "title": "Applied capability",
                        "order": 1,
                        "objective_refs": ["objective-1"],
                        "estimated_hours": 4,
                        "lessons": [{
                            "title": "Complete the work sample",
                            "order": 1,
                            "objective_refs": ["objective-1"],
                            "estimated_minutes": 120,
                            "lesson_type": "skill_practice",
                        }, {
                            "title": "Demonstrate the work sample",
                            "order": 2,
                            "objective_refs": ["objective-1"],
                            "estimated_minutes": 120,
                            "lesson_type": "skill_practice",
                        }],
                    }],
                    "estimated_total_learning_hours": 4,
                }),
                audit=SimpleNamespace(provider="fake", model="fake"),
            )

    context = CurriculumPlanningContext(
        authoring_request_ref="request-planning-001",
        mode=CourseAuthoringMode.GOAL_DRIVEN,
        course_title="Target course",
        training_goal="Build a target capability",
        audience_summary={"learner_count": 1, "source": "MANUAL_SELECTION"},
        duration=normalize_training_duration("2 hours"),
    )
    planner = ModelGatewayCurriculumPlanner(
        gateway=Gateway(), requested_provider="fake", correlation_id="planning-test"
    )

    plan = await planner.plan(context)

    assert plan.learning_objectives[0].id == "goal-driven-objective:request-planning-001:001"
    assert plan.modules[0].lessons[0].objective_refs == [plan.learning_objectives[0].id]
    assert calls[0][0].prompt_template_id == "curriculum_planning"
    assert calls[0][0].prompt_template_version == "sep-02.3-v3"
    assert CURRICULUM_PLANNING_HISTORICAL_VERSIONS == ("sep-02.3-v1", "sep-02.3-v2")
    assert calls[0][0].payload["estimated_total_learning_hours"] == 2
    assert plan.estimated_total_learning_hours == 2
    assert calls[0][0].payload["required_scope"] == {
        "modules": {"min": 1, "max": 2},
        "lessons": {"min": 2, "max": 6},
    }


@pytest.mark.asyncio
async def test_model_gateway_planner_replaces_uniform_model_minutes_with_workload_allocation() -> None:
    class Gateway:
        async def infer_structured(self, _inference: object, _schema: object) -> object:
            return SimpleNamespace(
                parsed=CurriculumPlanningOutput.model_validate({
                    "objectives": [{
                        "statement": "Build the target capability",
                        "measurable_outcome": "Deliver a working implementation.",
                        "sequence": 1,
                    }],
                    "modules": [{
                        "title": "Foundations and application",
                        "order": 1,
                        "objective_refs": ["objective-1"],
                        "estimated_hours": 5,
                        "lessons": [
                            {
                                "title": "Foundations",
                                "order": 1,
                                "objective_refs": ["objective-1"],
                                "estimated_minutes": 60,
                                "lesson_type": "foundation",
                            },
                            {
                                "title": "Core concepts",
                                "order": 2,
                                "objective_refs": ["objective-1"],
                                "estimated_minutes": 60,
                                "lesson_type": "concept",
                            },
                            {
                                "title": "Applied practice",
                                "order": 3,
                                "objective_refs": ["objective-1"],
                                "estimated_minutes": 60,
                                "lesson_type": "applied",
                            },
                        ],
                    }, {
                        "title": "Integration and delivery",
                        "order": 2,
                        "objective_refs": ["objective-1"],
                        "estimated_hours": 5,
                        "lessons": [
                            {
                                "title": "Practice lab",
                                "order": 1,
                                "objective_refs": ["objective-1"],
                                "estimated_minutes": 60,
                                "lesson_type": "practice",
                            },
                            {
                                "title": "Integration",
                                "order": 2,
                                "objective_refs": ["objective-1"],
                                "estimated_minutes": 60,
                                "lesson_type": "integration",
                            },
                            {
                                "title": "Capstone",
                                "order": 3,
                                "objective_refs": ["objective-1"],
                                "estimated_minutes": 60,
                                "lesson_type": "capstone",
                            },
                        ],
                    }],
                    "estimated_total_learning_hours": 10,
                }),
                audit=SimpleNamespace(provider="fake", model="fake"),
            )

    context = CurriculumPlanningContext(
        authoring_request_ref="request-planning-001",
        mode=CourseAuthoringMode.GOAL_DRIVEN,
        course_title="Target course",
        training_goal="Build a target capability",
        audience_summary={"learner_count": 1, "source": "MANUAL_SELECTION"},
        duration=normalize_training_duration("10 hours"),
    )

    plan = await ModelGatewayCurriculumPlanner(
        gateway=Gateway(), requested_provider="fake", correlation_id="planning-test"
    ).plan(context)
    lessons = [lesson for module in plan.modules for lesson in module.lessons]

    assert len({lesson.estimated_total_effort_minutes for lesson in lessons}) > 1
    assert sum(lesson.estimated_total_effort_minutes or 0 for lesson in lessons) == 600
    assert lessons[-1].estimated_total_effort_minutes > lessons[0].estimated_total_effort_minutes
    assert all(lesson.estimated_minutes % 15 == 0 for lesson in lessons)
