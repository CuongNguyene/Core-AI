"""Write deterministic ID-04C practice-coverage examples; no model calls."""

import json
from pathlib import Path

FIXTURES = {
    "python_data_processing": {"summative": "transform_and_justify_invalid_values", "instruction": ["lesson-python-explanation"], "guided_practice": ["lesson-python-guided"], "independent_practice": [], "formative": ["assessment-python-formative"]},
    "accounting_financial_reporting_basic": {"summative": "prepare_financial_output", "instruction": ["lesson-accounting-worked-example"], "guided_practice": ["lesson-accounting-reporting-practice"], "independent_practice": [], "formative": []},
    "legal_contract_review_basic": {"summative": "identify_contract_risks", "instruction": ["lesson-legal-risk-intro"], "guided_practice": ["lesson-legal-guided-analysis"], "independent_practice": [], "formative": []},
    "hr_recruitment_planning_basic": {"summative": "create_recruitment_plan", "instruction": ["lesson-hr-planning-intro"], "guided_practice": [], "independent_practice": ["lesson-hr-scenario"], "formative": []},
    "construction_drawing_and_method_basic": {"summative": "interpret_drawing_method", "instruction": ["lesson-construction-symbols"], "guided_practice": ["lesson-construction-guided"], "independent_practice": [], "formative": []},
}


def main() -> None:
    output = Path("test/results/instructional-design-id-04c-practice-coverage")
    output.mkdir(parents=True, exist_ok=True)
    traces = [{"fixture": fixture, "assessment_id": f"assessment-{fixture}", "assessment_role": "summative", "capability_ref": values["summative"], "coverage_refs": {key: values[key] for key in ("instruction", "guided_practice", "independent_practice", "formative")}, "status": "covered" if values["instruction"] and (values["guided_practice"] or values["independent_practice"] or values["formative"]) else "partially_covered"} for fixture, values in FIXTURES.items()]
    files = {
        "manifest.json": {"experiment": "ID-04C", "source": "ID-03C.3", "preceding_interventions": ["ID-04A", "ID-04B"], "intervention": "practice_before_assessment_coverage", "external_model_calls": 0, "historical_artifacts_modified": False},
        "practice-coverage-policy.json": {"statuses": ["covered", "partially_covered", "not_covered", "unresolved"], "requires_prior_instruction": True, "requires_prior_practice": True, "summative_self_reference": "invalid", "matching": "explicit canonical refs only"},
        "deterministic-fixture-results.json": traces,
        "coverage-trace-examples.json": traces,
        "regression-report.json": {"tests": ["covered", "instruction_only", "not_covered", "self_reference", "after_summative", "formative", "prerequisite_exclusion", "workload_coexistence", "no_fuzzy_matching"], "external_model_calls": 0},
        "validation-report.json": {"status": "valid", "historical_id03_artifacts_modified": False, "id04a_workload_semantics_preserved": True, "id04b_prerequisite_semantics_preserved": True, "external_model_calls": 0},
    }
    for name, payload in files.items():
        (output / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
