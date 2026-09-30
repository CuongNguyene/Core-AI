from app.extraction.benchmark_labels import (
    BenchmarkClaimLabel,
    BenchmarkJob,
    build_review_labels,
    compute_domain_metrics,
)


def test_build_labels_is_deterministic_and_leaves_review_flags_unset() -> None:
    manifest = [
        {
            "source_file": "hr.pdf",
            "source_sha256": "abc",
            "domain": "HR",
            "status": "succeeded",
            "profile_id": "profile-1",
        }
    ]
    profiles = [
        {
            "id": "profile-1",
            "output": {
                "skills": [
                    {
                        "value": "Payroll",
                        "evidence_type": "explicit_skill",
                        "evidence_status": "supported",
                        "source_locator": {"start_offset": 1, "end_offset": 8},
                    }
                ]
            },
        }
    ]
    _, labels = build_review_labels(manifest, profiles)
    assert len(labels) == 1
    assert labels[0].locator_resolved is True
    assert labels[0].claim_correct is None
    assert labels[0].label_id == build_review_labels(manifest, profiles)[1][0].label_id


def test_metrics_are_null_until_reviewer_labels_are_supplied() -> None:
    jobs = [
        BenchmarkJob(domain="HR", status="succeeded"),
        BenchmarkJob(domain="HR", status="failed"),
    ]
    labels = [
        BenchmarkClaimLabel(
            label_id="claim-1",
            domain="HR",
            source_file="hr.pdf",
            profile_id="profile-1",
            bucket="experience",
            claim_index=0,
            observed_value="Payroll",
            observed_evidence_type="work_experience",
            observed_status="supported",
            locator_resolved=True,
        )
    ]

    metrics = compute_domain_metrics(jobs, labels)["HR"]

    assert metrics.job_success_rate == 0.5
    assert metrics.locator_resolution_rate == 1.0
    assert metrics.evidence_type_accuracy is None
    assert metrics.activity_capture_rate is None
    assert metrics.employment_grouping_accuracy is None
    assert metrics.duplicate_rate is None
    assert metrics.unsupported_claim_rate is None


def test_metrics_use_only_explicit_reviewer_labels() -> None:
    jobs = [BenchmarkJob(domain="Legal", status="succeeded")]
    labels = [
        BenchmarkClaimLabel(
            label_id="claim-1",
            domain="Legal",
            source_file="legal.pdf",
            profile_id="profile-1",
            bucket="experience",
            claim_index=0,
            observed_value="Drafted contracts",
            observed_evidence_type="explicit_skill",
            observed_status="supported",
            locator_resolved=True,
            claim_correct=True,
            evidence_type_correct=False,
            duplicate=False,
            misclassified_context=True,
            unsupported=False,
        ),
        BenchmarkClaimLabel(
            label_id="missing-1",
            domain="Legal",
            source_file="legal.pdf",
            profile_id="profile-1",
            bucket="experience",
            claim_index=1,
            expected_value="Reviewed commercial contracts",
            expected_context="employment",
            missing=True,
            locator_resolved=True,
        ),
    ]

    metrics = compute_domain_metrics(jobs, labels)["Legal"]

    assert metrics.evidence_type_accuracy == 0.0
    assert metrics.activity_capture_rate == 0.0
    assert metrics.employment_grouping_accuracy == 0.0
    assert metrics.duplicate_rate == 0.0
    assert metrics.unsupported_claim_rate == 0.0
