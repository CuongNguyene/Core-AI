from app.instructional_design.practice_coverage import (
    CoverageStatus,
    evaluate_practice_coverage,
    planner_coverage_requirements,
)
from app.instructional_design.schemas import (
    ArtifactProvenance,
    ArtifactSource,
    AssessmentCapabilityRequirement,
    AssessmentRole,
    AssessmentSpec,
    AssessmentTaskSpec,
    CognitiveProcess,
    CourseOutline,
    InstructionalPattern,
    KnowledgeDimension,
    LearnerState,
    LearningObjectiveSpec,
    LessonSpec,
    ModuleOutline,
    ResearchCapability,
    ResearchConstraints,
    ResearchLearningBrief,
    ResearchProvenanceType,
)

_AUTHORED = ArtifactProvenance(source=ArtifactSource.RESEARCHER_AUTHORED)


def _brief() -> ResearchLearningBrief:
    return ResearchLearningBrief(
        id="brief-1",
        capability=ResearchCapability(name="generic capability"),
        learner_state=LearnerState(),
        desired_performances=["perform target"],
        constraints=ResearchConstraints(estimated_total_minutes=60),
        provenance={"type": ResearchProvenanceType.RESEARCH_FIXTURE},
    )


def _objective() -> LearningObjectiveSpec:
    return LearningObjectiveSpec(
        id="obj-1", brief_id="brief-1", performance="perform target",
        cognitive_process=CognitiveProcess.APPLY,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        provenance=_AUTHORED,
    )


def _assessment(role: AssessmentRole = AssessmentRole.SUMMATIVE) -> AssessmentSpec:
    return AssessmentSpec(
        id="asmt-s1", objective_ids=["obj-1"], capability_claim="target capability",
        required_evidence=[], task=AssessmentTaskSpec(task_type="task", description="perform"),
        cognitive_process=CognitiveProcess.APPLY, role=role,
        required_capabilities=[AssessmentCapabilityRequirement(name="cap-a", objective_ids=["obj-1"])],
        provenance=_AUTHORED,
    )


def _course() -> CourseOutline:
    return CourseOutline(
        id="course-1", brief_id="brief-1", objective_ids=["obj-1"],
        modules=[ModuleOutline(id="module-1", title="module", objective_ids=["obj-1"], lesson_ids=[])],
        provenance=_AUTHORED,
    )


def _lesson(lesson_id: str, pattern: InstructionalPattern, *, summative: bool = False, formative: list[str] | None = None) -> LessonSpec:
    return LessonSpec(
        id=lesson_id, module_id="module-1", objective_ids=["obj-1"], lesson_goal="goal",
        instructional_pattern=pattern, expected_learner_activity="activity",
        formative_assessment_ids=formative or [],
        summative_assessment_ids=["asmt-s1"] if summative else [],
        provenance=_AUTHORED,
    )


def test_instruction_and_guided_practice_before_summative_is_covered() -> None:
    result = evaluate_practice_coverage(
        assessments=[_assessment()], course_outline=_course(),
        lessons=[_lesson("l1", InstructionalPattern.EXPLANATION), _lesson("l2", InstructionalPattern.GUIDED_PRACTICE), _lesson("l3", InstructionalPattern.INDEPENDENT_PRACTICE, summative=True)],
    )
    assert result.traces[0].status is CoverageStatus.COVERED
    assert result.findings == []


def test_instruction_without_prior_practice_is_partial() -> None:
    result = evaluate_practice_coverage(
        assessments=[_assessment()], course_outline=_course(),
        lessons=[_lesson("l1", InstructionalPattern.EXPLANATION), _lesson("l2", InstructionalPattern.INDEPENDENT_PRACTICE, summative=True)],
    )
    assert result.traces[0].status is CoverageStatus.PARTIALLY_COVERED
    assert {f.code for f in result.findings} == {"practice_before_summative_missing"}


def test_no_prior_instruction_or_practice_is_not_covered() -> None:
    result = evaluate_practice_coverage(
        assessments=[_assessment()], course_outline=_course(),
        lessons=[_lesson("l1", InstructionalPattern.INDEPENDENT_PRACTICE, summative=True)],
    )
    assert result.traces[0].status is CoverageStatus.NOT_COVERED
    assert "assessment_requirement_not_taught" in {f.code for f in result.findings}


def test_summative_cannot_be_its_own_practice() -> None:
    result = evaluate_practice_coverage(
        assessments=[_assessment()], course_outline=_course(),
        lessons=[_lesson("l1", InstructionalPattern.EXPLANATION, summative=True, formative=["asmt-s1"])],
    )
    assert "summative_used_as_practice" in {f.code for f in result.findings}


def test_practice_after_summative_does_not_count() -> None:
    result = evaluate_practice_coverage(
        assessments=[_assessment()], course_outline=_course(),
        lessons=[_lesson("l1", InstructionalPattern.EXPLANATION, summative=True), _lesson("l2", InstructionalPattern.GUIDED_PRACTICE)],
    )
    assert result.traces[0].status is CoverageStatus.NOT_COVERED
    assert "practice_reference_after_summative" in {f.code for f in result.findings}


def test_prior_valid_formative_counts_as_practice() -> None:
    formative = _assessment(AssessmentRole.FORMATIVE).model_copy(update={"id": "asmt-f1"})
    result = evaluate_practice_coverage(
        assessments=[formative, _assessment()], course_outline=_course(),
        lessons=[_lesson("l0", InstructionalPattern.EXPLANATION), _lesson("l1", InstructionalPattern.GUIDED_PRACTICE, formative=["asmt-f1"]), _lesson("l2", InstructionalPattern.INDEPENDENT_PRACTICE, summative=True)],
    )
    assert result.traces[0].status is CoverageStatus.COVERED


def test_entry_prerequisite_and_supporting_dependency_do_not_create_requirements() -> None:
    result = evaluate_practice_coverage(
        assessments=[_assessment()], course_outline=_course(),
        lessons=[_lesson("l1", InstructionalPattern.EXPLANATION), _lesson("l2", InstructionalPattern.GUIDED_PRACTICE), _lesson("l3", InstructionalPattern.INDEPENDENT_PRACTICE, summative=True)],
    )
    assert len(result.traces) == 1


def test_planner_requirements_are_explicit_and_only_summative() -> None:
    formative = _assessment(AssessmentRole.FORMATIVE).model_copy(update={"id": "asmt-f1"})
    requirements = planner_coverage_requirements([formative, _assessment()])
    assert requirements == [{
        "assessment_id": "asmt-s1",
        "objective_refs": ["obj-1"],
        "capability_ref": "cap-a",
        "source_requirement_ref": "asmt-s1:required_capabilities:0",
    }]
