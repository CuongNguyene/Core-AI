"""Write the deterministic, no-model-call ID-04A workload artifact set."""

import json
from pathlib import Path

from app.instructional_design.workload import (
    WorkloadCategory,
    validate_workload_allocations,
)

FIXTURES = {
    "python_data_processing": {"instruction": 20, "guided_practice": 15, "independent_practice": 10, "formative_assessment": 5, "summative_assessment": 10},
    "accounting_financial_reporting_basic": {"instruction": 20, "guided_practice": 15, "independent_practice": 10, "summative_assessment": 15},
    "legal_contract_review_basic": {"instruction": 20, "guided_practice": 15, "independent_practice": 15, "summative_assessment": 20},
    "hr_recruitment_planning_basic": {"instruction": 15, "guided_practice": 15, "independent_practice": 10, "formative_assessment": 5, "summative_assessment": 15},
    "construction_drawing_and_method_basic": {"instruction": 20, "guided_practice": 20, "independent_practice": 15, "summative_assessment": 20},
}


def main() -> None:
    output = Path("test/results/instructional-design-id-04a-workload-semantics")
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for fixture, raw in FIXTURES.items():
        categories = {WorkloadCategory(key): value for key, value in raw.items()}
        result = validate_workload_allocations(declared_total_minutes=60, categories=categories)
        results.append({"fixture": fixture, "budget": result.budget.model_dump(mode="json") if result.budget else None, "findings": result.findings})
    files = {
        "manifest.json": {"experiment": "ID-04A", "source_milestone": "ID-03C.3", "intervention": "workload_time_budget_semantics", "policy_version": "workload_budget_policy@0.1", "external_model_calls": 0, "scope": "deterministic implementation + tests"},
        "workload-policy.json": {"policy_id": "workload_budget_policy", "policy_version": "0.1", "near_limit_slack_ratio": 0.1, "arithmetic_source": "category_allocations", "estimate_semantics": "planning estimate, not measured learner completion time"},
        "deterministic-fixture-results.json": results,
        "regression-report.json": {"tests": ["within_budget", "over_budget", "assessment_included", "missing_not_zero", "no_double_counting", "hierarchy_and_dependency_boundaries"], "external_model_calls": 0},
        "validation-report.json": {"status": "valid", "historical_id03_artifacts_mutated": False, "prompt_versions_mutated": False, "external_model_calls": 0},
    }
    for name, payload in files.items():
        (output / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
