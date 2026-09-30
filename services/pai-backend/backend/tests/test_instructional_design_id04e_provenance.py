from app.instructional_design.orchestrator import attach_prerequisite_dependency_provenance
from app.instructional_design.schemas import (
    AssessmentDependencyCandidate,
    PrerequisiteBasis,
    PrerequisiteDisposition,
    PrerequisiteSpec,
    PrerequisiteStatus,
)


def _prerequisite(capability: str, disposition: PrerequisiteDisposition) -> PrerequisiteSpec:
    return PrerequisiteSpec(
        id=f"pre-{capability[:8]}",
        capability=capability,
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
        disposition=disposition,
        rationale="explicit rationale",
        required_for_refs=["objective-1"],
    )


def test_missing_provenance_is_recovered_from_matching_dependency_candidate() -> None:
    candidate = AssessmentDependencyCandidate(
        capability="basic drawing conventions",
        reason="needed for the task",
        required_for_refs=["objective-1", "assessment-1"],
    )
    item = _prerequisite(" basic   drawing conventions ", PrerequisiteDisposition.ENTRY_PREREQUISITE)

    recovered = attach_prerequisite_dependency_provenance([item], [candidate])

    assert recovered[0].source_dependency_refs == ["dependency_candidate:basic drawing conventions"]
    assert recovered[0].status is PrerequisiteStatus.CANDIDATE
    assert recovered[0].basis is PrerequisiteBasis.MODEL_PROPOSED


def test_existing_provenance_is_not_overwritten() -> None:
    item = _prerequisite("basic Python syntax", PrerequisiteDisposition.ENTRY_PREREQUISITE).model_copy(
        update={"source_dependency_refs": ["dependency-1"]}
    )
    candidate = AssessmentDependencyCandidate(
        capability="basic Python syntax",
        reason="needed",
        required_for_refs=["objective-1"],
    )

    recovered = attach_prerequisite_dependency_provenance([item], [candidate])

    assert recovered[0].source_dependency_refs == ["dependency-1"]


def test_unmatched_dependency_does_not_get_invented_provenance() -> None:
    item = _prerequisite("advanced derivatives", PrerequisiteDisposition.NOT_REQUIRED)
    candidate = AssessmentDependencyCandidate(
        capability="basic spreadsheet navigation",
        reason="not related",
        required_for_refs=["objective-1"],
    )

    recovered = attach_prerequisite_dependency_provenance([item], [candidate])

    assert recovered[0].source_dependency_refs == []
