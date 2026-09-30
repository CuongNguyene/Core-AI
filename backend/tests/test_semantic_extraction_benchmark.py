from typing import cast

from app.extraction.benchmark_labels import BenchmarkClaimLabel
from app.extraction.semantic_benchmark import (
    DuplicateAliasLabel,
    ExpectedRecordTemplate,
    SemanticBenchmarkLabel,
    build_expected_record_templates,
    build_pilot_selection,
    compute_semantic_metrics,
    generate_decision_report,
)


def _manifest() -> list[dict[str, object]]:
    return [
        {
            "domain": "legal_test",
            "source_file": "legal.pdf",
            "source_sha256": "a" * 64,
            "status": "succeeded",
            "profile_id": "legal-profile",
        },
        {
            "domain": "kế toán_test",
            "source_file": "accounting.pdf",
            "source_sha256": "b" * 64,
            "status": "succeeded",
            "profile_id": "accounting-profile",
        },
        {
            "domain": "IT_test",
            "source_file": "it.pdf",
            "source_sha256": "c" * 64,
            "status": "succeeded",
            "profile_id": "it-profile",
        },
        {
            "domain": "tài chính test",
            "source_file": "finance.pdf",
            "source_sha256": "d" * 64,
            "status": "succeeded",
            "profile_id": "finance-profile",
        },
        {
            "domain": "xây dựng_test",
            "source_file": "construction.pdf",
            "source_sha256": "e" * 64,
            "status": "succeeded",
            "profile_id": "construction-profile",
        },
        {
            "domain": "HR_test",
            "source_file": "hr.pdf",
            "source_sha256": "f" * 64,
            "status": "succeeded",
            "profile_id": "hr-profile",
        },
        {
            "domain": "thư ký_test",
            "source_file": "secretary.pdf",
            "source_sha256": "0" * 64,
            "status": "succeeded",
            "profile_id": "secretary-profile",
        },
    ]


def _profiles() -> list[dict[str, object]]:
    profiles = []
    for entry in _manifest():
        claims = [
            {
                "value": f"Skill {index}",
                "evidence_type": "explicit_skill",
                "evidence_status": "supported",
                "source_locator": {"start_offset": index, "end_offset": index + 5},
                "source_excerpt": f"Skill {index}",
            }
            for index in range(30)
        ]
        profiles.append({"id": entry["profile_id"], "output": {"skills": claims}})
    return profiles


def test_semantic_reviewer_labels_are_nullable_and_duplicate_enum_is_explicit() -> None:
    label = SemanticBenchmarkLabel(
        label_id="label-1",
        domain="Legal",
        source_file="legal.pdf",
        profile_id="profile-1",
        bucket="skills",
        claim_index=0,
    )

    assert label.claim_correct is None
    assert label.representation_correct is None
    assert label.duplicate_or_alias is None
    assert DuplicateAliasLabel.ALIAS.value == "ALIAS"


def test_pilot_selection_is_reproducible_and_stratified() -> None:
    first = build_pilot_selection(_manifest(), _profiles())
    second = build_pilot_selection(_manifest(), _profiles())

    assert first == second
    selected_profiles = cast(list[dict[str, object]], first["selected_profiles"])
    assert {item["report_domain"] for item in selected_profiles} == {
        "Legal",
        "Accounting",
        "IT",
        "Finance",
        "Construction",
    }
    assert all(
        20 <= len(cast(list[dict[str, object]], item["claims"])) <= 30
        for item in selected_profiles
    )


def test_expected_record_templates_are_empty_and_one_per_domain() -> None:
    templates = build_expected_record_templates(_manifest())

    assert len(templates) == 7
    assert all(isinstance(template, ExpectedRecordTemplate) for template in templates)
    assert all(template.expected_value is None for template in templates)
    assert all(template.capture_status is None for template in templates)


