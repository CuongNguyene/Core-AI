import pytest

from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03,
    AssessmentDependencyCandidate,
    AssessmentDesignOutput,
    PrerequisiteProposalOutput,
    register_instructional_design_experiment_contracts,
    validate_v03_prerequisite_proposals,
)
from app.instructional_design.orchestrator import attach_lesson_ids, deduplicate_exact_prerequisites
from app.instructional_design.schemas import (
    ArtifactProvenance,
    ArtifactSource,
    CourseOutline,
    InstructionalPattern,
    LessonSpec,
    ModuleOutline,
    PrerequisiteBasis,
    PrerequisiteClassification,
    PrerequisiteSpec,
    PrerequisiteStatus,
)
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def test_v03_assessment_can_keep_dependency_candidate_outside_required_evidence() -> None:
    output = AssessmentDesignOutput(
        objective_ids=["objective-1"],
        assessments=[],
        dependency_candidates=[
            AssessmentDependencyCandidate(
                capability="read a CSV file",
                reason="The task cannot start without loading the supplied data.",
                required_for_refs=["objective-1"],
            )
        ],
    )

    assert output.dependency_candidates[0].required_for_refs == ["objective-1"]


def test_v03_model_proposed_required_prerequisite_needs_specific_rationale_and_refs() -> None:
    candidate = PrerequisiteSpec(
        id="prerequisite-1",
        capability="tabular data concepts",
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
        classification=PrerequisiteClassification.REQUIRED_PREREQUISITE,
        rationale="The learner cannot interpret rows and columns needed by objective-1.",
        required_for_refs=["objective-1"],
    )

    validate_v03_prerequisite_proposals(
        PrerequisiteProposalOutput(brief_id="brief-1", prerequisites=[candidate])
    )


def test_v03_model_proposed_required_prerequisite_without_reason_fails() -> None:
    candidate = PrerequisiteSpec(
        id="prerequisite-1",
        capability="helpful background",
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
        classification=PrerequisiteClassification.REQUIRED_PREREQUISITE,
    )

    with pytest.raises(ValueError, match="rationale and required_for_refs"):
        validate_v03_prerequisite_proposals(
            PrerequisiteProposalOutput(brief_id="brief-1", prerequisites=[candidate])
        )


def test_v03_prompt_is_registered_without_changing_baseline_version() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_instructional_design_experiment_contracts(prompts, schemas)

    rendered = "\n".join(
        message.content
        for message in prompts.resolve(ASSESSMENT_DESIGN_SCHEMA_ID, "0.3").render(
            {"brief_id": "brief-1"}
        )
    )
    assert "dependency_candidates" in rendered
    assert "Do not introduce professional behaviors" in rendered
    assert (
        prompts.resolve(ASSESSMENT_DESIGN_SCHEMA_ID, "0.2").version
        != INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03
    )


def test_v03_assessment_contract_forbids_hidden_professional_scope_and_id_dependencies() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_instructional_design_experiment_contracts(prompts, schemas)
    rendered = "\n".join(
        message.content
        for message in prompts.resolve(ASSESSMENT_DESIGN_SCHEMA_ID, "0.3").render(
            {"brief_id": "brief-1"}
        )
    )

    assert "`required_capability_refs` must contain capability names" in rendered
    assert "never assessment IDs" in rendered
    assert "negotiation, leadership, or conflict resolution" in rendered


def test_v03_dependency_candidate_reference_chain_is_preserved_at_stage_boundary() -> None:
    candidate = AssessmentDependencyCandidate(
        capability="read a technical issue description",
        reason="The assessment task requires interpreting the supplied issue before explaining it.",
        required_for_refs=["objective-1", "assessment-1"],
    )
    output = AssessmentDesignOutput(
        objective_ids=["objective-1"],
        assessments=[],
        dependency_candidates=[candidate],
    )

    assert output.dependency_candidates[0].model_dump(mode="json") == {
        "capability": "read a technical issue description",
        "reason": "The assessment task requires interpreting the supplied issue before explaining it.",
        "required_for_refs": ["objective-1", "assessment-1"],
    }


