import pytest

from app.instructional_design.schemas import (
    ArtifactProvenance,
    ArtifactSource,
    AssessmentCapabilityRequirement,
    AssessmentRole,
    AssessmentSpec,
    AssessmentTaskSpec,
    CognitiveProcess,
    PlanningWarning,
    PlanningWarningDecision,
    PlanningWarningType,
    PrerequisiteBasis,
    PrerequisiteClassification,
    PrerequisiteSpec,
    PrerequisiteStatus,
    PrerequisiteStructuralReviewStatus,
)


def _assessment(**changes: object) -> AssessmentSpec:
    values: dict[str, object] = {
        "id": "assessment-1",
        "objective_ids": ["objective-1"],
        "capability_claim": "Explain a technical issue",
        "required_evidence": [],
        "task": AssessmentTaskSpec(task_type="written", description="Explain the issue."),
        "cognitive_process": CognitiveProcess.APPLY,
        "role": AssessmentRole.FORMATIVE,
        "provenance": ArtifactProvenance(
            source=ArtifactSource.MODEL_PROPOSED,
            provisional=True,
        ),
    }
    values.update(changes)
    return AssessmentSpec(**values)


def test_assessment_uses_typed_capability_requirement_not_artifact_identity() -> None:
    assessment = _assessment(
        required_capabilities=[
            AssessmentCapabilityRequirement(
                capability="interpret a supplied technical issue",
                objective_ids=["objective-1"],
            )
        ]
    )

    assert assessment.effective_role is AssessmentRole.FORMATIVE
    assert assessment.required_capabilities[0].capability == "interpret a supplied technical issue"


def test_assessment_accepts_name_wire_shape_for_valid_capability() -> None:
    assessment = _assessment(
        required_capabilities=[
            {"name": "transform tabular data safely", "objective_ids": ["objective-1"]}
        ]
    )

    assert assessment.required_capabilities[0].capability == "transform tabular data safely"


def test_assessment_rejects_conflicting_legacy_and_typed_role() -> None:
    with pytest.raises(ValueError, match="role conflicts with legacy is_summative"):
        _assessment(is_summative=True)


def test_patch_contract_registers_v031_prompt_and_schema() -> None:
    from app.instructional_design.contracts import (
        ASSESSMENT_DESIGN_SCHEMA_ID,
        INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
        register_instructional_design_experiment_contracts,
    )
    from app.model_gateway.prompts import PromptTemplateRegistry
    from app.model_gateway.schema_registry import OutputSchemaRegistry

    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_instructional_design_experiment_contracts(prompts, schemas)

    rendered = "\n".join(
        message.content
        for message in prompts.resolve(
            ASSESSMENT_DESIGN_SCHEMA_ID, INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031
        ).render({"brief_id": "brief-1"})
    )
    assert "Use `role` and `required_capabilities`" in rendered
    assert schemas.resolve(
        ASSESSMENT_DESIGN_SCHEMA_ID, INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031
    ).schema is not None


def _reference_validation_inputs() -> dict[str, object]:
    from app.instructional_design.contracts import (
        AssessmentDesignOutput,
        CoursePlanningOutput,
        LearningObjectiveDesignOutput,
        LessonPlanningOutput,
        PrerequisiteProposalOutput,
    )
    from app.instructional_design.fixtures import research_fixture_bundles

    bundle = next(iter(research_fixture_bundles().values()))
    return {
        "brief": bundle.brief,
        "objective_output": LearningObjectiveDesignOutput(
            brief_id=bundle.brief.id,
            objectives=list(bundle.objectives),
        ),
        "assessment_output": AssessmentDesignOutput(
            objective_ids=[item.id for item in bundle.objectives],
            assessments=list(bundle.assessments),
        ),
        "prerequisite_output": PrerequisiteProposalOutput(
            brief_id=bundle.brief.id,
            prerequisites=list(bundle.prerequisites),
        ),
        "course_output": CoursePlanningOutput(
            brief_id=bundle.brief.id,
            course_outline=bundle.course_outline,
        ),
        "lesson_output": LessonPlanningOutput(
            course_id=bundle.course_outline.id,
            lessons=list(bundle.lessons),
        ),
    }


def test_patch_contract_rejects_artifact_id_in_legacy_capability_field() -> None:
    from app.instructional_design.experiment_runners import _validate_v03_references

    inputs = _reference_validation_inputs()
    assessment_output = inputs["assessment_output"]
    assert hasattr(assessment_output, "assessments")
    broken_assessment = assessment_output.assessments[0].model_copy(
        update={"required_capability_refs": [assessment_output.assessments[0].id]}
    )
    inputs["assessment_output"] = assessment_output.model_copy(
        update={"assessments": [broken_assessment, *assessment_output.assessments[1:]]}
    )

    with pytest.raises(ValueError, match="artifact ID in capability requirement"):
        _validate_v03_references(**inputs)  # type: ignore[arg-type]


