from app.instructional_design.contracts import AssessmentDependencyCandidate
from app.instructional_design.dependency_normalizer import normalize_assessment_dependencies
from app.instructional_design.fixtures import research_fixture_bundles
from app.instructional_design.orchestrator import build_research_snapshot
from app.instructional_design.schemas import (
    ArtifactProvenance,
    ArtifactSource,
    AssessmentCapabilityRequirement,
    AssessmentDependencyRole,
    AssessmentDependencyStatus,
    AssessmentRole,
    AssessmentSpec,
    AssessmentTaskSpec,
    CognitiveProcess,
    DependencySourceType,
)


def assessment(
    *,
    legacy: list[str] | None = None,
    typed: list[str] | None = None,
) -> AssessmentSpec:
    return AssessmentSpec(
        id="assessment-001",
        objective_ids=["objective-001"],
        capability_claim="Transform tabular data safely.",
        task=AssessmentTaskSpec(task_type="practical", description="Transform data."),
        cognitive_process=CognitiveProcess.APPLY,
        role=AssessmentRole.SUMMATIVE,
        required_capability_refs=legacy or [],
        required_capabilities=[
            AssessmentCapabilityRequirement(name=value, objective_ids=["objective-001"])
            for value in typed or []
        ],
        provenance=ArtifactProvenance(source=ArtifactSource.MODEL_PROPOSED, provisional=True),
    )


def test_identical_legacy_and_typed_capability_normalizes_once_with_two_sources() -> None:
    result = normalize_assessment_dependencies(
        assessment(legacy=["Transform   Tabular Data"], typed=["transform tabular data"])
    )

    assert len(result.dependencies) == 1
    dependency = result.dependencies[0]
    assert dependency.capability_ref == "transform tabular data"
    assert dependency.dependency_role is AssessmentDependencyRole.REQUIRED_CAPABILITY
    assert dependency.status is AssessmentDependencyStatus.CONFIRMED
    assert {source.type for source in dependency.provenance.sources} == {
        DependencySourceType.TYPED_REQUIRED_CAPABILITY,
        DependencySourceType.LEGACY_COMPATIBILITY,
    }
    assert result.findings == []


def test_conflicting_legacy_and_typed_capability_emits_explicit_finding() -> None:
    result = normalize_assessment_dependencies(
        assessment(legacy=["transform tabular data"], typed=["database administration"])
    )

    assert len(result.dependencies) == 2
    assert [finding.code for finding in result.findings] == [
        "conflicting_dependency_semantics"
    ]


def test_dependency_candidate_is_preserved_as_candidate_supporting_dependency() -> None:
    result = normalize_assessment_dependencies(
        assessment(typed=["transform tabular data"]),
        dependency_candidates=[
            AssessmentDependencyCandidate(
                capability="understand data types",
                reason="Needed to choose a safe transformation.",
                required_for_refs=["assessment-001"],
            )
        ],
    )

    candidate = next(
        item
        for item in result.dependencies
        if item.capability_ref == "understand data types"
    )
    assert candidate.dependency_role is AssessmentDependencyRole.SUPPORTING_DEPENDENCY
    assert candidate.status is AssessmentDependencyStatus.CANDIDATE
    assert candidate.provenance.sources[0].type is DependencySourceType.DEPENDENCY_CANDIDATE


def test_normalization_does_not_promote_model_proposed_prerequisite() -> None:
    candidate = AssessmentDependencyCandidate(
        capability="basic data types",
        reason="Needed to choose a safe transformation.",
        required_for_refs=["assessment-001"],
    )

    result = normalize_assessment_dependencies(assessment(), dependency_candidates=[candidate])

    assert next(
        item for item in result.dependencies if item.capability_ref == "basic data types"
    ).status is AssessmentDependencyStatus.CANDIDATE


def test_dependency_candidate_provenance_survives_snapshot_boundary() -> None:
    bundle = next(iter(research_fixture_bundles().values()))
    assessment_id = bundle.assessments[0].id
    candidate = AssessmentDependencyCandidate(
        capability="supporting data literacy",
        reason="Needed to interpret the task input.",
        required_for_refs=[assessment_id],
    )

    snapshot = build_research_snapshot(
        brief=bundle.brief,
        objectives=bundle.objectives,
        assessments=bundle.assessments,
        prerequisites=bundle.prerequisites,
        course_outline=bundle.course_outline,
        lessons=bundle.lessons,
        dependency_candidates=[candidate],
        generation_provenance=bundle.snapshot.generation_provenance,
    )

    supporting = next(
        item
        for item in snapshot.canonical_dependencies
        if item.capability_ref == "supporting data literacy"
    )
    assert snapshot.dependency_candidates == [candidate]
    assert supporting.status is AssessmentDependencyStatus.CANDIDATE
    assert supporting.provenance.sources[0].type is DependencySourceType.DEPENDENCY_CANDIDATE


def test_smoke4_python_duplicate_requirements_collapse_without_hiding_scope_creep() -> None:
    """The two requirements from the recovered Python trace are checked once each."""

    smoke4_requirements = [
        "basic Python programming",
        "written justification and reasoning communication",
    ]

    for requirement in smoke4_requirements:
        result = normalize_assessment_dependencies(
            assessment(legacy=[requirement], typed=[requirement])
        )

        assert len(result.dependencies) == 1
        assert result.findings == []
        assert {
            source.type for source in result.dependencies[0].provenance.sources
        } == {
            DependencySourceType.TYPED_REQUIRED_CAPABILITY,
            DependencySourceType.LEGACY_COMPATIBILITY,
        }
