from app.instructional_design.contracts import (
    ASSESSMENT_DESIGN_SCHEMA_ID,
    COURSE_PLANNING_SCHEMA_ID,
    INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03,
    LESSON_PLANNING_SCHEMA_ID,
    OBJECTIVE_DESIGN_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_ID,
    ONE_SHOT_BASELINE_SCHEMA_VERSION,
    PREREQUISITE_PROPOSAL_SCHEMA_ID,
)
from app.instructional_design.experiment import ExperimentCondition
from app.instructional_design.smoke_3_cli import build_smoke_3_config


def test_smoke_3_uses_same_baseline_and_v03_structured_condition() -> None:
    config = build_smoke_3_config(
        model_provider="vilao",
        model_name="claude-sonnet-5",
        model_revision=None,
        policy_id="pai_instructional_design",
        policy_version="0.1",
    )

    assert config.conditions == (ExperimentCondition.ONE_SHOT, ExperimentCondition.STRUCTURED_V03)
    assert config.runs_per_fixture_per_condition == 1
    assert config.fixture_ids == [
        "model_monitoring",
        "python_data_processing",
        "technical_communication",
    ]
    versions = {item.prompt_id: item.prompt_version for item in config.prompt_schema_versions}
    assert versions[ONE_SHOT_BASELINE_SCHEMA_ID] == ONE_SHOT_BASELINE_SCHEMA_VERSION
    assert all(
        versions[item] == INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03
        for item in (
            OBJECTIVE_DESIGN_SCHEMA_ID,
            ASSESSMENT_DESIGN_SCHEMA_ID,
            PREREQUISITE_PROPOSAL_SCHEMA_ID,
            COURSE_PLANNING_SCHEMA_ID,
            LESSON_PLANNING_SCHEMA_ID,
        )
    )