def test_patch_contract_rejects_requirement_objective_outside_parent_assessment() -> None:
    """A globally valid objective is still invalid outside its assessment owner."""

    from app.instructional_design.experiment_runners import _validate_v03_references

    inputs = _reference_validation_inputs()
    objective_output = inputs["objective_output"]
    assessment_output = inputs["assessment_output"]
    assert hasattr(objective_output, "objectives")
    assert hasattr(assessment_output, "assessments")
    assessment = assessment_output.assessments[0]
    foreign_objective = objective_output.objectives[0].model_copy(
        update={"id": "objective-globally-valid-but-not-assessment-owned"}
    )
    foreign_objective_id = foreign_objective.id
    inputs["objective_output"] = objective_output.model_copy(
        update={"objectives": [*objective_output.objectives, foreign_objective]}
    )
    requirement = AssessmentCapabilityRequirement(
        capability="externally owned objective capability",
        objective_ids=[foreign_objective_id],
    )
    broken_assessment = assessment.model_copy(
        update={"required_capabilities": [requirement]}
    )
    inputs["assessment_output"] = assessment_output.model_copy(
        update={"assessments": [broken_assessment, *assessment_output.assessments[1:]]}
    )

    with pytest.raises(
        ValueError, match="capability requirement contains an unknown objective reference"
    ):
        _validate_v03_references(**inputs)  # type: ignore[arg-type]


def test_patch_contract_rejects_summative_reference_as_formative() -> None:
    from app.instructional_design.experiment_runners import _validate_v03_references

    inputs = _reference_validation_inputs()
    assessment_output = inputs["assessment_output"]
    assert hasattr(assessment_output, "assessments")
    summative_id = next(
        item.id for item in assessment_output.assessments if item.effective_role is AssessmentRole.SUMMATIVE
    )
    lesson_output = inputs["lesson_output"]
    assert hasattr(lesson_output, "lessons")
    broken_lesson = lesson_output.lessons[0].model_copy(
        update={"formative_assessment_ids": [summative_id]}
    )
    inputs["lesson_output"] = lesson_output.model_copy(
        update={"lessons": [broken_lesson, *lesson_output.lessons[1:]]}
    )

    with pytest.raises(ValueError, match="non-formative assessment reference"):
        _validate_v03_references(**inputs)  # type: ignore[arg-type]


def test_patch_contract_rejects_lesson_objective_outside_its_module() -> None:
    from app.instructional_design.contracts import LearningObjectiveDesignOutput
    from app.instructional_design.experiment_runners import _validate_v03_references

    inputs = _reference_validation_inputs()
    lesson_output = inputs["lesson_output"]
    course_output = inputs["course_output"]
    assert hasattr(lesson_output, "lessons")
    assert hasattr(course_output, "course_outline")
    module = course_output.course_outline.modules[0]
    objective_output = inputs["objective_output"]
    assert hasattr(objective_output, "objectives")
    additional_objective = objective_output.objectives[0].model_copy(update={"id": "objective-2"})
    unrelated_objective_id = additional_objective.id
    inputs["objective_output"] = LearningObjectiveDesignOutput(
        brief_id=objective_output.brief_id,
        objectives=[*objective_output.objectives, additional_objective],
    )
    inputs["course_output"] = course_output.model_copy(
        update={
            "course_outline": course_output.course_outline.model_copy(
                update={
                    "objective_ids": [*course_output.course_outline.objective_ids, unrelated_objective_id],
                    "modules": [module, *course_output.course_outline.modules[1:]],
                }
            )
        }
    )
    broken_lesson = lesson_output.lessons[0].model_copy(
        update={"objective_ids": [unrelated_objective_id]}
    )
    inputs["lesson_output"] = lesson_output.model_copy(
        update={"lessons": [broken_lesson, *lesson_output.lessons[1:]]}
    )

    with pytest.raises(ValueError, match="outside its module"):
        _validate_v03_references(**inputs)  # type: ignore[arg-type]


def test_patch_contract_requires_warning_for_declared_duration_overflow() -> None:
    from app.instructional_design.experiment_runners import _validate_v03_references

    inputs = _reference_validation_inputs()
    course_output = inputs["course_output"]
    assert hasattr(course_output, "course_outline")
    overflowing_course = course_output.course_outline.model_copy(
        update={
            "estimated_minutes": 30,
            "modules": [
                course_output.course_outline.modules[0].model_copy(update={"estimated_minutes": 45})
            ],
        }
    )
    inputs["course_output"] = course_output.model_copy(update={"course_outline": overflowing_course})

    with pytest.raises(ValueError, match="scope_time_conflict planning warning"):
        _validate_v03_references(**inputs)  # type: ignore[arg-type]

    inputs["course_output"] = course_output.model_copy(
        update={
            "course_outline": overflowing_course.model_copy(
                update={
                    "planning_warnings": [
                        PlanningWarning(
                            type=PlanningWarningType.SCOPE_TIME_CONFLICT,
                            decision=PlanningWarningDecision.PRIORITIZED_CORE_OBJECTIVES,
                        )
                    ]
                }
            )
        }
    )
    _validate_v03_references(**inputs)  # type: ignore[arg-type]


def test_prerequisite_structural_review_is_non_mutating_and_candidate_only() -> None:
    from app.instructional_design.contracts import review_prerequisite_structural_minimality

    prerequisite = PrerequisiteSpec(
        id="prerequisite-1",
        capability="interpret a table header",
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
        classification=PrerequisiteClassification.REQUIRED_PREREQUISITE,
        rationale="Without this, the learner cannot interpret the supplied task input.",
        required_for_refs=["objective-1"],
    )

    review = review_prerequisite_structural_minimality(
        prerequisite,
        allowed_requirement_refs={"objective-1"},
    )

    assert review.status is PrerequisiteStructuralReviewStatus.STRUCTURALLY_SUPPORTED
    assert prerequisite.status is PrerequisiteStatus.CANDIDATE
