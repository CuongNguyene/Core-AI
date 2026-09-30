"""Human-owned semantic benchmark helpers for the frozen CV extraction contract."""

import hashlib
import re
import unicodedata
from collections.abc import Sequence
from enum import StrEnum
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from app.extraction.benchmark_labels import BenchmarkClaimLabel


class DuplicateAliasLabel(StrEnum):
    NONE = "NONE"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    SEMANTIC_DUPLICATE = "SEMANTIC_DUPLICATE"
    ALIAS = "ALIAS"
    SAME_EVIDENCE_DIFFERENT_CLAIM = "SAME_EVIDENCE_DIFFERENT_CLAIM"


class SuspectedLayer(StrEnum):
    PROMPT_TYPING = "PROMPT_TYPING"
    SCHEMA_REPRESENTATION = "SCHEMA_REPRESENTATION"
    MERGE_DEDUP = "MERGE_DEDUP"
    EXTRACTION_RECALL = "EXTRACTION_RECALL"
    GROUNDING = "GROUNDING"
    PARSER_SOURCE_STRUCTURE = "PARSER_SOURCE_STRUCTURE"
    UNKNOWN = "UNKNOWN"


class CaptureStatus(StrEnum):
    CAPTURED_CORRECTLY = "CAPTURED_CORRECTLY"
    CAPTURED_PARTIALLY = "CAPTURED_PARTIALLY"
    CAPTURED_WRONG_CONTEXT = "CAPTURED_WRONG_CONTEXT"
    MISSED = "MISSED"
    UNRESOLVED = "UNRESOLVED"


class SemanticBenchmarkLabel(BenchmarkClaimLabel):
    """Additive semantic fields; all reviewer decisions remain nullable."""

    model_config = ConfigDict(extra="forbid", strict=False)

    representation_correct: bool | None = None
    duplicate_or_alias: DuplicateAliasLabel | None = None
    suspected_layer: SuspectedLayer | None = None


class ExpectedRecordTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    expected_record_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    expected_value: str | None = None
    expected_kind: str | None = None
    expected_context: str | None = None
    expected_evidence_type: str | None = None
    importance: str = "material"
    source_locator: dict[str, object] | None = None
    matched_claim_ids: list[str] = Field(default_factory=list)
    capture_status: CaptureStatus | None = None
    reviewer_note: str | None = None


class SemanticDomainMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    job_success_rate: float = Field(ge=0, le=1)
    locator_resolution_rate: float | None = Field(default=None, ge=0, le=1)
    supported_grounding_rate: float | None = Field(default=None, ge=0, le=1)
    claim_correctness_rate: float | None = Field(default=None, ge=0, le=1)
    evidence_type_accuracy: float | None = Field(default=None, ge=0, le=1)
    representation_accuracy: float | None = Field(default=None, ge=0, le=1)
    duplicate_or_alias_rate: float | None = Field(default=None, ge=0, le=1)
    unsupported_claim_rate: float | None = Field(default=None, ge=0, le=1)
    material_evidence_capture_rate: float | None = Field(default=None, ge=0, le=1)
    paraphrased_source_rate: float | None = Field(default=None, ge=0, le=1)
    unsupported_source_rate: float | None = Field(default=None, ge=0, le=1)
    source_relation_unclear_rate: float | None = Field(default=None, ge=0, le=1)
    format_only_rate: float | None = Field(default=None, ge=0, le=1)
    ambiguous_source_rate: float | None = Field(default=None, ge=0, le=1)
    reviewed_claim_count: int = Field(ge=0)
    reviewed_expected_record_count: int = Field(ge=0)


_DOMAIN_NAMES = ("HR", "IT", "Accounting", "Legal", "Finance", "Secretary", "Construction")
_PILOT_DOMAINS = ("Legal", "Accounting", "IT", "Finance", "Construction")


def canonical_domain(value: str) -> str:
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    if normalized.startswith("hr"):
        return "HR"
    if normalized.startswith("it"):
        return "IT"
    if "ke toan" in normalized or "account" in normalized:
        return "Accounting"
    if "legal" in normalized or "phap ly" in normalized:
        return "Legal"
    if "tai chinh" in normalized or "finance" in normalized:
        return "Finance"
    if "thu ky" in normalized or "secret" in normalized:
        return "Secretary"
    if "xay dung" in normalized or "construction" in normalized:
        return "Construction"
    return value


