from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.content_generation.prompts import (
    COURSE_GENERATION_HISTORICAL_VERSIONS,
    course_generation_prompt_template,
)
from app.content_generation.schemas import (
    AssessmentQuestion,
    AssessmentQuestionType,
    ContentSectionType,
    GeneratedAssessmentDraft,
    GeneratedCourse,
    GeneratedCourseDraft,
    GeneratedCourseLesson,
    GeneratedCourseModule,
    GeneratedCourseSection,
    GoalDerivedLearningObjective,
)
from app.course_authoring.schemas import (
    AudienceSnapshot,
    AudienceSnapshotSource,
    CourseAuthoringMode,
    CourseAuthoringRequest,
    CourseAuthoringStatus,
    TrainingBrief,
)
from app.course_generation.context import CourseGenerationContext, CourseGenerationContextBuilder
from app.course_generation.validation import (
    GeneratedCourseValidationError,
    validate_generated_course,
)
from app.learning_authoring.schemas import LearningObjectiveProjection


def context(*, goal_driven: bool = False) -> CourseGenerationContext:
    objective = LearningObjectiveProjection(
        id="objective-001",
        learning_need_ref="learning-need-001",
        statement="Apply the skill",
        bloom_level="apply",
        evidence_required=["practical deliverable"],
        competency_id="competency-001",
        current_level=1,
        target_level=3,
        measurable_outcome="Apply the skill in a practical task.",
        gap_id="gap-001",
        sequence=1,
    )
    return CourseGenerationContext(
        authoring_request_ref="request-001",
        course_title="Practical capability",
        training_brief=TrainingBrief(goal="Build practical capability", language="en"),
        audience_summary={"learner_count": 2, "source": "MANUAL_SELECTION"},
        learning_need_refs=[] if goal_driven else ["learning-need-001"],
        learning_objectives=[] if goal_driven else [objective],
        instructional_blueprint=None,
        language="en",
        duration_constraint=None,
        target_completion_context=None,
    )


def words(count: int) -> str:
    return " ".join(f"word{index}" for index in range(count))


def section(section_type: ContentSectionType, count: int) -> GeneratedCourseSection:
    return GeneratedCourseSection(
        type=section_type,
        title=section_type.value.replace("_", " ").title(),
        content=words(count),
        order=list(ContentSectionType).index(section_type) + 1,
        steps=["Inspect the task", "Complete the guided action"]
        if section_type is ContentSectionType.GUIDED_PRACTICE
        else [],
        success_criteria=["The learner produces the expected result"]
        if section_type is ContentSectionType.INDEPENDENT_PRACTICE
        else [],
    )


def rich_draft(*, objective_ref: str = "objective-001") -> GeneratedCourseDraft:
    minimums = {
        ContentSectionType.INTRODUCTION: 60,
        ContentSectionType.CONCEPT: 180,
        ContentSectionType.EXAMPLE: 100,
        ContentSectionType.GUIDED_PRACTICE: 100,
        ContentSectionType.INDEPENDENT_PRACTICE: 80,
        ContentSectionType.SUMMARY: 60,
    }
    return GeneratedCourseDraft(
        course=GeneratedCourse(title="Practical capability", description=words(40)),
        modules=[
            GeneratedCourseModule(
                title="Foundations",
                order=1,
                lessons=[
                    GeneratedCourseLesson(
                        title="Apply the capability",
                        order=1,
                        objective_refs=[objective_ref] if objective_ref else [],
                        sections=[
                            section(section_type, minimum)
                            for section_type, minimum in minimums.items()
                        ],
                    )
                ],
            )
        ],
        assessment=None,
    )


def authoring_request(mode: CourseAuthoringMode) -> CourseAuthoringRequest:
    return CourseAuthoringRequest(
        id="request-goal-001",
        title="Practical capability",
        training_brief=TrainingBrief(goal="Build practical capability", language="en"),
        audience_snapshot=AudienceSnapshot(
            id="audience-001",
            learner_refs=("learner-1", "learner-2"),
            learner_count=2,
            captured_at=datetime(2026, 8, 25, tzinfo=UTC),
            source=AudienceSnapshotSource.MANUAL_SELECTION,
        ),
        learning_need_refs=(),
        objective_refs=(),
        instructional_blueprint_ref=None,
        mode=mode,
        status=CourseAuthoringStatus.DRAFT,
        created_by_actor_ref=UUID("11111111-1111-1111-1111-111111111111"),
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
    )


