import json
from uuid import uuid4

import pytest

from app.candidate_source.domain import (
    CandidateSourceError,
    OrganizationExternalMapping,
    canonical_fingerprint,
    project_candidate_profile,
    resolve_organization,
    snapshot_disposition,
    source_content_fingerprint,
)
from app.candidate_source.schemas import CandidateSourceEnvelope


def sample_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": "pai.candidate-source",
        "schema_version": "v1",
        "company": "CT Group",
        "department": "Engineering",
        "identity": {"source_system": "HRM", "employee_ref": "HR-EMP-00301"},
        "source_revision": 17,
        "source_snapshot": {"source_updated_at": "2026-10-01T10:00:00Z"},
        "career_history": [
            {
                "source_record_ref": "job-1",
                "company": "Acme",
                "role": "Engineer",
                "department": "R&D",
            }
        ],
        "education": [{"institution": "Uni", "degree": "BSc", "field": "CS"}],
        "certifications": [{"name": "Cloud cert", "issuer": "Example"}],
        "tools": [{"name": "Python"}],
        "languages": [{"name": "Vietnamese", "proficiency": "native"}],
        "projects": [{"name": "Migration"}],
        "interviews": [{"source_record_ref": "int-1", "score": 4}],
        "assessments": [
            {"source_record_ref": "assess-1", "dimensions": [{"name": "Python", "score": 8}]}
        ],
    }
    payload.update(overrides)
    return payload


def test_company_mapping_is_exact_and_department_is_not_a_fallback() -> None:
    organization_id = uuid4()
    mappings = [OrganizationExternalMapping("HRM", "CT Group", organization_id)]
    assert (
        resolve_organization(mappings, source_system="HRM", external_company_ref="CT Group")
        == organization_id
    )
    with pytest.raises(CandidateSourceError, match="organization_mapping_not_found"):
        resolve_organization(mappings, source_system="HRM", external_company_ref="CT group")
    with pytest.raises(CandidateSourceError, match="organization_mapping_not_found"):
        resolve_organization(mappings, source_system="HRM", external_company_ref="Engineering")


def test_fingerprint_is_stable_for_object_key_order_and_changes_with_content() -> None:
    assert canonical_fingerprint({"a": 1, "b": 2}) == canonical_fingerprint({"b": 2, "a": 1})
    assert canonical_fingerprint({"a": 1}) != canonical_fingerprint({"a": 2})


def test_source_revision_is_required_positive_strict_integer() -> None:
    payload = sample_payload()
    payload.pop("source_revision")
    with pytest.raises(ValueError):
        CandidateSourceEnvelope.model_validate(payload)

    for invalid_revision in (0, -1, True, 17.0, "17"):
        with pytest.raises(ValueError):
            CandidateSourceEnvelope.model_validate(sample_payload(source_revision=invalid_revision))


def test_source_revision_does_not_require_source_timestamp() -> None:
    payload = sample_payload(source_snapshot={})
    envelope = CandidateSourceEnvelope.model_validate(payload)
    assert envelope.source_revision == 17
    assert envelope.source_snapshot.source_updated_at is None


def test_content_fingerprint_excludes_ordering_and_audit_metadata() -> None:
    first = sample_payload(
        source_revision=17, source_snapshot={"source_updated_at": "2026-10-01T10:00:00Z"}
    )
    same_content_new_revision = sample_payload(
        source_revision=18, source_snapshot={"source_updated_at": "2026-10-02T10:00:00Z"}
    )
    changed_content = sample_payload(source_revision=18, career_history=[])

    first_envelope = CandidateSourceEnvelope.model_validate_json(json.dumps(first))
    newer_envelope = CandidateSourceEnvelope.model_validate_json(
        json.dumps(same_content_new_revision)
    )
    changed_envelope = CandidateSourceEnvelope.model_validate_json(json.dumps(changed_content))

    assert source_content_fingerprint(first_envelope) == source_content_fingerprint(newer_envelope)
    assert source_content_fingerprint(first_envelope) != source_content_fingerprint(
        changed_envelope
    )
    assert canonical_fingerprint(first) != canonical_fingerprint(same_content_new_revision)


def test_source_revision_orders_snapshots_without_using_timestamp_or_fingerprint() -> None:
    assert (
        snapshot_disposition(
            17, "content-17", current_revision=None, current_content_fingerprint=None
        )
        == "INITIAL"
    )
    assert (
        snapshot_disposition(
            18, "same-content", current_revision=17, current_content_fingerprint="same-content"
        )
        == "NEWER"
    )
    assert (
        snapshot_disposition(
            19, "same-content", current_revision=18, current_content_fingerprint="same-content"
        )
        == "NEWER"
    )
    assert (
        snapshot_disposition(
            17, "content-17", current_revision=17, current_content_fingerprint="content-17"
        )
        == "REPLAY"
    )
    with pytest.raises(CandidateSourceError, match="candidate_source_snapshot_stale"):
        snapshot_disposition(
            17, "old-content", current_revision=18, current_content_fingerprint="new-content"
        )
    with pytest.raises(CandidateSourceError, match="candidate_source_snapshot_revision_conflict"):
        snapshot_disposition(
            18,
            "different-content",
            current_revision=18,
            current_content_fingerprint="current-content",
        )
    # Source timestamps and ingestion time are not arguments to this decision.


def test_source_profile_projection_is_deterministic_and_does_not_promote_claims() -> None:
    envelope = CandidateSourceEnvelope.model_validate_json(json.dumps(sample_payload()))
    profile = project_candidate_profile(envelope)
    assert [(item.organization, item.role) for item in profile.employment_history] == [
        ("Acme", "Engineer")
    ]
    assert [(item.institution, item.degree, item.field) for item in profile.education] == [
        ("Uni", "BSc", "CS")
    ]
    assert [item.name for item in profile.credentials] == ["Cloud cert"]
    assert profile.skills == []
    assert profile.model_dump(mode="json") == project_candidate_profile(envelope).model_dump(
        mode="json"
    )


def test_source_only_records_and_absent_ai_scan_are_valid_and_preserved() -> None:
    payload = sample_payload()
    payload.pop("ats_ai_scanning", None)
    envelope = CandidateSourceEnvelope.model_validate_json(json.dumps(payload))
    assert len(envelope.interviews) == 1
    assert envelope.assessments[0].dimensions[0].score == 8
    assert envelope.ats_ai_scanning is None
    assert project_candidate_profile(envelope).skills == []