def test_orchestration_derives_module_lesson_ids_and_deduplicates_exact_candidates() -> None:
    provenance = ArtifactProvenance(source=ArtifactSource.RESEARCHER_AUTHORED)
    course = CourseOutline(
        id="course-1",
        brief_id="brief-1",
        objective_ids=["objective-1"],
        modules=[
            ModuleOutline(
                id="module-1",
                title="Practice",
                objective_ids=["objective-1"],
                lesson_ids=["model-advisory-id"],
            )
        ],
        provenance=provenance,
    )
    lesson = LessonSpec(
        id="lesson-1",
        module_id="module-1",
        objective_ids=["objective-1"],
        lesson_goal="Practice",
        instructional_pattern=InstructionalPattern.GUIDED_PRACTICE,
        expected_learner_activity="Do the task",
        provenance=provenance,
    )
    first = PrerequisiteSpec(
        id="pre-1",
        capability="  Tabular   Data ",
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
        rationale="Needed for objective-1.",
        required_for_refs=["objective-1"],
    )
    second = first.model_copy(update={"id": "pre-2", "capability": "tabular data"})

    assert attach_lesson_ids(course, [lesson]).modules[0].lesson_ids == ["lesson-1"]
    deduplicated = deduplicate_exact_prerequisites([first, second])
    assert [item.id for item in deduplicated] == ["pre-1"]
    assert deduplicated[0].required_for_refs == ["objective-1"]


def test_v03_reference_validation_fails_closed_on_unknown_module_objective() -> None:
    from app.instructional_design.contracts import (
        CoursePlanningOutput,
        LearningObjectiveDesignOutput,
        LessonPlanningOutput,
    )
    from app.instructional_design.experiment_runners import _validate_v03_references
    from app.instructional_design.fixtures import research_fixture_bundles

    bundle = next(iter(research_fixture_bundles().values()))
    broken_outline = bundle.course_outline.model_copy(
        update={
            "modules": [
                bundle.course_outline.modules[0].model_copy(
                    update={"objective_ids": ["unknown-objective"], "lesson_ids": []}
                ),
                *bundle.course_outline.modules[1:],
            ]
        }
    )

    with pytest.raises(ValueError, match="unknown objective reference"):
        _validate_v03_references(
            objective_output=LearningObjectiveDesignOutput(
                brief_id=bundle.brief.id, objectives=list(bundle.objectives)
            ),
            assessment_output=AssessmentDesignOutput(
                objective_ids=[item.id for item in bundle.objectives],
                assessments=list(bundle.assessments),
            ),
            prerequisite_output=PrerequisiteProposalOutput(
                brief_id=bundle.brief.id, prerequisites=list(bundle.prerequisites)
            ),
            course_output=CoursePlanningOutput(
                brief_id=bundle.brief.id, course_outline=broken_outline
            ),
            lesson_output=LessonPlanningOutput(
                course_id=broken_outline.id, lessons=list(bundle.lessons)
            ),
            brief=bundle.brief,
        )


def test_v03_reference_validation_fails_closed_on_unknown_dependency_candidate() -> None:
    from app.instructional_design.contracts import (
        CoursePlanningOutput,
        LearningObjectiveDesignOutput,
        LessonPlanningOutput,
    )
    from app.instructional_design.experiment_runners import _validate_v03_references
    from app.instructional_design.fixtures import research_fixture_bundles

    bundle = next(iter(research_fixture_bundles().values()))
    with pytest.raises(ValueError, match="dependency candidate contains an unknown reference"):
        _validate_v03_references(
            objective_output=LearningObjectiveDesignOutput(
                brief_id=bundle.brief.id, objectives=list(bundle.objectives)
            ),
            assessment_output=AssessmentDesignOutput(
                objective_ids=[item.id for item in bundle.objectives],
                assessments=list(bundle.assessments),
                dependency_candidates=[
                    AssessmentDependencyCandidate(
                        capability="unknown dependency",
                        reason="test",
                        required_for_refs=["unknown-reference"],
                    )
                ],
            ),
            prerequisite_output=PrerequisiteProposalOutput(
                brief_id=bundle.brief.id, prerequisites=list(bundle.prerequisites)
            ),
            course_output=CoursePlanningOutput(
                brief_id=bundle.brief.id, course_outline=bundle.course_outline
            ),
            lesson_output=LessonPlanningOutput(
                course_id=bundle.course_outline.id, lessons=list(bundle.lessons)
            ),
            brief=bundle.brief,
        )