def test_prompt_v3_requires_substantive_instruction_and_structured_practice() -> None:
    template = course_generation_prompt_template()

    assert template.version == "sep-02-v3"
    for phrase in (
        "why the topic matters",
        "clear explanation",
        "concrete scenario",
        "step-by-step guidance",
        "success criteria",
        "substantive self-study draft",
        "one-sentence sections",
    ):
        assert phrase in f"{template.system_instruction} {template.user_instruction}"
    assert "Goal-driven requests without objectives must keep objective_refs empty" not in template.user_instruction
    assert COURSE_GENERATION_HISTORICAL_VERSIONS == ("sep-02-v2",)


@pytest.mark.parametrize(
    ("section_type", "below", "minimum"),
    [
        (ContentSectionType.INTRODUCTION, 59, 60),
        (ContentSectionType.CONCEPT, 179, 180),
        (ContentSectionType.EXAMPLE, 99, 100),
        (ContentSectionType.SUMMARY, 59, 60),
    ],
)
def test_section_below_threshold_is_rejected_at_boundary(
    section_type: ContentSectionType, below: int, minimum: int
) -> None:
    below_draft = rich_draft()
    sections = list(below_draft.modules[0].lessons[0].sections)
    index = list(ContentSectionType).index(section_type)
    sections[index] = section(section_type, below)
    below_draft = below_draft.model_copy(
        update={
            "modules": [
                below_draft.modules[0].model_copy(
                    update={
                        "lessons": [
                            below_draft.modules[0].lessons[0].model_copy(
                                update={"sections": sections}
                            )
                        ]
                    }
                )
            ]
        }
    )

    with pytest.raises(GeneratedCourseValidationError, match="section_word_count"):
        validate_generated_course(below_draft, context())

    assert section(section_type, minimum).content.count(" ") + 1 == minimum


def test_section_quality_failure_log_includes_observed_depth(caplog: pytest.LogCaptureFixture) -> None:
    invalid = rich_draft()
    sections = list(invalid.modules[0].lessons[0].sections)
    sections[1] = section(ContentSectionType.CONCEPT, 179)
    invalid = invalid.model_copy(
        update={
            "modules": [
                invalid.modules[0].model_copy(
                    update={
                        "lessons": [
                            invalid.modules[0].lessons[0].model_copy(
                                update={"sections": sections}
                            )
                        ]
                    }
                )
            ]
        }
    )

    with pytest.raises(GeneratedCourseValidationError):
        validate_generated_course(invalid, context())

    assert "section_type=concept" in caplog.text
    assert "words=179" in caplog.text
    assert "minimum=180" in caplog.text


def test_required_section_coverage_is_rejected() -> None:
    draft = rich_draft()
    lesson = draft.modules[0].lessons[0]
    missing = [item for item in lesson.sections if item.type is not ContentSectionType.SUMMARY]
    invalid = draft.model_copy(
        update={
            "modules": [
                draft.modules[0].model_copy(
                    update={"lessons": [lesson.model_copy(update={"sections": missing})]}
                )
            ]
        }
    )

    with pytest.raises(GeneratedCourseValidationError, match="required_section_missing"):
        validate_generated_course(invalid, context())


def test_guided_practice_requires_two_steps_and_independent_practice_requires_criteria() -> None:
    draft = rich_draft()
    lesson = draft.modules[0].lessons[0]
    sections = [
        item.model_copy(update={"steps": ["Only one step"]})
        if item.type is ContentSectionType.GUIDED_PRACTICE
        else item.model_copy(update={"success_criteria": []})
        if item.type is ContentSectionType.INDEPENDENT_PRACTICE
        else item
        for item in lesson.sections
    ]
    invalid = draft.model_copy(
        update={
            "modules": [
                draft.modules[0].model_copy(
                    update={"lessons": [lesson.model_copy(update={"sections": sections})]}
                )
            ]
        }
    )

    with pytest.raises(GeneratedCourseValidationError, match="guided_practice_steps"):
        validate_generated_course(invalid, context())


