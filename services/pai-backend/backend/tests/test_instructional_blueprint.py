from uuid import UUID

import pytest

from app.capability_analysis.schemas import PreliminaryPriority
from app.instructional_blueprint.generator import (
    DeterministicInstructionalBlueprintGenerator,
    InstructionalBlueprintInput,
)
from app.instructional_blueprint.schemas import (
    CourseBlueprint,
    InstructionalBlueprint,
    InstructionalPattern,
    LessonBlueprint,
    LessonType,
    ModuleBlueprint,
)
from app.instructional_blueprint.validation import validate_instructional_blueprint
from app.learning.schemas import LearningObjective
from app.learning_need_profile.schemas import (
    LearnerContext,
    LearningNeedCompetency,
    LearningNeedCurrentState,
    LearningNeedGap,
    LearningNeedProfile,
    LearningNeedProvenance,
    LearningNeedTargetState,
)


def learning_need(*, constraints: dict[str, object] | None = None) -> LearningNeedProfile:
    return LearningNeedProfile(
        id="learning-need:analysis-001:gap-python-cleaning",
        candidate_reference=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        target_reference="role-data-analyst@2",
        learner_context=LearnerContext(role=None, experience_level=None),
        competency=LearningNeedCompetency(
            id="cap-python-cleaning", name=None, description=None
        ),
        current_state=LearningNeedCurrentState(level=None, evidence_refs=[]),
        target_state=LearningNeedTargetState(
            level="3", expected_behaviors=["Handle invalid values in tabular data"]
        ),
        gap=LearningNeedGap(
            type="skill_gap", description="Handle invalid values in tabular data"
        ),
        missing_knowledge=["data_cleaning_depth"],
        learning_constraints=constraints or {},
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
            evidence_refs=[],
            transformation="learning-need-profile-v1",
        ),
    )


def objective(learning_need_profile: LearningNeedProfile) -> LearningObjective:
    return LearningObjective(
        id="objective-python-cleaning",
        learning_need_ref=learning_need_profile.id,
        statement="Handle invalid values in tabular data",
        bloom_level=None,
        evidence_required=None,
        competency_id="cap-python-cleaning",
        current_level=None,
        target_level=3,
        measurable_outcome="Handle invalid values in tabular data",
        gap_id="gap-python-cleaning",
        sequence=1,
    )


def test_blueprint_schema_preserves_course_module_lesson_references() -> None:
    lesson = LessonBlueprint(
        id="lesson-001",
        title="Handling Missing Values",
        objective_refs=["objective-001"],
        lesson_type=LessonType.SKILL_PRACTICE,
        estimated_minutes=45,
        instructional_pattern=[
            InstructionalPattern.CONCEPT_INTRODUCTION,
            InstructionalPattern.WORKED_EXAMPLE,
            InstructionalPattern.GUIDED_PRACTICE,
            InstructionalPattern.INDEPENDENT_PRACTICE,
        ],
        assessment_refs=[],
        sequence=1,
    )
    module = ModuleBlueprint(
        id="module-001",
        title="Data cleaning",
        objective_refs=["objective-001"],
        lesson_refs=[lesson.id],
        sequence=1,
    )
    course = CourseBlueprint(
        id="course-001",
        title="Python data cleaning",
        objective_refs=["objective-001"],
        module_refs=[module.id],
    )
    blueprint = InstructionalBlueprint(
        id="blueprint-001",
        learning_need_ref="learning-need-001",
        objective_refs=["objective-001"],
        course=course,
        modules=[module],
        lessons=[lesson],
    )

    validate_instructional_blueprint(
        blueprint,
        objective_ids={"objective-001"},
        learning_need_ref="learning-need-001",
    )


@pytest.mark.asyncio
async def test_deterministic_generator_maps_objective_to_content_free_blueprint() -> None:
    source = learning_need(constraints={"estimated_minutes": 45})
    input_context = InstructionalBlueprintInput(
        learning_need=source,
        objective=objective(source),
    )
    generator = DeterministicInstructionalBlueprintGenerator()

    first = await generator.generate(input_context)
    second = await generator.generate(input_context)

    assert first == second
    assert first.learning_need_ref == source.id
    assert first.objective_refs == ["objective-python-cleaning"]
    assert first.lessons[0].title == "Handle invalid values in tabular data"
    assert first.lessons[0].objective_refs == ["objective-python-cleaning"]
    assert first.lessons[0].estimated_minutes == 45
    assert first.lessons[0].assessment_refs == []
    assert "content" not in first.model_dump()


