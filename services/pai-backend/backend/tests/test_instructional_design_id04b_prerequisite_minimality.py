from app.instructional_design.contracts import (
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V033,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
)
from app.instructional_design.prerequisite_minimality import (
    validate_prerequisite_dispositions,
)
from app.instructional_design.prompts import instructional_design_experiment_prompt_templates
from app.instructional_design.schemas import (
    PrerequisiteBasis,
    PrerequisiteDisposition,
    PrerequisiteSpec,
    PrerequisiteStatus,
)


def _candidate(
    capability: str,
    disposition: PrerequisiteDisposition,
    *,
    rationale: str | None = "source dependency is required before entry",
    source: str = "dependency-1",
) -> PrerequisiteSpec:
    return PrerequisiteSpec(
        id=f"prereq-{capability.replace(' ', '-')}",
        capability=capability,
        status=PrerequisiteStatus.CANDIDATE,
        basis=PrerequisiteBasis.MODEL_PROPOSED,
        disposition=disposition,
        rationale=rationale,
        source_dependency_refs=[source],
    )


def test_entry_prerequisite_remains_candidate_with_rationale_and_provenance() -> None:
    item = _candidate("basic Python syntax", PrerequisiteDisposition.ENTRY_PREREQUISITE)
    assert validate_prerequisite_dispositions([item]) == []
    assert item.status is PrerequisiteStatus.CANDIDATE
    assert item.basis is PrerequisiteBasis.MODEL_PROPOSED
    assert item.source_dependency_refs == ["dependency-1"]


def test_in_course_support_is_valid_and_not_confirmed() -> None:
    item = _candidate("data-quality criteria", PrerequisiteDisposition.IN_COURSE_SUPPORT)
    assert validate_prerequisite_dispositions([item]) == []
    assert item.status is PrerequisiteStatus.CANDIDATE


def test_not_required_is_preserved_in_trace() -> None:
    item = _candidate("advanced derivative pricing", PrerequisiteDisposition.NOT_REQUIRED)
    assert validate_prerequisite_dispositions([item]) == []
    assert item.source_dependency_refs


def test_entry_requires_rationale() -> None:
    item = _candidate("basic Python syntax", PrerequisiteDisposition.ENTRY_PREREQUISITE, rationale=None)
    findings = validate_prerequisite_dispositions([item])
    assert [finding.code for finding in findings] == ["prerequisite_entry_rationale_missing"]


def test_contradictory_dispositions_fail_closed() -> None:
    first = _candidate("contract terminology", PrerequisiteDisposition.ENTRY_PREREQUISITE)
    second = _candidate(
        "contract terminology", PrerequisiteDisposition.IN_COURSE_SUPPORT, source="dependency-1"
    )
    findings = validate_prerequisite_dispositions([first, second])
    assert [finding.code for finding in findings] == ["prerequisite_disposition_conflict"]


def test_model_proposed_entry_cannot_be_confirmed_implicitly() -> None:
    item = _candidate("basic drawing symbols", PrerequisiteDisposition.ENTRY_PREREQUISITE)
    item = item.model_copy(update={"status": PrerequisiteStatus.CONFIRMED})
    findings = validate_prerequisite_dispositions([item])
    assert [finding.code for finding in findings] == ["prerequisite_disposition_auto_confirmation"]


def test_minimality_prompt_is_patch_versioned_and_historical_prompt_is_unchanged() -> None:
    current = {
        item.template_id: item
        for item in instructional_design_experiment_prompt_templates(
            version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V033
        )
    }
    historical = {
        item.template_id: item
        for item in instructional_design_experiment_prompt_templates(
            version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031
        )
    }
    assert "entry_prerequisite" in current[PREREQUISITE_PROPOSAL_SCHEMA_ID].system_instruction.casefold()
    assert "entry_prerequisite" not in historical[PREREQUISITE_PROPOSAL_SCHEMA_ID].system_instruction.casefold()