def test_independent_practice_requires_success_criteria() -> None:
    draft = rich_draft()
    lesson = draft.modules[0].lessons[0]
    sections = [
        item.model_copy(update={"success_criteria": []})
        if item.type is ContentSectionType.INDEPENDENT_PRACTICE
        else item
        for item in lesson.sections
    ]
    invalid = GeneratedCourseDraft.model_validate(
        draft.model_dump()
        | {
            "modules": [
                draft.modules[0].model_dump()
                | {"lessons": [lesson.model_dump() | {"sections": sections}]}
            ]
        }
    )

    with pytest.raises(
        GeneratedCourseValidationError,
        match="independent_practice_success_criteria",
    ):
        validate_generated_course(invalid, context())


def test_assessment_requires_three_choices_and_objective_alignment() -> None:
    draft = rich_draft()
    assessment = GeneratedAssessmentDraft(
        questions=[
            AssessmentQuestion(
                prompt="Choose the best action.",
                question_type=AssessmentQuestionType.MULTIPLE_CHOICE,
                options=["First", "Second", "Third"],
                expected_answer="Second",
                objective_refs=["objective-001"],
            )
        ]
    )
    valid = draft.model_copy(update={"assessment": assessment})
    validate_generated_course(valid, context())

    with pytest.raises(ValueError, match="multiple_choice_options_required"):
        AssessmentQuestion(
            prompt="Choose.",
            question_type=AssessmentQuestionType.MULTIPLE_CHOICE,
            options=["First", "Second"],
            expected_answer="First",
            objective_refs=["objective-001"],
        )

    invalid_reference = GeneratedCourseDraft.model_validate(
        valid.model_dump()
        | {
            "assessment": {
                "questions": [
                    {
                        "prompt": "Choose.",
                        "question_type": AssessmentQuestionType.SHORT_ANSWER,
                        "expected_answer": "A practical answer.",
                        "objective_refs": ["objective-unknown"],
                    }
                ]
            }
        }
    )
    with pytest.raises(GeneratedCourseValidationError, match="assessment_objective_reference"):
        validate_generated_course(invalid_reference, context())


@pytest.mark.asyncio
async def test_goal_driven_context_creates_explicit_derived_objective_artifact() -> None:
    class Reader:
        async def get_learning_need(self, _reference: str, _actor: object) -> object:
            raise AssertionError("GOAL_DRIVEN must not read capability artifacts")

        async def get_learning_objective(self, _reference: str, _actor: object) -> object:
            raise AssertionError("GOAL_DRIVEN must not read canonical objectives")

        async def get_instructional_blueprint(self, _reference: str, _actor: object) -> object:
            raise AssertionError("GOAL_DRIVEN must not read a capability blueprint")

    context_value = await CourseGenerationContextBuilder(Reader()).build(
        authoring_request(CourseAuthoringMode.GOAL_DRIVEN), object()
    )

    assert len(context_value.generated_objectives) == 1
    derived = context_value.generated_objectives[0]
    assert derived.id == "goal-driven-objective:request-goal-001:1"
    assert derived.statement == "Build practical capability"
    assert derived.measurable_outcome is None
    assert derived.origin == "GOAL_DRIVEN_TRAINING_BRIEF"


def test_goal_derived_reference_can_align_course_and_assessment() -> None:
    derived_ref = "goal-driven-objective:request-goal-001:1"
    goal_context = context(goal_driven=True).model_copy(
        update={
            "generated_objectives": [
                GoalDerivedLearningObjective(
                    id=derived_ref,
                    statement="Build practical capability",
                    measurable_outcome=None,
                    sequence=1,
                    origin="GOAL_DRIVEN_TRAINING_BRIEF",
                )
            ]
        }
    )
    goal_draft = rich_draft(objective_ref=derived_ref).model_copy(
        update={
            "assessment": GeneratedAssessmentDraft(
                questions=[
                    AssessmentQuestion(
                        prompt="Which action best demonstrates the goal?",
                        question_type=AssessmentQuestionType.SHORT_ANSWER,
                        expected_answer="A practical demonstration.",
                        objective_refs=[derived_ref],
                    )
                ]
            )
        }
    )

    validate_generated_course(goal_draft, goal_context)
