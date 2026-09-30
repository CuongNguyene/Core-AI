import json
from datetime import UTC, datetime
from pathlib import Path

from app.instructional_design.experiment import (
    ExperimentCondition,
    ExperimentConfig,
    ExperimentRun,
    ExperimentRunResult,
    ExperimentRunStatus,
    GenerationConfig,
    PromptSchemaVersion,
)
from app.instructional_design.fixtures import research_fixture_bundles


def _result(fixture_id: str, condition: ExperimentCondition) -> ExperimentRunResult:
    bundle = research_fixture_bundles()[fixture_id]
    config = ExperimentConfig(
        experiment_id="id-02",
        experiment_version="0.1",
        fixture_ids=[fixture_id],
        model_provider="test",
        model_name="test",
        generation_config=GenerationConfig(),
        policy_id="pai_instructional_design",
        policy_version="0.1",
        dependency_normalizer_version="id02d.2@0.1",
        prompt_schema_versions=[
            PromptSchemaVersion(
                prompt_id="test-prompt",
                prompt_version="1",
                schema_id="test-schema",
                schema_version="1",
            )
        ],
    )
    return ExperimentRunResult(
        run=ExperimentRun.from_config(
            run_id=f"id-02:{fixture_id}:{condition.value}:1",
            config=config,
            fixture_id=fixture_id,
            condition=condition,
            run_number=1,
            started_at=datetime(2026, 8, 12, tzinfo=UTC),
        ),
        status=ExperimentRunStatus.COMPLETED,
        snapshot=bundle.snapshot,
        completed_at=datetime(2026, 8, 12, tzinfo=UTC),
    )


def test_blinded_review_bundle_writes_six_condition_free_packets_and_private_mapping(
    tmp_path: Path,
) -> None:
    from app.instructional_design.blinded_review_cli import (
        build_blinded_review_bundle,
        write_blinded_review_bundle,
    )

    results = [
        _result(fixture_id, condition)
        for fixture_id in research_fixture_bundles()
        for condition in (ExperimentCondition.ONE_SHOT, ExperimentCondition.STRUCTURED)
    ]

    bundle = build_blinded_review_bundle(results)
    write_blinded_review_bundle(bundle, tmp_path)

    assert len(bundle.packets) == 6
    assert len(bundle.private_mapping) == 6
    assert {item.review_id for item in bundle.packets} == {
        item.review_id for item in bundle.private_mapping
    }
    assert len(list((tmp_path / "reviewer-packets").glob("*.json"))) == 6
    assert (tmp_path / "researcher-private-review-mapping.json").is_file()
    packet_text = "\n".join(
        path.read_text() for path in (tmp_path / "reviewer-packets").glob("*.json")
    )
    assert "one_shot" not in packet_text
    assert "structured" not in packet_text
    assert "generation_provenance" not in packet_text
    private_mapping = json.loads((tmp_path / "researcher-private-review-mapping.json").read_text())
    assert all("run_id" in item and "condition" in item for item in private_mapping["private_mapping"])


def test_cli_loader_accepts_strict_json_serialized_experiment_results(tmp_path: Path) -> None:
    from app.instructional_design.blinded_review_cli import load_experiment_results

    serialized_result = _result("model_monitoring", ExperimentCondition.ONE_SHOT).model_dump(mode="json")
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps({"results": [serialized_result]}), encoding="utf-8")

    results = load_experiment_results(results_path)

    assert results[0].run.run_id == "id-02:model_monitoring:one_shot:1"


def test_blinded_review_loader_accepts_strict_json_wire_artifacts(tmp_path: Path) -> None:
    from app.instructional_design.blinded_review_cli import load_experiment_results

    result = _result("model_monitoring", ExperimentCondition.ONE_SHOT)
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"results": [result.model_dump(mode="json")]}), encoding="utf-8")

    loaded = load_experiment_results(path)

    assert loaded == [result]
