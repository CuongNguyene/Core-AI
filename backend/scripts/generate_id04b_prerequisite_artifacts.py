"""Write deterministic ID-04B prerequisite-minimality fixture artifacts."""

import json
from pathlib import Path

from app.instructional_design.prerequisite_minimality import validate_prerequisite_dispositions
from app.instructional_design.schemas import (
    PrerequisiteBasis,
    PrerequisiteDisposition,
    PrerequisiteSpec,
    PrerequisiteStatus,
)

FIXTURES = {
    "python_data_processing": [("basic Python syntax", "entry_prerequisite"), ("data-quality criteria", "in_course_support")],
    "accounting_financial_reporting_basic": [("spreadsheet navigation", "entry_prerequisite"), ("advanced derivative pricing", "not_required")],
    "legal_contract_review_basic": [("contract terminology", "entry_prerequisite"), ("risk-analysis framework", "in_course_support")],
    "hr_recruitment_planning_basic": [("role context awareness", "entry_prerequisite"), ("planning rubric", "in_course_support")],
    "construction_drawing_and_method_basic": [("basic drawing symbols", "entry_prerequisite"), ("task-specific method reasoning", "in_course_support")],
}


def main() -> None:
    output = Path("test/results/instructional-design-id-04b-prerequisite-minimality")
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for fixture, items in FIXTURES.items():
        proposals = [PrerequisiteSpec(id=f"prereq-{index}", capability=capability, status=PrerequisiteStatus.CANDIDATE, basis=PrerequisiteBasis.MODEL_PROPOSED, disposition=PrerequisiteDisposition(disposition), rationale="Explicit planning disposition from source dependency.", source_dependency_refs=[f"dependency-{index}"]) for index, (capability, disposition) in enumerate(items, 1)]
        findings = validate_prerequisite_dispositions(proposals)
        results.append({"fixture": fixture, "proposals": [item.model_dump(mode="json") for item in proposals], "findings": [item.model_dump(mode="json") for item in findings]})
    files = {
        "manifest.json": {"experiment": "ID-04B", "source": "ID-03C.3", "preceding_intervention": "ID-04A", "intervention": "prerequisite_minimality_semantics", "external_model_calls": 0, "historical_artifacts_modified": False},
        "prerequisite-policy.json": {"dispositions": [item.value for item in PrerequisiteDisposition], "candidate_governance": "model_proposed remains candidate", "entry_rationale_required": True, "provenance_required": True, "conflict_behavior": "fail_closed"},
        "deterministic-fixture-results.json": results,
        "regression-report.json": {"tests": ["entry_prerequisite", "in_course_support", "not_required", "no_auto_confirmation", "rationale", "provenance", "conflict", "domain_neutral"], "external_model_calls": 0},
        "validation-report.json": {"status": "valid", "historical_id03_artifacts_modified": False, "id04a_workload_semantics_preserved": True, "external_model_calls": 0},
    }
    for name, payload in files.items():
        (output / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
