from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.candidate_semantics.contracts import CandidateSemanticEvidenceKind
from app.candidate_semantics.structured_adapter import adapt_candidate_source_snapshot


def snapshot(payload: dict[str, object], *, schema_id: str, schema_version: str) -> SimpleNamespace:
    return SimpleNamespace(
        candidate_id="candidate:42",
        organization_id="organization:7",
        source_system="HRM",
        employee_ref="HR-EMP-00280",
        snapshot_id="snapshot:abc",
        schema_id=schema_id,
        schema_version=schema_version,
        source_revision=17,
        content_fingerprint="a" * 64,
        payload=payload,
    )


def learning_projection() -> dict[str, object]:
    fixture = Path(__file__).parent / "fixtures/employee_learning_projection_v1.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


def test_learning_projection_adapts_eligible_facts_with_exact_paths_and_exclusions() -> None:
    result = adapt_candidate_source_snapshot(
        snapshot(
            learning_projection(),
            schema_id="pai.employee-learning-projection",
            schema_version="1.0",
        )
    )

    assert any(
        item.content == "Phát triển dịch vụ Python; không phải capability claim."
        and item.field_path == "candidate_source.career_history[0].responsibilities"
        and item.source_record_ref == "career-1"
        and item.source_kind is CandidateSemanticEvidenceKind.EMPLOYMENT
        for item in result
    )
    paths = {item.field_path for item in result}
    assert "candidate_source.education[0].degree" in paths
    assert "candidate_source.certifications[0].name" in paths
    assert "candidate_source.projects[0].description" in paths
    contents = {item.content for item in result}
    assert "English" not in contents
    assert "Odoo" not in contents
    assert all("ATS" not in item.content for item in result)
    assert all("score" not in item.field_path for item in result)
    assert all(item.transport_schema_version is None for item in result)


def test_outer_transport_v1_is_kept_separate_from_learning_projection_1_0() -> None:
    data = learning_projection()
    wrapped = {"schema_version": "v1", "data": data}

    result = adapt_candidate_source_snapshot(
        snapshot(
            wrapped,
            schema_id="pai.employee-learning-projection",
            schema_version="1.0",
        )
    )

    assert result
    assert {item.transport_schema_version for item in result} == {"v1"}
    assert {item.source_revision for item in result} == {17}


def test_legacy_candidate_source_schema_uses_separate_schema_id_and_version() -> None:
    payload: dict[str, object] = {
        "schema_id": "pai.candidate-source",
        "schema_version": "v1",
        "source_revision": 17,
        "company": "Example Corp",
        "identity": {"source_system": "HRM", "employee_ref": "HR-EMP-00280"},
        "career_history": [
            {
                "source_record_ref": "job-9",
                "responsibilities": "Coordinated delivery milestones.",
                "technologies": ["Do not include"],
            }
        ],
        "education": [],
        "certifications": [],
        "projects": [],
        "tools": [{"name": "Do not include"}],
        "languages": [],
        "interviews": [],
        "assessments": [],
        "ats_ai_scanning": {"reason": "Do not include"},
        "source_snapshot": {"source_updated_at": "2026-10-01T10:00:00Z"},
    }

    result = adapt_candidate_source_snapshot(
        snapshot(payload, schema_id="pai.candidate-source", schema_version="v1")
    )

    assert len(result) == 1
    assert result[0].field_path == "career_history[0].responsibilities"
    assert result[0].content == "Coordinated delivery milestones."


@pytest.mark.parametrize(
    ("schema_id", "schema_version"),
    [
        ("pai.employee-learning-projection@1.0", "1.0"),
        ("pai.employee-learning-projection", "v1"),
        ("pai.candidate-source", "1.0"),
        ("unsupported", "1.0"),
    ],
)
def test_schema_identity_fields_are_validated_separately(
    schema_id: str, schema_version: str
) -> None:
    with pytest.raises(ValueError):
        adapt_candidate_source_snapshot(
            snapshot(learning_projection(), schema_id=schema_id, schema_version=schema_version)
        )


def test_empty_and_missing_eligible_fields_emit_no_evidence() -> None:
    data = learning_projection()
    data["candidate_source"] = {
        "career_history": [{"source_record_ref": "empty", "responsibilities": "  "}],
        "education": [],
        "languages": [],
        "tools": [],
        "certifications": [],
        "projects": [],
    }
    data["recruitment_evidence"] = {"interviewer_feedback": [], "assessments": []}
    data.pop("auxiliary_signals", None)

    assert not adapt_candidate_source_snapshot(
        snapshot(
            data,
            schema_id="pai.employee-learning-projection",
            schema_version="1.0",
        )
    )
