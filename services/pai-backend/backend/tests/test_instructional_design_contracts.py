from datetime import UTC, datetime

from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_SCHEMA_VERSION,
    LESSON_PLANNING_SCHEMA_ID,
    OBJECTIVE_DESIGN_SCHEMA_ID,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
    AssessmentDesigner,
    AssessmentDesignOutput,
    CoursePlanner,
    LearningObjectiveDesignOutput,
    LessonPlanner,
    ObjectiveDesigner,
    PrerequisiteProposer,
    register_instructional_design_contracts,
)
from app.instructional_design.orchestrator import build_research_snapshot
from app.instructional_design.schemas import (
    ArtifactProvenance,
    ArtifactSource,
    AssessmentSpec,
    AssessmentTaskSpec,
    CognitiveProcess,
    CourseOutline,
    EvidenceCriterion,
    GenerationProvenance,
    InstructionalPattern,
    KnowledgeDimension,
    LearnerState,
    LearningObjectiveSpec,
    LessonSpec,
    ModuleOutline,
    ResearchBriefProvenance,
    ResearchCapability,
    ResearchConstraints,
    ResearchLearningBrief,
)
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry

AUTHORED = ArtifactProvenance(source=ArtifactSource.RESEARCHER_AUTHORED)


def _brief() -> ResearchLearningBrief:
    return ResearchLearningBrief(
        id="brief-1",
        capability=ResearchCapability(name="technical communication"),
        learner_state=LearnerState(),
        desired_performances=["explain a technical issue"],
        constraints=ResearchConstraints(language="en"),
        provenance=ResearchBriefProvenance(),
    )


def _objective() -> LearningObjectiveSpec:
    return LearningObjectiveSpec(
        id="objective-1",
        brief_id="brief-1",
        performance="Given a non-specialist audience, explain a technical issue with suitable terminology.",
        cognitive_process=CognitiveProcess.APPLY,
        knowledge_dimension=KnowledgeDimension.CONCEPTUAL,
        success_criteria=["Adapts terminology to audience"],
        capability_refs=["technical-communication"],
        provenance=AUTHORED,
    )


def _assessment() -> AssessmentSpec:
    return AssessmentSpec(
        id="assessment-1",
        objective_ids=["objective-1"],
        capability_claim="Can explain a technical issue to a non-specialist.",
        required_evidence=[
            EvidenceCriterion(id="evidence-1", criterion="Uses suitable terminology")
        ],
        task=AssessmentTaskSpec(
            task_type="scenario_response", description="Explain a service outage to a stakeholder."
        ),
        cognitive_process=CognitiveProcess.APPLY,
        provenance=AUTHORED,
    )


def _course() -> CourseOutline:
    return CourseOutline(
        id="course-1",
        brief_id="brief-1",
        objective_ids=["objective-1"],
        modules=[
            ModuleOutline(
                id="module-1",
                title="Audience adaptation",
                objective_ids=["objective-1"],
                lesson_ids=["lesson-1"],
            )
        ],
        provenance=AUTHORED,
    )


def _lesson() -> LessonSpec:
    return LessonSpec(
        id="lesson-1",
        module_id="module-1",
        objective_ids=["objective-1"],
        lesson_goal="Practice adapting a technical explanation.",
        instructional_pattern=InstructionalPattern.GUIDED_PRACTICE,
        expected_learner_activity="Revise an explanation for a non-specialist audience.",
        provenance=AUTHORED,
    )


def test_versioned_prompt_and_output_contracts_are_registered() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()

    register_instructional_design_contracts(prompts, schemas)

    assert (
        schemas.resolve(OBJECTIVE_DESIGN_SCHEMA_ID, INSTRUCTIONAL_DESIGN_SCHEMA_VERSION)
        is LearningObjectiveDesignOutput
    )
    assert (
        schemas.resolve(ASSESSMENT_DESIGN_SCHEMA_ID, INSTRUCTIONAL_DESIGN_SCHEMA_VERSION)
        is AssessmentDesignOutput
    )
    for contract_id in (
        OBJECTIVE_DESIGN_SCHEMA_ID,
        ASSESSMENT_DESIGN_SCHEMA_ID,
        PREREQUISITE_PROPOSAL_SCHEMA_ID,
        COURSE_PLANNING_SCHEMA_ID,
        LESSON_PLANNING_SCHEMA_ID,
    ):
        rendered = "\n".join(
            message.content
            for message in prompts.resolve(contract_id, INSTRUCTIONAL_DESIGN_SCHEMA_VERSION).render(
                {"brief_id": "brief-1"}
            )
        ).casefold()
        assert "json" in rendered
        assert "research-only" in rendered
        assert "competency" in rendered


def test_staged_designer_responsibilities_are_not_a_one_shot_course_generator() -> None:
    assert {
        item.__name__
        for item in (
            ObjectiveDesigner,
            AssessmentDesigner,
            PrerequisiteProposer,
            CoursePlanner,
            LessonPlanner,
        )
    } == {
        "ObjectiveDesigner",
        "AssessmentDesigner",
        "PrerequisiteProposer",
        "CoursePlanner",
        "LessonPlanner",
    }


def test_model_proposal_contract_preserves_brief_and_upstream_objective_ids() -> None:
    proposal = LearningObjectiveDesignOutput(brief_id="brief-1", objectives=[_objective()])
    assessment = AssessmentDesignOutput(objective_ids=["objective-1"], assessments=[_assessment()])

    assert proposal.objectives[0].brief_id == proposal.brief_id
    assert assessment.assessments[0].objective_ids == assessment.objective_ids


def test_orchestrator_uses_deterministic_gate_and_preserves_generation_provenance() -> None:
    snapshot = build_research_snapshot(
        brief=_brief(),
        objectives=[_objective()],
        assessments=[_assessment()],
        prerequisites=[],
        course_outline=_course(),
        lessons=[_lesson()],
        generation_provenance=GenerationProvenance(
            research_brief_id="brief-1",
            instructional_design_policy_id="pai_instructional_design",
            instructional_design_policy_version="0.1",
            prompt_versions={OBJECTIVE_DESIGN_SCHEMA_ID: "0.1"},
            output_schema_versions={OBJECTIVE_DESIGN_SCHEMA_ID: "0.1"},
            provider="fixture-provider",
            model="fixture-model",
            model_revision="fixture-revision",
            generated_at=datetime(2026, 8, 12, tzinfo=UTC),
        ),
    )

    assert snapshot.quality_report.passed is True
    assert (
        snapshot.generation_provenance.output_schema_versions[OBJECTIVE_DESIGN_SCHEMA_ID] == "0.1"
    )
    assert snapshot.lessons[0].lesson_goal == "Practice adapting a technical explanation."
