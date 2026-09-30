import pytest

from app.extraction.ext_03a9_flash_model_comparison import (
    FLASH_MODELS,
    build_comparison_manifest,
    choose_flash_candidate,
    compare_model_metrics,
    model_endpoint,
    validate_comparison_inputs,
)


def test_comparison_uses_exact_three_flash_models() -> None:
    assert FLASH_MODELS == (
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
    )


def test_manifest_can_describe_a_separate_explicit_model_run() -> None:
    manifest = build_comparison_manifest(
        fixtures=[{"fixture_id": "sales", "sha256": "a" * 64}],
        stage1_fact_ids={"sales": "facts-sales-1"},
        taxonomy_id="professional_capability_core",
        taxonomy_version="0.1",
        criteria_id="strict-demonstrated-evidence",
        criteria_version="0.1",
        prompt_id="cv_capability_selection_criteria",
        prompt_version="1.0",
        expectation_ref="expectations.json",
        models=("gemini-3.1-pro-preview",),
    )
    assert manifest["models"] == ["gemini-3.1-pro-preview"]


def test_gemini_endpoint_changes_model_path_for_comparison() -> None:
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
    assert model_endpoint(endpoint, "gemini-3.7-flash") == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash:generateContent"
    proxy = "http://localhost:4000/api/v1/generate"
    assert model_endpoint(proxy, "gemini-3.7-flash") == proxy


def test_manifest_locks_facts_taxonomy_criteria_and_expectations() -> None:
    manifest = build_comparison_manifest(
        fixtures=[{"fixture_id": "sales", "sha256": "a" * 64}],
        stage1_fact_ids={"sales": "facts-sales-1"},
        taxonomy_id="professional_capability_core",
        taxonomy_version="0.1",
        criteria_id="strict-demonstrated-evidence",
        criteria_version="0.1",
        prompt_id="cv_capability_selection_criteria",
        prompt_version="1.0",
        expectation_ref="expectations.json",
    )
    assert manifest["models"] == list(FLASH_MODELS)
    assert manifest["thinking"] == "medium"
    assert manifest["stage1_fact_ids"] == {"sales": "facts-sales-1"}
    assert manifest["taxonomy"] == {
        "id": "professional_capability_core",
        "version": "0.1",
    }


def test_comparison_rejects_mismatched_fixture_expectation_identity() -> None:
    with pytest.raises(ValueError, match="expectation_fixture_mismatch"):
        validate_comparison_inputs(
            fixtures=[{"fixture_id": "sales", "sha256": "a" * 64}],
            expectations=[{"fixture_id": "sales", "sha256": "b" * 64}],
            taxonomy_id="professional_capability_core",
            taxonomy_version="0.1",
            expected_taxonomy_id="professional_capability_core",
            expected_taxonomy_version="0.1",
            criteria_id="strict-demonstrated-evidence",
            expected_criteria_id="strict-demonstrated-evidence",
            criteria_version="0.1",
            expected_criteria_version="0.1",
        )


def test_model_comparison_preserves_statement_refs_and_metrics() -> None:
    result = compare_model_metrics(
        model="gemini-3.6-flash",
        fixture_id="sales",
        selected_ids=["project_management", "product_management"],
        supported_ids=["project_management"],
        expected_ids=["project_management", "team_leadership"],
        statement_refs={
            "project_management": ["stmt-1"],
            "product_management": ["stmt-2"],
        },
    )
    assert result["supporting_statement_ids"] == {
        "project_management": ["stmt-1"],
        "product_management": ["stmt-2"],
    }
    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["grounding"] == 1.0


def test_winner_requires_precision_and_recall_before_tie_breaking() -> None:
    records = [
        {"model": "gemini-3.6-flash", "mean_precision": 0.95, "mean_recall": 0.69, "mean_f1": 0.8, "sales_precision": 0.8, "mean_latency_ms": 100},
        {"model": "gemini-3.7-flash", "mean_precision": 0.91, "mean_recall": 0.71, "mean_f1": 0.8, "sales_precision": 0.3, "mean_latency_ms": 200},
    ]
    assert choose_flash_candidate(records) == "gemini-3.7-flash"