def _ratio(numerator: float, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _label_id(source_sha256: object, profile_id: object, bucket: str, index: int) -> str:
    key = f"{source_sha256}|{profile_id}|{bucket}|{index}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _sampling_reasons(claim: dict[str, object], bucket: str, siblings: list[dict[str, object]]) -> list[str]:
    reasons: list[str] = []
    evidence_type = str(claim.get("evidence_type", "unknown"))
    if evidence_type in {"explicit_skill", "work_experience", "education", "certification", "project_usage"}:
        reasons.append(f"evidence_type:{evidence_type}")
    if bucket == "experience" or evidence_type == "work_experience":
        reasons.append("work_activity_candidate")
    if evidence_type == "certification":
        reasons.append("credential_candidate")
    if claim.get("evidence_status") != "supported":
        reasons.append("insufficient_or_unresolved")
    locator = claim.get("source_locator")
    if isinstance(locator, dict):
        same_source = sum(item.get("source_locator") == locator for item in siblings)
        if same_source > 1:
            reasons.append("same_source_multi_claim")
    value = str(claim.get("value") or "")
    if re.search(r"\b(19|20)\d{2}\b|\b\d{1,2}/\d{4}\b|\bto\b|\bnow\b|\bnay\b", value.casefold()):
        reasons.append("duration_or_date_candidate")
    return reasons or ["stratified_fill"]


def build_pilot_selection(
    manifest: Sequence[dict[str, object]], profiles: Sequence[dict[str, object]], *, max_claims: int = 25
) -> dict[str, object]:
    by_profile = {str(profile.get("id")): profile for profile in profiles if profile.get("id") is not None}
    candidates: dict[str, list[dict[str, object]]] = {}
    for entry in manifest:
        if entry.get("status") != "succeeded" or entry.get("profile_id") is None:
            continue
        report_domain = canonical_domain(str(entry.get("domain", "")))
        if report_domain not in _DOMAIN_NAMES:
            continue
        profile = by_profile.get(str(entry["profile_id"]))
        output = profile.get("output") if profile else None
        if not isinstance(output, dict):
            continue
        candidates.setdefault(report_domain, []).append({"entry": entry, "output": output})

    selected_profiles: list[dict[str, object]] = []
    for report_domain in _PILOT_DOMAINS:
        if report_domain not in candidates:
            continue
        selected = min(
            candidates[report_domain],
            key=lambda item: (
                str(cast(dict[str, object], item["entry"]).get("source_sha256", "")),
                str(cast(dict[str, object], item["entry"]).get("profile_id")),
            ),
        )
        entry = cast(dict[str, object], selected["entry"])
        output = cast(dict[str, object], selected["output"])
        all_claims: list[dict[str, object]] = []
        for bucket in ("skills", "experience", "education"):
            claims = output.get(bucket, [])
            if not isinstance(claims, list):
                continue
            for claim_index, claim in enumerate(claims):
                if isinstance(claim, dict):
                    all_claims.append({"bucket": bucket, "claim_index": claim_index, "claim": claim})
        reasons_by_index = {
            index: _sampling_reasons(
                cast(dict[str, object], item["claim"]),
                str(item["bucket"]),
                [cast(dict[str, object], other["claim"]) for other in all_claims],
            )
            for index, item in enumerate(all_claims)
        }
        selected_indices: list[int] = []
        seen_types: set[str] = set()
        for index, item in enumerate(all_claims):
            evidence_type = str(cast(dict[str, object], item["claim"]).get("evidence_type", "unknown"))
            if evidence_type not in seen_types:
                selected_indices.append(index)
                seen_types.add(evidence_type)
        suspicious = sorted(
            (index for index, reasons in reasons_by_index.items() if len(reasons) > 1),
            key=lambda index: (-(len(reasons_by_index[index])), index),
        )
        selected_indices.extend(index for index in suspicious if index not in selected_indices)
        selected_indices.extend(index for index in range(len(all_claims)) if index not in selected_indices)
        selected_indices = sorted(selected_indices[:max_claims])
        claim_rows = []
        for index in selected_indices:
            item = all_claims[index]
            claim = cast(dict[str, object], item["claim"])
            claim_index = cast(int, item["claim_index"])
            claim_rows.append(
                {
                    "label_id": _label_id(entry.get("source_sha256", ""), entry.get("profile_id", ""), str(item["bucket"]), claim_index),
                    "domain": report_domain,
                    "profile_id": entry.get("profile_id"),
                    "bucket": item["bucket"],
                    "claim_index": claim_index,
                    "sampling_reason": reasons_by_index[index],
                    "observed_value": claim.get("value"),
                    "observed_evidence_type": claim.get("evidence_type"),
                    "observed_status": claim.get("evidence_status"),
                    "locator_resolved": isinstance(claim.get("source_locator"), dict),
                }
            )
        selected_profiles.append(
            {
                "profile_id": entry.get("profile_id"),
                "domain": entry.get("domain"),
                "report_domain": report_domain,
                "source_file": entry.get("source_file"),
                "source_sha256": entry.get("source_sha256"),
                "claims": claim_rows,
            }
        )
    return {
        "schema_version": "semantic_benchmark_pilot@1",
        "selection_version": "stratified_deterministic_v1",
        "review_state": "pending_reviewer",
        "selected_profiles": selected_profiles,
    }


def build_expected_record_templates(
    manifest: Sequence[dict[str, object]],
) -> list[ExpectedRecordTemplate]:
    by_domain: dict[str, dict[str, object]] = {}
    for entry in manifest:
        if entry.get("status") != "succeeded" or entry.get("profile_id") is None:
            continue
        domain = canonical_domain(str(entry.get("domain", "")))
        current = by_domain.get(domain)
        candidate_key = (str(entry.get("source_sha256", "")), str(entry.get("profile_id")))
        current_key = (
            (str(current.get("source_sha256", "")), str(current.get("profile_id", "")))
            if current
            else ("~", "~")
        )
        if current is None or candidate_key < current_key:
            by_domain[domain] = dict(entry)
    templates: list[ExpectedRecordTemplate] = []
    for domain in _DOMAIN_NAMES:
        expected_entry = by_domain.get(domain)
        if expected_entry is None:
            continue
        record_id = hashlib.sha256(
            f"expected|{domain}|{expected_entry['profile_id']}".encode()
        ).hexdigest()[:16]
        templates.append(
            ExpectedRecordTemplate(
                expected_record_id=record_id,
                profile_id=str(expected_entry["profile_id"]),
                domain=domain,
            )
        )
    return templates


def _reviewed(value: object) -> bool:
    return value is not None


def _grounding_rate(items: list[dict[str, object]], label: str, domain: str) -> float | None:
    rows = [item for item in items if canonical_domain(str(item.get("domain", ""))) == domain and item.get("review_label") is not None]
    return _ratio(sum(item.get("review_label") == label for item in rows), len(rows))


def compute_semantic_metrics(
    manifest: Sequence[dict[str, object]],
    labels: Sequence[SemanticBenchmarkLabel],
    expected_records: Sequence[ExpectedRecordTemplate],
    grounding_items: Sequence[dict[str, object]] = (),
) -> dict[str, SemanticDomainMetrics]:
    domains = {canonical_domain(str(entry.get("domain", ""))) for entry in manifest}
    result: dict[str, SemanticDomainMetrics] = {}
    for domain in sorted(domains):
        jobs = [entry for entry in manifest if canonical_domain(str(entry.get("domain", ""))) == domain]
        domain_labels = [label for label in labels if canonical_domain(label.domain) == domain]
        observed = [label for label in domain_labels if label.missing is not True]
        claim_review = [label for label in domain_labels if _reviewed(label.claim_correct)]
        type_review = [label for label in domain_labels if _reviewed(label.evidence_type_correct)]
        representation_review = [label for label in domain_labels if _reviewed(label.representation_correct)]
        duplicate_review = [label for label in domain_labels if label.duplicate_or_alias is not None or label.duplicate is not None]
        unsupported_review = [label for label in domain_labels if _reviewed(label.unsupported)]
        expected = [record for record in expected_records if canonical_domain(record.domain) == domain and record.capture_status is not None]
        result[domain] = SemanticDomainMetrics(
            job_success_rate=_ratio(sum(entry.get("status") == "succeeded" for entry in jobs), len(jobs)) or 0.0,
            locator_resolution_rate=_ratio(sum(label.locator_resolved for label in observed), len(observed)),
            supported_grounding_rate=_ratio(sum(label.locator_resolved for label in observed if label.observed_status == "supported"), sum(label.observed_status == "supported" for label in observed)),
            claim_correctness_rate=_ratio(sum(label.claim_correct is True for label in claim_review), len(claim_review)),
            evidence_type_accuracy=_ratio(sum(label.evidence_type_correct is True for label in type_review), len(type_review)),
            representation_accuracy=_ratio(sum(label.representation_correct is True for label in representation_review), len(representation_review)),
            duplicate_or_alias_rate=_ratio(sum((label.duplicate_or_alias not in {None, DuplicateAliasLabel.NONE}) or label.duplicate is True for label in duplicate_review), len(duplicate_review)),
            unsupported_claim_rate=_ratio(sum(label.unsupported is True for label in unsupported_review), len(unsupported_review)),
            material_evidence_capture_rate=_ratio(sum(record.capture_status is CaptureStatus.CAPTURED_CORRECTLY for record in expected), len(expected)),
            paraphrased_source_rate=_grounding_rate(list(grounding_items), "G_PARAPHRASED_SOURCE", domain),
            unsupported_source_rate=_grounding_rate(list(grounding_items), "H_UNSUPPORTED_SOURCE", domain),
            source_relation_unclear_rate=_grounding_rate(list(grounding_items), "SOURCE_RELATION_UNCLEAR", domain),
            format_only_rate=_grounding_rate(list(grounding_items), "FORMAT_ONLY", domain),
            ambiguous_source_rate=_grounding_rate(list(grounding_items), "AMBIGUOUS_SOURCE", domain),
            reviewed_claim_count=len({label.label_id for label in domain_labels if any((_reviewed(label.claim_correct), _reviewed(label.evidence_type_correct), _reviewed(label.representation_correct), label.duplicate_or_alias is not None, _reviewed(label.unsupported))) }),
            reviewed_expected_record_count=len(expected),
        )
    return result


def generate_decision_report(
    manifest: Sequence[dict[str, object]],
    labels: Sequence[SemanticBenchmarkLabel],
    expected_records: Sequence[ExpectedRecordTemplate],
    grounding_items: Sequence[dict[str, object]],
) -> str:
    metrics = compute_semantic_metrics(manifest, labels, expected_records, grounding_items)
    representation_errors = [
        label for label in labels
        if label.claim_correct is True
        and label.representation_correct is False
        and label.locator_resolved
        and label.unsupported is not True
    ]
    typing_errors = [
        label for label in labels
        if label.claim_correct is True
        and label.representation_correct is not False
        and label.evidence_type_correct is False
    ]
    dedup_errors = [
        label for label in labels
        if label.duplicate_or_alias in {
            DuplicateAliasLabel.EXACT_DUPLICATE,
            DuplicateAliasLabel.SEMANTIC_DUPLICATE,
            DuplicateAliasLabel.ALIAS,
        }
    ]
    missed = [record for record in expected_records if record.capture_status is CaptureStatus.MISSED]
    reviewed = sum(metric.reviewed_claim_count for metric in metrics.values())
    lines = [
        "# Semantic Extraction Benchmark Report",
        "",
        "## Scope",
        "",
        "- Contract: `CVExtractionOutput@1.1` (frozen)",
        "- Reliability, grounding, semantic correctness, representation, deduplication, and recall are reported separately.",
        "- No automatic production changes; all semantic labels remain human-owned.",
        "",
        "## Review state",
        "",
        f"- Status: {'pending human review' if reviewed == 0 else 'pilot review in progress'}.",
        f"- Reviewed claims: {reviewed}",
        f"- Expected-record templates: {len(expected_records)}; reviewed expected records: {sum(metric.reviewed_expected_record_count for metric in metrics.values())}",
        "",
        "## Reliability and grounding",
        "",
        "Reliability metrics remain job/locator metrics. Grounding queue labels are not provenance recovery and are not merged into semantic correctness.",
        "",
        "## Decision gates",
        "",
        f"- Representation/schema candidates: {len(representation_errors)} reviewed cases.",
        f"- Prompt/evidence typing candidates: {len(typing_errors)} reviewed cases.",
        f"- Merge/dedup candidates: {len(dedup_errors)} reviewed cases (aliases remain separate).",
        f"- Recall candidates: {len(missed)} manually marked MISSED expected records.",
        "- v2 gate: requires repeated grounded `claim_correct=true` and `representation_correct=false` across multiple profiles/domains; no schema v2 is designed here.",
        "",
        "## Per-domain metrics",
        "",
        "| Domain | Reviewed claims | Claim correctness | Evidence type | Representation | Duplicate/alias | Material capture |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for domain, metric in sorted(metrics.items()):
        def fmt(value: float | None) -> str:
            return "null" if value is None else f"{value:.3f}"
        lines.append(
            f"| {domain} | {metric.reviewed_claim_count} | {fmt(metric.claim_correctness_rate)} | {fmt(metric.evidence_type_accuracy)} | {fmt(metric.representation_accuracy)} | {fmt(metric.duplicate_or_alias_rate)} | {fmt(metric.material_evidence_capture_rate)} |"
        )
    lines.extend(
        [
            "",
            "## Remaining reviewer-owned work",
            "",
            "Review pilot claims, then populate the seven expected-record templates and unresolved grounding queue. Only after repeated patterns appear should a prompt/rule, merge/dedup, extraction-strategy, or schema-v2 follow-up be proposed.",
        ]
    )
    return "\n".join(lines) + "\n"
