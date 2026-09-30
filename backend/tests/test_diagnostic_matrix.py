from app.extraction.diagnostic_matrix import (
    MatrixRun,
    capability_coverage,
    duplicate_count,
    education_recall,
    recommend,
)


def test_evaluator_uses_bounded_capability_aliases_and_detects_duplicates() -> None:
    coverage = capability_coverage(["Omni Channel Management", "Project Delivery Management"])

    assert coverage["Omnichannel Commerce"] == "FOUND"
    assert coverage["Project Management"] == "FOUND"
    assert duplicate_count(["Project Management", "project management", "Team Leadership"]) == 1
    assert education_recall(1) == "1/2"


def test_failed_run_is_preserved_and_recommends_runtime_fix() -> None:
    run = MatrixRun(
        run_id="a",
        input_mode="native_pdf",
        thinking="high",
        provider="gemini",
        model="gemini-3.5-flash-lite",
        prompt_id="cv_full_extraction",
        prompt_version="2.0",
        success=False,
        failure_stage="structured_output",
        failure_code="TRUNCATED_OUTPUT",
        latency_ms=10,
        token_usage={"total_tokens": 10},
        counts={},
        quality={},
    )

    decision = recommend([run])

    assert run.failure_code == "TRUNCATED_OUTPUT"
    assert decision["primary_blocker"] == "TECHNICAL_RUNTIME"
