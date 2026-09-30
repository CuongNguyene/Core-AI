from pathlib import Path

from app.instructional_design.smoke_3_merge_recovery_cli import merge_recovery


def test_merge_recovery_replaces_only_matching_fixture_condition() -> None:
    root = Path("test/results/instructional-design-smoke-3-live-network-3")
    output = root / "_test-merged-results.json"
    execution = merge_recovery(
        parent_results=root / "results.json",
        recovery_results=root / "recovery-run-1/recovery-results.json",
        output=output,
    )
    try:
        assert len(execution.results) == 6
        target = [
            item
            for item in execution.results
            if item.run.fixture_id == "technical_communication"
            and item.run.condition.value == "structured_v0.3"
        ]
        assert len(target) == 1
        assert target[0].status.value == "completed"
    finally:
        output.unlink(missing_ok=True)