def test_semantic_metrics_are_null_until_reviewed() -> None:
    metrics = compute_semantic_metrics(_manifest(), [], [])

    assert metrics["Legal"].claim_correctness_rate is None
    assert metrics["Legal"].representation_accuracy is None
    assert metrics["Legal"].material_evidence_capture_rate is None
    assert metrics["Legal"].reviewed_claim_count == 0
    assert metrics["Legal"].reviewed_expected_record_count == 0


def test_semantic_metrics_use_only_explicit_review_labels() -> None:
    labels = [
        SemanticBenchmarkLabel(
            label_id="label-1",
            domain="Legal",
            source_file="legal.pdf",
            profile_id="legal-profile",
            bucket="skills",
            claim_index=0,
            locator_resolved=True,
            claim_correct=True,
            evidence_type_correct=False,
            representation_correct=True,
            duplicate_or_alias=DuplicateAliasLabel.NONE,
            unsupported=False,
            suspected_layer="PROMPT_TYPING",
        ),
        SemanticBenchmarkLabel(
            label_id="label-2",
            domain="Legal",
            source_file="legal.pdf",
            profile_id="legal-profile",
            bucket="experience",
            claim_index=1,
            locator_resolved=True,
            claim_correct=True,
            evidence_type_correct=True,
            representation_correct=False,
            duplicate_or_alias=DuplicateAliasLabel.SEMANTIC_DUPLICATE,
            unsupported=False,
            suspected_layer="SCHEMA_REPRESENTATION",
        ),
    ]
    expected = [
        ExpectedRecordTemplate(
            expected_record_id="expected-1",
            profile_id="legal-profile",
            domain="Legal",
            capture_status="CAPTURED_CORRECTLY",
        ),
        ExpectedRecordTemplate(
            expected_record_id="expected-2",
            profile_id="legal-profile",
            domain="Legal",
            capture_status="MISSED",
        ),
    ]

    metrics = compute_semantic_metrics(_manifest(), labels, expected)

    assert metrics["Legal"].claim_correctness_rate == 1.0
    assert metrics["Legal"].evidence_type_accuracy == 0.5
    assert metrics["Legal"].representation_accuracy == 0.5
    assert metrics["Legal"].duplicate_or_alias_rate == 0.5
    assert metrics["Legal"].material_evidence_capture_rate == 0.5


def test_decision_report_is_pending_without_review_data_and_has_no_profile_mutation() -> None:
    report = generate_decision_report(_manifest(), [], [], [])

    assert "pending human review" in report.lower()
    assert "CVExtractionOutput@1.1" in report
    assert "No automatic production changes" in report
    assert "v2 gate" in report.lower()


def test_grounding_metrics_are_separate_from_semantic_metrics() -> None:
    grounding: list[dict[str, object]] = [
        {"domain": "Legal", "review_label": "G_PARAPHRASED_SOURCE"},
        {"domain": "Legal", "review_label": "AMBIGUOUS_SOURCE"},
    ]

    metrics = compute_semantic_metrics(_manifest(), [], [], grounding)

    assert metrics["Legal"].paraphrased_source_rate == 0.5
    assert metrics["Legal"].ambiguous_source_rate == 0.5
    assert metrics["Legal"].claim_correctness_rate is None


def test_historical_benchmark_claim_shape_remains_readable() -> None:
    legacy = BenchmarkClaimLabel(
        label_id="legacy-1",
        domain="HR",
        source_file="hr.pdf",
        profile_id="profile-1",
        bucket="skills",
        claim_index=0,
        observed_value="Payroll",
        observed_evidence_type="explicit_skill",
        observed_status="supported",
        locator_resolved=True,
        duplicate=False,
    )

    assert legacy.duplicate is False
    assert legacy.reviewer_note is None


def test_sampling_does_not_mutate_profile_artifact() -> None:
    profiles = _profiles()
    before = repr(profiles)

    build_pilot_selection(_manifest(), profiles)

    assert repr(profiles) == before
