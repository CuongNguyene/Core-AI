import json
from pathlib import Path

import pytest

from app.instructional_design.blinded_review_cli import load_experiment_results
from app.instructional_design.blinded_review_id03c import (
    ID03C_REVIEW_FIXTURES,
    build_id03c_bundle,
    validate_id03c_submission,
    write_id03c_bundle,
)

RESULTS = Path("test/results/instructional-design-id-03b6-cross-domain-smoke/results.json")


def _bundle(tmp_path: Path):
    bundle = build_id03c_bundle(load_experiment_results(RESULTS))
    write_id03c_bundle(bundle, tmp_path)
    return bundle


def test_id03c_has_exactly_one_packet_per_fixture_and_required_sections(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    assert len(bundle.packets) == 5
    assert [packet.fixture_id for packet in bundle.packets] == list(ID03C_REVIEW_FIXTURES)
    assert len({packet.review_id for packet in bundle.packets}) == 5
    for packet in bundle.packets:
        assert packet.brief.id
        assert packet.objectives is not None
        assert packet.assessments is not None
        assert packet.prerequisites is not None
        assert packet.course_outline is not None
        assert packet.lessons is not None
        assert packet.machine_observations is not None
        assert packet.review_instructions


def test_id03c_packets_do_not_leak_condition_or_private_metadata(tmp_path: Path) -> None:
    _bundle(tmp_path)
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "reviewer-packets").glob("review-*.json")
    ).lower()

    for forbidden in ("structured_v0.3.1", "one_shot", "prompt_versions", "model_provider", "root_cause"):
        assert forbidden not in text
    assert "machine_observations" in text


def test_id03c_manifest_and_empty_submission_directory(tmp_path: Path) -> None:
    _bundle(tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == {
        "experiment": "ID-03C",
        "source_experiment": "ID-03B.6",
        "review_type": "blinded_cross_domain_sme_review",
        "packet_count": 5,
        "fixtures": list(ID03C_REVIEW_FIXTURES),
        "rubric_version": "instructional_design_human_rubric@0.2",
        "submission_schema_version": "id03c_review_submission@0.1",
        "status": "prepared",
    }
    assert list((tmp_path / "reviewer-submissions").iterdir()) == []


def test_submission_validation_requires_all_scores_and_rationales(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    packet = bundle.packets[0]
    valid = {
        "review_id": packet.review_id,
        "rubric_scores": {
            name: 3
            for name in (
                "objective_measurability",
                "objective_assessment_alignment",
                "evidence_validity",
                "cognitive_alignment",
                "prerequisite_quality",
                "course_sequence_coherence",
                "instruction_assessment_alignment",
                "scope_balance",
                "workload_time_realism",
                "domain_appropriateness",
            )
        },
        "rationales": {
            name: "Evidence-based rationale"
            for name in (
                "objective_measurability",
                "objective_assessment_alignment",
                "evidence_validity",
                "cognitive_alignment",
                "prerequisite_quality",
                "course_sequence_coherence",
                "instruction_assessment_alignment",
                "scope_balance",
                "workload_time_realism",
                "domain_appropriateness",
            )
        },
        "machine_validity_observations": [],
        "prerequisites_acceptable": True,
        "edit_effort": "minor",
        "special_question": {"answer": "PARTIALLY", "rationale": "The design is usable with edits."},
        "top_strengths": ["Clear objective"],
        "top_issues": ["Needs review"],
    }
    assert validate_id03c_submission(packet, valid).review_id == packet.review_id

    missing = dict(valid)
    missing["rationales"] = dict(valid["rationales"])
    del missing["rationales"]["evidence_validity"]
    with pytest.raises(ValueError, match="rationale"):
        validate_id03c_submission(packet, missing)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("edit_effort", "huge"),
        ("special_question", {"answer": "UNKNOWN", "rationale": "x"}),
        ("rubric_scores", {"objective_measurability": 6}),
    ],
)
def test_submission_validation_rejects_invalid_values(tmp_path: Path, field: str, value: object) -> None:
    bundle = _bundle(tmp_path)
    packet = bundle.packets[0]
    payload = {
        "review_id": packet.review_id,
        "rubric_scores": {
            name: 3
            for name in (
                "objective_measurability", "objective_assessment_alignment", "evidence_validity",
                "cognitive_alignment", "prerequisite_quality", "course_sequence_coherence",
                "instruction_assessment_alignment", "scope_balance", "workload_time_realism",
                "domain_appropriateness",
            )
        },
        "rationales": {name: "reason" for name in (
            "objective_measurability", "objective_assessment_alignment", "evidence_validity",
            "cognitive_alignment", "prerequisite_quality", "course_sequence_coherence",
            "instruction_assessment_alignment", "scope_balance", "workload_time_realism",
            "domain_appropriateness",
        )},
        "machine_validity_observations": [], "prerequisites_acceptable": True,
        "edit_effort": "minor", "special_question": {"answer": "YES", "rationale": "reason"},
        "top_strengths": [], "top_issues": [],
    }
    payload[field] = value
    with pytest.raises(ValueError):
        validate_id03c_submission(packet, payload)


def test_submission_review_id_must_match_packet(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    with pytest.raises(ValueError, match="review_id"):
        validate_id03c_submission(bundle.packets[0], {"review_id": "review-999"})
