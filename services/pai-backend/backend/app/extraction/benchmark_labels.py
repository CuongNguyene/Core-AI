"""Human-review labels and domain metrics for extraction benchmarks.

Mechanical fields (job status and locator resolution) are populated by the
runner.  Correctness fields deliberately remain nullable until a reviewer
labels the claim; extraction output must never be treated as its own oracle.
"""

import hashlib
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkJob(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    domain: str = Field(min_length=1)
    status: str = Field(min_length=1)


class BenchmarkClaimLabel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    label_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    profile_id: str | None = None
    bucket: str = Field(min_length=1)
    claim_index: int = Field(ge=0)
    observed_value: str | None = None
    observed_evidence_type: str | None = None
    observed_status: str | None = None
    expected_value: str | None = None
    expected_context: str | None = None
    locator_resolved: bool = False
    claim_correct: bool | None = None
    evidence_type_correct: bool | None = None
    duplicate: bool | None = None
    misclassified_context: bool | None = None
    unsupported: bool | None = None
    missing: bool | None = None
    reviewer_note: str | None = None


class DomainBenchmarkMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    job_success_rate: float = Field(ge=0, le=1)
    locator_resolution_rate: float | None = Field(default=None, ge=0, le=1)
    supported_grounding_rate: float | None = Field(default=None, ge=0, le=1)
    evidence_type_accuracy: float | None = Field(default=None, ge=0, le=1)
    activity_capture_rate: float | None = Field(default=None, ge=0, le=1)
    employment_grouping_accuracy: float | None = Field(default=None, ge=0, le=1)
    duplicate_rate: float | None = Field(default=None, ge=0, le=1)
    unsupported_claim_rate: float | None = Field(default=None, ge=0, le=1)
    reviewed_claim_count: int = Field(ge=0)
    observed_claim_count: int = Field(ge=0)


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def compute_domain_metrics(
    jobs: Sequence[BenchmarkJob], labels: Sequence[BenchmarkClaimLabel]
) -> dict[str, DomainBenchmarkMetrics]:
    """Compute metrics without filling any reviewer labels implicitly."""

    domains = {job.domain for job in jobs} | {label.domain for label in labels}
    result: dict[str, DomainBenchmarkMetrics] = {}
    for domain in sorted(domains):
        domain_jobs = [job for job in jobs if job.domain == domain]
        domain_labels = [label for label in labels if label.domain == domain]
        observed = [label for label in domain_labels if label.missing is not True]
        supported = [label for label in observed if label.observed_status == "supported"]
        reviewed_type = [label for label in observed if label.evidence_type_correct is not None]
        expected_activity = [label for label in domain_labels if label.expected_context]
        employment = [
            label for label in expected_activity if label.expected_context == "employment"
        ]
        reviewed_duplicate = [label for label in observed if label.duplicate is not None]
        reviewed_unsupported = [label for label in observed if label.unsupported is not None]
        result[domain] = DomainBenchmarkMetrics(
            job_success_rate=_ratio(
                sum(job.status == "succeeded" for job in domain_jobs), len(domain_jobs)
            )
            or 0.0,
            locator_resolution_rate=_ratio(
                sum(label.locator_resolved for label in observed), len(observed)
            ),
            supported_grounding_rate=_ratio(
                sum(label.locator_resolved for label in supported), len(supported)
            ),
            evidence_type_accuracy=_ratio(
                sum(label.evidence_type_correct is True for label in reviewed_type),
                len(reviewed_type),
            ),
            activity_capture_rate=_ratio(
                sum(label.missing is not True for label in expected_activity),
                len(expected_activity),
            ),
            employment_grouping_accuracy=_ratio(
                sum(
                    label.missing is not True and label.misclassified_context is False
                    for label in employment
                ),
                len(employment),
            ),
            duplicate_rate=_ratio(
                sum(label.duplicate is True for label in reviewed_duplicate),
                len(reviewed_duplicate),
            ),
            unsupported_claim_rate=_ratio(
                sum(label.unsupported is True for label in reviewed_unsupported),
                len(reviewed_unsupported),
            ),
            reviewed_claim_count=sum(
                any(
                    value is not None
                    for value in (
                        label.claim_correct,
                        label.evidence_type_correct,
                        label.duplicate,
                        label.misclassified_context,
                        label.unsupported,
                        label.missing,
                    )
                )
                for label in domain_labels
            ),
            observed_claim_count=len(observed),
        )
    return result


def build_review_labels(
    manifest: Sequence[dict[str, object]], profiles: Sequence[dict[str, object]]
) -> tuple[list[BenchmarkJob], list[BenchmarkClaimLabel]]:
    """Build a deterministic, reviewer-pending label set from one run."""

    by_profile = {
        str(profile["id"]): profile
        for profile in profiles
        if profile.get("id") is not None
    }
    jobs: list[BenchmarkJob] = []
    labels: list[BenchmarkClaimLabel] = []
    for entry in manifest:
        domain = str(entry["domain"])
        source_file = str(entry["source_file"])
        status = str(entry["status"])
        jobs.append(BenchmarkJob(domain=domain, status=status))
        profile_id = entry.get("profile_id")
        profile = by_profile.get(str(profile_id)) if profile_id is not None else None
        if profile is None:
            continue
        output = profile.get("output")
        if not isinstance(output, dict):
            continue
        for bucket in ("skills", "experience", "education"):
            claims = output.get(bucket, [])
            if not isinstance(claims, list):
                continue
            for claim_index, claim in enumerate(claims):
                if not isinstance(claim, dict):
                    continue
                key = f"{entry.get('source_sha256', '')}|{profile_id}|{bucket}|{claim_index}"
                label_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
                locator = claim.get("source_locator")
                labels.append(
                    BenchmarkClaimLabel(
                        label_id=label_id,
                        domain=domain,
                        source_file=source_file,
                        profile_id=str(profile_id),
                        bucket=bucket,
                        claim_index=claim_index,
                        observed_value=claim.get("value"),
                        observed_evidence_type=claim.get("evidence_type"),
                        observed_status=claim.get("evidence_status"),
                        locator_resolved=isinstance(locator, dict),
                    )
                )
    return jobs, labels
