from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.instructional_design.schemas import (
    ArtifactProvenance,
    ArtifactSource,
    AssessmentSpec,
    AssessmentTaskSpec,
    CognitiveProcess,
    EvidenceCriterion,
    GenerationProvenance,
    InstructionalDesignQualityReport,
    InstructionalDesignResearchSnapshot,
    KnowledgeDimension,
    LearnerState,
    LearningObjectiveSpec,
    PrerequisiteBasis,
    PrerequisiteSpec,
    PrerequisiteStatus,
    ResearchBriefProvenance,
    ResearchCapability,
    ResearchConstraints,
    ResearchLearningBrief,
    ResearchProvenanceType,
)


def research_brief() -> ResearchLearningBrief:
    return ResearchLearningBrief(
        id="brief-monitoring-v1",
        capability=ResearchCapability(
            id=None,
            name="model monitoring response",
            target_context="research lab",
        ),
        learner_state=LearnerState(
            known=["basic Python"],
            unknown=["operational monitoring experience"],
            evidence_refs=["research:learner-state-1"],
        ),
        desired_performances=["interpret monitoring signals"],
        constraints=ResearchConstraints(estimated_total_minutes=90, language="en"),
        provenance=ResearchBriefProvenance(
            authored_by="researcher-1", created_at=datetime(2026, 8, 12, tzinfo=UTC)
        ),
    )


def observable_objective() -> LearningObjectiveSpec:
    return LearningObjectiveSpec(
        id="objective-monitoring-1",
        brief_id="brief-monitoring-v1",
        performance=(
            "Given a monitoring dashboard, identify evidence of performance degradation "
            "and justify a response"
        ),
        cognitive_process=CognitiveProcess.ANALYZE,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        conditions=["Given a monitoring dashboard"],
        success_criteria=["Identifies a relevant signal", "Justifies a response"],
        capability_refs=["monitoring-response"],
        provenance=ArtifactProvenance(source=ArtifactSource.RESEARCHER_AUTHORED),
    )


def test_research_brief_is_explicitly_research_only_and_not_a_role_profile() -> None:
    brief = research_brief()

    assert brief.provenance.type is ResearchProvenanceType.RESEARCH_FIXTURE
    assert "role_profile" not in brief.model_dump(mode="json")
    assert brief.learner_state.unknown == ["operational monitoring experience"]


def test_observable_objective_has_bloom_metadata_without_role_level() -> None:
    objective = observable_objective()

    assert objective.cognitive_process is CognitiveProcess.ANALYZE
    assert objective.knowledge_dimension is KnowledgeDimension.PROCEDURAL
    assert "role_level" not in objective.model_dump(mode="json")


def test_model_proposed_prerequisite_cannot_be_confirmed() -> None:
    with pytest.raises(ValidationError, match="model_proposed"):
        PrerequisiteSpec(
            id="prerequisite-monitoring-1",
            capability="basic statistics",
            status=PrerequisiteStatus.CONFIRMED,
            basis=PrerequisiteBasis.MODEL_PROPOSED,
        )


def test_research_snapshot_keeps_policy_prompt_schema_and_model_provenance() -> None:
    objective = observable_objective()
    assessment = AssessmentSpec(
        id="assessment-monitoring-1",
        objective_ids=[objective.id],
        capability_claim="Can identify degradation evidence and justify a response.",
        required_evidence=[
            EvidenceCriterion(id="evidence-1", criterion="Identifies a relevant signal")
        ],
        task=AssessmentTaskSpec(
            task_type="scenario_analysis",
            description="Analyze a dashboard scenario.",
            conditions=["Dashboard data supplied"],
        ),
        cognitive_process=CognitiveProcess.ANALYZE,
        provenance=ArtifactProvenance(source=ArtifactSource.MODEL_PROPOSED, provisional=True),
    )
    report = InstructionalDesignQualityReport(
        passed=True,
        findings=[],
        objective_coverage=1.0,
        assessment_coverage=1.0,
        unresolved_prerequisites=[],
        policy_id="pai_instructional_design",
        policy_version="0.1",
    )

    snapshot = InstructionalDesignResearchSnapshot(
        snapshot_version="instructional-design-research-snapshot@0.1",
        brief=research_brief(),
        objectives=[objective],
        assessments=[assessment],
        prerequisites=[],
        course_outline=None,
        lessons=[],
        quality_report=report,
        generation_provenance=GenerationProvenance(
            research_brief_id="brief-monitoring-v1",
            instructional_design_policy_id="pai_instructional_design",
            instructional_design_policy_version="0.1",
            prompt_versions={"instructional_objective_design": "0.1"},
            output_schema_versions={"instructional_objective_design": "0.1"},
            provider="fixture",
            model="fixture-model",
            model_revision="fixture-revision",
            generated_at=datetime(2026, 8, 12, tzinfo=UTC),
        ),
    )

    assert snapshot.generation_provenance.research_brief_id == snapshot.brief.id
    assert snapshot.assessments[0].provenance.provisional is True


def test_research_snapshot_rejects_generation_policy_that_differs_from_quality_report() -> None:
    objective = observable_objective()
    report = InstructionalDesignQualityReport(
        passed=True,
        findings=[],
        objective_coverage=1.0,
        assessment_coverage=1.0,
        unresolved_prerequisites=[],
        policy_id="pai_instructional_design",
        policy_version="0.1",
    )
    provenance = GenerationProvenance(
        research_brief_id="brief-monitoring-v1",
        instructional_design_policy_id="pai_instructional_design",
        instructional_design_policy_version="0.2",
        generated_at=datetime(2026, 8, 12, tzinfo=UTC),
    )

    with pytest.raises(ValidationError, match="policy"):
        InstructionalDesignResearchSnapshot(
            snapshot_version="instructional-design-research-snapshot@0.1",
            brief=research_brief(),
            objectives=[objective],
            assessments=[],
            prerequisites=[],
            course_outline=None,
            lessons=[],
            quality_report=report,
            generation_provenance=provenance,
        )
