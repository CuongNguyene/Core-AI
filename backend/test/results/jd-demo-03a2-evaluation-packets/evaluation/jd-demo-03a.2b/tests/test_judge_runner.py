import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from judge_runner import (  # noqa: E402, I001
    JudgePayload,
    _load_docx_text,
    discover_packets,
    validate_packet_result,
)


ROOT = Path(__file__).resolve().parents[3]


def test_discovers_ten_manifest_packets_and_preserves_pending_review() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    packets = discover_packets(ROOT, manifest)

    assert len(packets) == 10
    assert sum(len(packet["extracted_output"]["requirements"]) for packet in packets) == 67
    assert all(packet["source_text"] for packet in packets)
    assert all(packet["manifest_entry"]["runtime"]["review_state"] == "pending_review" for packet in packets)


def test_source_parser_matches_locator_excerpt_for_all_supported_outputs() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for packet in discover_packets(ROOT, manifest):
        source = packet["source_text"]
        for requirement in packet["extracted_output"]["requirements"]:
            excerpt = requirement["source_excerpt"]
            assert excerpt in source
            locator = requirement["source_locator"]
            assert source[locator["start_offset"] : locator["end_offset"]] == excerpt


def test_judge_result_requires_exactly_the_extracted_requirement_ids() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    packet = discover_packets(ROOT, manifest)[0]
    with pytest.raises(ValueError, match="do not reconcile"):
        validate_packet_result(
            packet,
            JudgePayload.model_validate(
                {
                    "packet_id": packet["packet_id"],
                    "scores": {key: 4 for key in (
                        "requirement_coverage", "unsupported_or_inferred_content", "atomicity_and_granularity",
                        "criterion_dimension_correctness", "modality_correctness", "duplicate_and_overlap_control",
                        "evidence_semantic_alignment", "overall_review_readiness",
                    )},
                    "special_questions": {
                        "semantically_reasonable": "YES",
                        "proceed_to_review_ui": "YES",
                        "calibration_needed": False,
                    },
                    "requirement_reviews": [],
                    "missing_requirements": [],
                    "summary_findings": [],
                }
            ),
        )


def test_docx_parser_is_deterministic() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    packet = discover_packets(ROOT, manifest)[0]
    assert _load_docx_text(packet["source_path"]) == packet["source_text"]
