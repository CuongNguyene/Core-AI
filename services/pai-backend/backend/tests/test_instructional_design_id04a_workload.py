from app.instructional_design.contracts import (
    COURSE_PLANNING_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V032,
    LESSON_PLANNING_SCHEMA_ID,
)
from app.instructional_design.prompts import instructional_design_experiment_prompt_templates
from app.instructional_design.quality_gate import evaluate_instructional_design
from app.instructional_design.workload import (
    WorkloadBudgetStatus,
    WorkloadCategory,
    calculate_workload_budget,
    validate_workload_allocations,
)


def test_within_budget_categories_are_deterministic() -> None:
    result = validate_workload_allocations(
        declared_total_minutes=60,
        categories={
            WorkloadCategory.INSTRUCTION: 20,
            WorkloadCategory.GUIDED_PRACTICE: 15,
            WorkloadCategory.INDEPENDENT_PRACTICE: 10,
            WorkloadCategory.FORMATIVE_ASSESSMENT: 5,
            WorkloadCategory.SUMMATIVE_ASSESSMENT: 10,
        },
    )
    assert result.budget is not None
    assert result.budget.status is WorkloadBudgetStatus.WITHIN_BUDGET
    assert result.budget.over_budget_minutes == 0


def test_over_budget_is_a_warning_and_keeps_arithmetic_visible() -> None:
    result = validate_workload_allocations(
        declared_total_minutes=60,
        categories={
            WorkloadCategory.INSTRUCTION: 25,
            WorkloadCategory.GUIDED_PRACTICE: 20,
            WorkloadCategory.INDEPENDENT_PRACTICE: 15,
            WorkloadCategory.FORMATIVE_ASSESSMENT: 10,
            WorkloadCategory.SUMMATIVE_ASSESSMENT: 20,
        },
    )
    assert result.budget and result.budget.planned_total_minutes == 90
    assert result.budget.status is WorkloadBudgetStatus.OVER_BUDGET
    assert result.budget.over_budget_minutes == 30
    assert result.findings[0]["code"] == "workload_time_budget_exceeded"
    assert result.findings[0]["severity"] == "warning"


def test_assessment_time_is_included_and_missing_is_not_zero() -> None:
    result = validate_workload_allocations(
        declared_total_minutes=60,
        categories={
            WorkloadCategory.INSTRUCTION: 30,
            WorkloadCategory.GUIDED_PRACTICE: 20,
            WorkloadCategory.SUMMATIVE_ASSESSMENT: 20,
        },
    )
    assert result.budget and result.budget.planned_total_minutes == 70
    assert result.budget.over_budget_minutes == 10
    missing = validate_workload_allocations(
        declared_total_minutes=60,
        categories={WorkloadCategory.INSTRUCTION: 50, WorkloadCategory.SUMMATIVE_ASSESSMENT: None},
    )
    assert missing.budget is None
    assert missing.findings[0]["code"] == "workload_time_allocation_missing"


def test_declared_budget_is_not_redefined_and_category_total_prevents_double_counting() -> None:
    budget = calculate_workload_budget(
        declared_total_minutes=60,
        categories={WorkloadCategory.INSTRUCTION: 10, WorkloadCategory.GUIDED_PRACTICE: 10},
    )
    assert budget.declared_total_minutes == 60
    assert budget.planned_total_minutes == 20
    assert budget.unallocated_minutes == 40


def test_quality_gate_keeps_workload_finding_separate_from_existing_findings() -> None:
    from app.instructional_design.fixtures import research_fixture_bundles

    bundle = research_fixture_bundles()["python_data_processing"]
    workload = validate_workload_allocations(
        declared_total_minutes=60,
        categories={WorkloadCategory.INSTRUCTION: 90},
    )
    report = evaluate_instructional_design(
        brief=bundle.brief,
        objectives=bundle.objectives,
        assessments=bundle.assessments,
        prerequisites=bundle.prerequisites,
        course_outline=bundle.course_outline,
        lessons=bundle.lessons,
        workload_validation=workload,
    )
    codes = {finding.code for finding in report.findings}
    assert "workload_time_budget_exceeded" in codes


def test_workload_prompt_is_new_patch_and_historical_prompt_is_unchanged() -> None:
    prompts = instructional_design_experiment_prompt_templates(
        version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V032
    )
    current = {p.template_id: p for p in prompts}
    historical = {p.template_id: p for p in instructional_design_experiment_prompt_templates(
        version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031
    )}
    assert "declared total minutes" in current[COURSE_PLANNING_SCHEMA_ID].system_instruction
    assert "declared total minutes" not in historical[COURSE_PLANNING_SCHEMA_ID].system_instruction
    assert "missing allocation" in current[LESSON_PLANNING_SCHEMA_ID].system_instruction
