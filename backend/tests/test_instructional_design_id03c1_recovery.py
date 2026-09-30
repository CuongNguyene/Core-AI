import json
from pathlib import Path

import pytest

from app.instructional_design.blinded_review_id03c import ID03CReviewPacket
from app.instructional_design.blinded_review_id03c1_recovery import (
    recover_submission,
    recover_submission_directory,
    write_recovery,
)


def _legacy(answer: str = "yes") -> dict:
    dimensions = {
        "objective_measurability",
        "objective_assessment_alignment",
        "evidence_validity",
        "cognitive_alignment",
        "prerequisite_quality",
        "sequence_coherence",
        "instruction_assessment_alignment",
        "under_teaching",
        "over_teaching",
        "overall_edit_effort",
    }
    return {
        "review_id": "review-001",
        "reviewer_id": "reviewer-01",
        "rubric_version": "instructional_design_human_rubric@0.1",
        "technical_review": {"issues": []},
        "pedagogical_review": {
            "special_question": {"answer": answer, "notes": "Reason"},
            "rubric_scores": [
                {"dimension": name, "score": 3, "rationale": "Reason"}
                for name in dimensions
            ],
            "prerequisite_acceptance": {"decision": "accept"},
            "edit_effort": {"level": "minor"},
        },
    }


def test_aliases_and_lossless_sections_are_recovered() -> None:
    result = recover_submission(_legacy())

    assert result.draft["rubric_scores"]["course_sequence_coherence"] == 3
    assert result.draft["edit_effort"] == "minor"
    assert result.draft["special_question"] == {"answer": "YES", "rationale": "Reason"}
    assert "technical_review" in result.recovery_metadata["source_sections"]
    assert "pedagogical_review" in result.recovery_metadata["source_sections"]


def test_edit_effort_alias_accepts_exact_legacy_enum() -> None:
    payload = _legacy()
    pedagogical = payload["pedagogical_review"]
    pedagogical["edit_effort"] = {}
    for item in pedagogical["rubric_scores"]:
        if item["dimension"] == "overall_edit_effort":
            item["score"] = "minor"
    packet_path = Path(
        "test/results/instructional-design-id-03c-human-review/reviewer-packets/review-001.json"
    )
    packet = ID03CReviewPacket.model_validate_json(packet_path.read_text(encoding="utf-8"))
    result = recover_submission(payload, packet=packet)

    assert result.draft["edit_effort"] == "minor"


def test_missing_dimensions_are_not_inferred_from_under_or_over_teaching() -> None:
    result = recover_submission(_legacy())

    assert "rubric_scores.scope_balance" in result.missing_required_fields
    assert "rubric_scores.workload_time_realism" in result.missing_required_fields
    assert "rubric_scores.domain_appropriateness" in result.missing_required_fields
    assert "rubric_scores.scope_balance" not in result.draft["rubric_scores"]


def test_mixed_special_question_is_unresolved() -> None:
    result = recover_submission(_legacy("YES. The design is sound [cite: 21]."))

    assert "special_question.answer" in result.ambiguous_fields
    assert "special_question.answer" in result.missing_required_fields
    assert result.recovery_metadata["raw_special_question_answer"] == (
        "YES. The design is sound [cite: 21]."
    )


def test_recovery_directory_does_not_modify_source_bytes(tmp_path: Path) -> None:
    source = tmp_path / "reviewer1"
    source.mkdir()
    path = source / "review-001.json"
    original = json.dumps(_legacy(), indent=2).encode()
    path.write_bytes(original)

    result = recover_submission_directory(tmp_path)

    assert result.source_submissions == 1
    assert path.read_bytes() == original


def test_canonical_draft_with_missing_fields_is_not_valid() -> None:
    result = recover_submission(_legacy())

    assert result.state == "NEEDS_REVIEWER_COMPLETION"
    assert result.canonical_submission is None


def test_complete_recovered_shape_can_pass_canonical_validator() -> None:
    payload = _legacy()
    pedagogical = payload["pedagogical_review"]
    pedagogical["special_question"] = {"answer": "YES", "notes": "Reason"}
    for name in ("scope_balance", "workload_time_realism", "domain_appropriateness"):
        pedagogical["rubric_scores"].append({"dimension": name, "score": 3, "rationale": "Reason"})
    packet_path = Path(
        "test/results/instructional-design-id-03c-human-review/reviewer-packets/review-001.json"
    )
    packet = ID03CReviewPacket.model_validate_json(packet_path.read_text(encoding="utf-8"))
    result = recover_submission(payload, packet=packet)

    assert result.missing_required_fields == []
    assert result.draft["rubric_scores"]["scope_balance"] == 3
    assert result.state == "CANONICAL_VALID"


def test_unknown_source_shape_fails_closed() -> None:
    with pytest.raises(ValueError, match="pedagogical_review"):
        recover_submission({"review_id": "review-001"})


def test_completion_request_uses_typed_field_contract_and_review_layout(tmp_path: Path) -> None:
    source_dir = Path("test/results/instructional-design-id-03c-human-review/reviewer-submissions")
    packets_dir = Path("test/results/instructional-design-id-03c-human-review/reviewer-packets")
    output_dir = tmp_path / "recovery"

    write_recovery(
        recover_submission_directory(source_dir),
        output_dir=output_dir,
        packets_dir=packets_dir,
    )
    request = json.loads((output_dir / "review-001/completion-request.json").read_text())

    assert request["instruction"].startswith("Complete only the fields")
    assert request["fixture_id"] == "python_data_processing"
    assert request["required_completion"]["rubric_scores.scope_balance"] == {
        "type": "integer",
        "allowed_range": [1, 5],
        "rationale_required": True,
    }
    assert request["required_completion"]["special_question"] == {
        "answer": {"type": "enum", "allowed_values": ["YES", "PARTIALLY", "NO"]},
        "rationale_required": True,
    }