@pytest.mark.asyncio
async def test_missing_bloom_and_constraints_use_no_inferred_instructional_claims() -> None:
    source = learning_need()
    result = await DeterministicInstructionalBlueprintGenerator().generate(
        InstructionalBlueprintInput(learning_need=source, objective=objective(source))
    )

    assert result.lessons[0].estimated_minutes == 30
    assert result.lessons[0].assessment_refs == []
    assert result.lessons[0].instructional_pattern == [
        InstructionalPattern.CONCEPT_INTRODUCTION,
        InstructionalPattern.WORKED_EXAMPLE,
        InstructionalPattern.GUIDED_PRACTICE,
        InstructionalPattern.INDEPENDENT_PRACTICE,
    ]


def test_validation_rejects_orphan_objective_reference() -> None:
    source = learning_need()
    blueprint = InstructionalBlueprint(
        id="blueprint-001",
        learning_need_ref=source.id,
        objective_refs=["objective-missing"],
        course=CourseBlueprint(
            id="course-001",
            title="Course",
            objective_refs=["objective-missing"],
            module_refs=["module-001"],
        ),
        modules=[
            ModuleBlueprint(
                id="module-001",
                title="Module",
                objective_refs=["objective-missing"],
                lesson_refs=["lesson-001"],
                sequence=1,
            )
        ],
        lessons=[
            LessonBlueprint(
                id="lesson-001",
                title="Lesson",
                objective_refs=["objective-missing"],
                lesson_type=LessonType.SKILL_PRACTICE,
                estimated_minutes=30,
                instructional_pattern=[InstructionalPattern.GUIDED_PRACTICE],
                assessment_refs=[],
                sequence=1,
            )
        ],
    )

    with pytest.raises(ValueError, match="objective_reference_not_found"):
        validate_instructional_blueprint(
            blueprint,
            objective_ids={"objective-python-cleaning"},
            learning_need_ref=source.id,
        )


def test_validation_rejects_invented_assessment_reference() -> None:
    source = learning_need()
    blueprint = blueprint_with_assessments(source, assessment_refs=["assessment-001"])

    with pytest.raises(ValueError, match="assessment_reference_not_supported"):
        validate_instructional_blueprint(
            blueprint,
            objective_ids={"objective-python-cleaning"},
            learning_need_ref=source.id,
        )


def test_validation_rejects_invalid_lesson_sequence() -> None:
    source = learning_need()
    blueprint = blueprint_with_assessments(source, assessment_refs=[])
    invalid = blueprint.model_copy(
        update={
            "lessons": [blueprint.lessons[0].model_copy(update={"sequence": 2})]
        }
    )

    with pytest.raises(ValueError, match="invalid_lesson_sequence"):
        validate_instructional_blueprint(
            invalid,
            objective_ids={"objective-python-cleaning"},
            learning_need_ref=source.id,
        )


def test_validation_rejects_invalid_duration() -> None:
    source = learning_need()
    blueprint = blueprint_with_assessments(source, assessment_refs=[])
    invalid = blueprint.model_copy(
        update={
            "lessons": [
                blueprint.lessons[0].model_copy(update={"estimated_minutes": 0})
            ]
        }
    )

    with pytest.raises(ValueError, match="invalid_lesson_duration"):
        validate_instructional_blueprint(
            invalid,
            objective_ids={"objective-python-cleaning"},
            learning_need_ref=source.id,
        )


def test_validation_rejects_inconsistent_module_references() -> None:
    source = learning_need()
    blueprint = blueprint_with_assessments(source, assessment_refs=[])
    invalid = blueprint.model_copy(
        update={
            "course": blueprint.course.model_copy(update={"module_refs": []})
        }
    )

    with pytest.raises(ValueError, match="course_module_references_inconsistent"):
        validate_instructional_blueprint(
            invalid,
            objective_ids={"objective-python-cleaning"},
            learning_need_ref=source.id,
        )


def blueprint_with_assessments(
    source: LearningNeedProfile, *, assessment_refs: list[str]
) -> InstructionalBlueprint:
    return InstructionalBlueprint(
        id="blueprint-001",
        learning_need_ref=source.id,
        objective_refs=["objective-python-cleaning"],
        course=CourseBlueprint(
            id="course-001",
            title="Course",
            objective_refs=["objective-python-cleaning"],
            module_refs=["module-001"],
        ),
        modules=[
            ModuleBlueprint(
                id="module-001",
                title="Module",
                objective_refs=["objective-python-cleaning"],
                lesson_refs=["lesson-001"],
                sequence=1,
            )
        ],
        lessons=[
            LessonBlueprint(
                id="lesson-001",
                title="Lesson",
                objective_refs=["objective-python-cleaning"],
                lesson_type=LessonType.SKILL_PRACTICE,
                estimated_minutes=30,
                instructional_pattern=[InstructionalPattern.GUIDED_PRACTICE],
                assessment_refs=assessment_refs,
                sequence=1,
            )
        ],
    )
