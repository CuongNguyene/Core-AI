from app.instructional_design.quality_gate import evaluate_instructional_design
from app.instructional_design.schemas import (
    ArtifactProvenance,
    ArtifactSource,
    AssessmentCapabilityRequirement,
    AssessmentSpec,
    AssessmentTaskSpec,
    CognitiveProcess,
    CourseOutline,
    EvidenceCriterion,
    InstructionalPattern,
    KnowledgeDimension,
    LearnerState,
    LearningObjectiveSpec,
    LessonSpec,
    ModuleOutline,
    PrerequisiteBasis,
    PrerequisiteClassification,
    PrerequisiteSpec,
    PrerequisiteStatus,
    ResearchBriefProvenance,
    ResearchCapability,
    ResearchConstraints,
    ResearchLearningBrief,
)

AUTHORED = ArtifactProvenance(source=ArtifactSource.RESEARCHER_AUTHORED)


def brief() -> ResearchLearningBrief:
    return ResearchLearningBrief(
        id="brief-1",
        capability=ResearchCapability(name="data processing"),
        learner_state=LearnerState(known=["known-capability"]),
        desired_performances=["transform tabular data"],
        constraints=ResearchConstraints(),
        provenance=ResearchBriefProvenance(),
    )


def objective(
    objective_id: str = "objective-1",
    *,
    performance: str = "Given a dataset, transform invalid values and justify the choice.",
    cognitive: CognitiveProcess = CognitiveProcess.APPLY,
    prerequisites: list[str] | None = None,
    capabilities: list[str] | None = None,
) -> LearningObjectiveSpec:
    return LearningObjectiveSpec(
        id=objective_id,
        brief_id="brief-1",
        performance=performance,
        cognitive_process=cognitive,
        knowledge_dimension=KnowledgeDimension.PROCEDURAL,
        success_criteria=["Produces a justified transformation"],
        prerequisite_refs=prerequisites or [],
        capability_refs=capabilities or [f"capability-{objective_id}"],
        provenance=AUTHORED,
    )


def assessment(
    assessment_id: str = "assessment-1",
    *,
    objective_ids: list[str] | None = None,
    cognitive: CognitiveProcess = CognitiveProcess.APPLY,
    required_capabilities: list[str] | None = None,
    typed_required_capabilities: list[str] | None = None,
    is_summative: bool = True,
) -> AssessmentSpec:
    return AssessmentSpec(
        id=assessment_id,
        objective_ids=["objective-1"] if objective_ids is None else objective_ids,
        capability_claim="Can transform invalid dataset values.",
        required_evidence=[
            EvidenceCriterion(id=f"evidence-{assessment_id}", criterion="Valid output")
        ],
        task=AssessmentTaskSpec(
            task_type="practical_task",
            description="Transform supplied records and explain the result.",
        ),
        cognitive_process=cognitive,
        is_summative=is_summative,
        required_capability_refs=[] if required_capabilities is None else required_capabilities,
        required_capabilities=[
            AssessmentCapabilityRequirement(
                name=value,
                objective_ids=["objective-1"],
            )
            for value in (typed_required_capabilities or [])
        ],
        provenance=AUTHORED,
    )


def course_and_lessons(
    objectives: list[LearningObjectiveSpec], *, lesson_objective_ids: list[str] | None = None
) -> tuple[CourseOutline, list[LessonSpec]]:
    lesson_ids = [f"lesson-{item.id}" for item in objectives]
    module = ModuleOutline(
        id="module-1",
        title="Transform data",
        objective_ids=[item.id for item in objectives],
        lesson_ids=lesson_ids,
    )
    course = CourseOutline(
        id="course-1",
        brief_id="brief-1",
        objective_ids=[item.id for item in objectives],
        modules=[module],
        provenance=AUTHORED,
    )
    lessons = [
        LessonSpec(
            id=lesson_id,
            module_id="module-1",
            objective_ids=(
                lesson_objective_ids
                if index == 0 and lesson_objective_ids is not None
                else [item.id]
            ),
            lesson_goal="Practice a data transformation.",
            instructional_pattern=InstructionalPattern.GUIDED_PRACTICE,
            expected_learner_activity="Transform supplied data and explain the choice.",
            provenance=AUTHORED,
        )
        for index, (item, lesson_id) in enumerate(zip(objectives, lesson_ids, strict=True))
    ]
    return course, lessons


