from datetime import UTC, datetime

from app.instructional_design.experiment import ExperimentCondition
from app.instructional_design.smoke_3_cli import build_smoke_3_config
from app.instructional_design.smoke_3_recovery_cli import build_recovery_run


def test_recovery_target_is_only_missing_structured_fixture() -> None:
    config = build_smoke_3_config(
        model_provider="vilao",
        model_name="claude-sonnet-5",
        model_revision=None,
        policy_id="pai_instructional_design",
        policy_version="0.1",
    )

    run = build_recovery_run(config, started_at=datetime(2026, 8, 13, tzinfo=UTC))

    assert run.fixture_id == "technical_communication"
    assert run.condition is ExperimentCondition.STRUCTURED_V03
    assert run.run_number == 2
    assert run.run_id.endswith(":recovery-1")