def codes(report: object) -> set[str]:
    return {finding.code for finding in report.findings}  # type: ignore[attr-defined]


def test_observable_objective_with_aligned_assessment_and_lesson_passes() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment()],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert "objective_not_observable" not in codes(report)
    assert report.passed is True


def test_apply_objective_without_practice_is_reported() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    lessons = [lessons[0].model_copy(update={"instructional_pattern": InstructionalPattern.EXPLANATION})]

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment()],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert "summative_without_prior_practice" in codes(report)
    assert report.passed is False


def test_vague_objective_is_reported_without_verb_only_rejection() -> None:
    item = objective(performance="Understand MLOps")
    course, lessons = course_and_lessons([item])

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment()],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert "objective_not_observable" in codes(report)


def test_objective_and_assessment_traceability_findings_are_separate() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    orphan = assessment("assessment-orphan", objective_ids=[])

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[orphan],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert {"objective_without_assessment", "orphan_assessment"} <= codes(report)


def test_summative_assessment_below_objective_cognitive_demand_is_error() -> None:
    item = objective(cognitive=CognitiveProcess.CREATE)
    course, lessons = course_and_lessons([item])

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment(cognitive=CognitiveProcess.REMEMBER)],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    finding = next(
        finding for finding in report.findings if finding.code == "insufficient_cognitive_demand"
    )
    assert finding.severity.value == "error"


def test_orphan_lesson_module_and_untaught_objective_are_reported() -> None:
    item = objective()
    orphan_module = ModuleOutline(
        id="module-orphan", title="Unaligned", objective_ids=[], lesson_ids=["lesson-orphan"]
    )
    course = CourseOutline(
        id="course-1",
        brief_id="brief-1",
        objective_ids=[item.id],
        modules=[orphan_module],
        provenance=AUTHORED,
    )
    orphan_lesson = LessonSpec(
        id="lesson-orphan",
        module_id="module-orphan",
        objective_ids=[],
        lesson_goal="Unaligned lesson",
        instructional_pattern=InstructionalPattern.EXPLANATION,
        expected_learner_activity="Read an explanation.",
        provenance=AUTHORED,
    )

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment()],
        prerequisites=[],
        course_outline=course,
        lessons=[orphan_lesson],
    )

    assert {"orphan_module", "orphan_lesson", "objective_not_taught"} <= codes(report)


def test_confirmed_prerequisite_cycle_is_blocking() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    prerequisites = [
        PrerequisiteSpec(
            id="prerequisite-a",
            capability="A",
            status=PrerequisiteStatus.CONFIRMED,
            basis=PrerequisiteBasis.RESEARCHER_AUTHORED,
            requires_prerequisite_refs=["prerequisite-b"],
        ),
        PrerequisiteSpec(
            id="prerequisite-b",
            capability="B",
            status=PrerequisiteStatus.CONFIRMED,
            basis=PrerequisiteBasis.RESEARCHER_AUTHORED,
            requires_prerequisite_refs=["prerequisite-a"],
        ),
    ]

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment()],
        prerequisites=prerequisites,
        course_outline=course,
        lessons=lessons,
    )

    finding = next(finding for finding in report.findings if finding.code == "prerequisite_cycle")
    assert finding.severity.value == "blocking"
    assert report.passed is False


def test_confirmed_prerequisite_taught_after_dependent_lesson_is_reported() -> None:
    prerequisite_objective = objective("objective-prerequisite")
    dependent_objective = objective("objective-dependent", prerequisites=["prerequisite-1"])
    course, lessons = course_and_lessons([dependent_objective, prerequisite_objective])
    prerequisite = PrerequisiteSpec(
        id="prerequisite-1",
        capability="basic tabular data",
        status=PrerequisiteStatus.CONFIRMED,
        basis=PrerequisiteBasis.RESEARCHER_AUTHORED,
        teaching_objective_id=prerequisite_objective.id,
    )

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[prerequisite_objective, dependent_objective],
        assessments=[
            assessment("assessment-dependent", objective_ids=[dependent_objective.id]),
            assessment("assessment-prerequisite", objective_ids=[prerequisite_objective.id]),
        ],
        prerequisites=[prerequisite],
        course_outline=course,
        lessons=lessons,
    )

    assert "prerequisite_order_violation" in codes(report)


def test_model_proposed_candidate_is_unresolved_but_never_promoted() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    candidate = PrerequisiteSpec(
        id="prerequisite-candidate",
        capability="statistics",
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
    )

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment()],
        prerequisites=[candidate],
        course_outline=course,
        lessons=lessons,
    )

    assert report.unresolved_prerequisites == [candidate.id]
    assert candidate.status is PrerequisiteStatus.CANDIDATE


def test_uncovered_assessment_dependency_and_report_are_deterministic() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    fixture_brief = brief()
    fixture_assessments = [assessment(required_capabilities=["uncovered-capability"])]
    first = evaluate_instructional_design(
        brief=fixture_brief,
        objectives=[item],
        assessments=fixture_assessments,
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )
    second = evaluate_instructional_design(
        brief=fixture_brief,
        objectives=[item],
        assessments=fixture_assessments,
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert "assessment_dependency_not_covered" in codes(first)
    assert first == second


def test_candidate_prerequisite_does_not_count_as_assessment_dependency_coverage() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    unresolved = PrerequisiteSpec(
        id="prerequisite-candidate",
        capability="candidate-only capability",
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
    )

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment(required_capabilities=[unresolved.capability])],
        prerequisites=[unresolved],
        course_outline=course,
        lessons=lessons,
    )

    assert "assessment_dependency_not_covered" in codes(report)
    assert unresolved.status is PrerequisiteStatus.CANDIDATE


def test_artifact_id_in_assessment_capability_field_is_a_semantic_error() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    item_assessment = assessment(required_capabilities=["assessment-1"])

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[item_assessment],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert "assessment_capability_ref_is_artifact_id" in codes(report)


def test_identical_legacy_and_typed_dependency_is_checked_once_with_no_conflict() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    item_assessment = assessment(
        required_capabilities=["transform tabular data"],
        typed_required_capabilities=["Transform   Tabular Data"],
    )

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[item_assessment],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert "conflicting_dependency_semantics" not in codes(report)
    assert sum(
        finding.code == "assessment_dependency_not_covered" for finding in report.findings
    ) == 1


def test_conflicting_legacy_and_typed_dependency_is_explicit() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    item_assessment = assessment(
        required_capabilities=["transform tabular data"],
        typed_required_capabilities=["database administration"],
    )

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[item_assessment],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert "conflicting_dependency_semantics" in codes(report)


def test_summative_assessment_cannot_be_lesson_formative_reference() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    lessons = [lessons[0].model_copy(update={"formative_assessment_ids": ["assessment-1"]})]

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment()],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert "lesson_formative_assessment_is_not_formative" in codes(report)


def test_lesson_objective_must_be_owned_by_its_module_and_course_outline() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    course = course.model_copy(
        update={
            "objective_ids": [],
            "modules": [course.modules[0].model_copy(update={"objective_ids": []})],
        }
    )

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment()],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert {
        "lesson_objective_not_in_course_outline",
        "lesson_objective_not_owned_by_module",
    } <= codes(report)


def test_declared_duration_overflow_requires_a_planning_warning() -> None:
    item = objective()
    course, lessons = course_and_lessons([item])
    course = course.model_copy(
        update={
            "estimated_minutes": 30,
            "modules": [course.modules[0].model_copy(update={"estimated_minutes": 45})],
        }
    )

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment()],
        prerequisites=[],
        course_outline=course,
        lessons=lessons,
    )

    assert "scope_time_conflict_missing_planning_warning" in codes(report)


def test_required_candidate_with_vague_rationale_is_a_review_finding_not_confirmation() -> None:
    item = objective(prerequisites=["prerequisite-candidate"])
    course, lessons = course_and_lessons([item])
    candidate = PrerequisiteSpec(
        id="prerequisite-candidate",
        capability="background knowledge",
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
        classification=PrerequisiteClassification.REQUIRED_PREREQUISITE,
        rationale="helpful",
        required_for_refs=[item.id],
    )

    report = evaluate_instructional_design(
        brief=brief(),
        objectives=[item],
        assessments=[assessment()],
        prerequisites=[candidate],
        course_outline=course,
        lessons=lessons,
    )

    assert "prerequisite_candidate_insufficient_rationale" in codes(report)
    assert candidate.status is PrerequisiteStatus.CANDIDATE
