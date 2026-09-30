"""Deterministic recovery of legacy ID-03C reviewer submissions."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.instructional_design.blinded_review_id03c import (
    RUBRIC_DIMENSIONS,
    ID03CReviewPacket,
    validate_id03c_submission,
)

_RUBRIC_ALIASES = {"sequence_coherence": "course_sequence_coherence"}
_EDIT_EFFORTS = {"none", "minor", "moderate", "major", "rewrite"}
_SPECIAL_ANSWERS = {"yes": "YES", "partially": "PARTIALLY", "no": "NO"}


@dataclass
class RecoveryRecord:
    review_id: str
    draft: dict[str, Any]
    recovery_metadata: dict[str, Any]
    missing_required_fields: list[str] = field(default_factory=list)
    ambiguous_fields: list[str] = field(default_factory=list)
    canonical_submission: dict[str, Any] | None = None
    state: str = "NEEDS_REVIEWER_COMPLETION"
    source_path: str | None = None


@dataclass
class RecoveryBatch:
    records: list[RecoveryRecord]
    source_submissions: int


def _score_items(legacy: dict[str, Any]) -> tuple[dict[str, int], dict[str, str]]:
    scores: dict[str, int] = {}
    rationales: dict[str, str] = {}
    for item in legacy.get("rubric_scores", []):
        if not isinstance(item, dict) or not isinstance(item.get("dimension"), str):
            continue
        name = item["dimension"]
        canonical = _RUBRIC_ALIASES.get(name, name)
        if canonical not in RUBRIC_DIMENSIONS:
            continue
        if isinstance(item.get("score"), int) and 1 <= item["score"] <= 5:
            scores[canonical] = item["score"]
        if isinstance(item.get("rationale"), str) and item["rationale"].strip():
            rationales[canonical] = item["rationale"]
    return scores, rationales


def _special_question(legacy: dict[str, Any]) -> tuple[dict[str, str] | None, list[str], dict[str, Any]]:
    raw = legacy.get("special_question", {})
    if not isinstance(raw, dict) or not isinstance(raw.get("answer"), str):
        return None, ["special_question.answer"], {}
    answer = raw["answer"].strip()
    canonical = _SPECIAL_ANSWERS.get(answer.casefold())
    if canonical is None:
        return None, ["special_question.answer"], {"raw_special_question_answer": answer}
    rationale = raw.get("rationale", raw.get("notes"))
    if not isinstance(rationale, str) or not rationale.strip():
        return None, ["special_question.rationale"], {"raw_special_question_answer": answer}
    return {"answer": canonical, "rationale": rationale}, [], {}


def _machine_observations(legacy: dict[str, Any]) -> list[dict[str, Any]]:
    technical = legacy.get("technical_review", {})
    issues = technical.get("issues", []) if isinstance(technical, dict) else []
    return [
        {
            "code": str(issue.get("category", "legacy_observation")),
            "severity": str(issue.get("severity", "info")),
            "entity_type": None,
            "entity_id": str(issue["entity"]) if issue.get("entity") else None,
            "field": str(issue["field"]) if issue.get("field") else None,
            "message": str(issue.get("description", "Legacy reviewer observation")),
        }
        for issue in issues
        if isinstance(issue, dict)
    ]


def recover_submission(
    payload: dict[str, Any], *, packet: ID03CReviewPacket | None = None, source_path: Path | None = None
) -> RecoveryRecord:
    review_id = payload.get("review_id")
    if not isinstance(review_id, str) or not review_id:
        raise ValueError("review_id is required")
    pedagogical = payload.get("pedagogical_review")
    if not isinstance(pedagogical, dict):
        raise ValueError("pedagogical_review section is required")
    if not isinstance(payload.get("technical_review"), dict):
        raise ValueError("technical_review section is required")
    scores, rationales = _score_items(pedagogical)
    special, special_missing, special_meta = _special_question(pedagogical)
    acceptance = pedagogical.get("prerequisite_acceptance", {})
    decision = acceptance.get("decision") if isinstance(acceptance, dict) else None
    prerequisites = True if decision == "accept" else False if decision == "reject" else None
    edit = pedagogical.get("edit_effort", {})
    edit_level = edit.get("level") if isinstance(edit, dict) else None
    edit_effort = edit_level if edit_level in _EDIT_EFFORTS else None
    if edit_effort is None:
        legacy_edit = next(
            (item.get("score") for item in pedagogical.get("rubric_scores", [])
             if isinstance(item, dict) and item.get("dimension") == "overall_edit_effort"),
            None,
        )
        if isinstance(legacy_edit, str) and legacy_edit in _EDIT_EFFORTS:
            edit_effort = legacy_edit
    missing = [f"rubric_scores.{name}" for name in RUBRIC_DIMENSIONS if name not in scores]
    missing.extend(f"rationales.{name}" for name in RUBRIC_DIMENSIONS if name not in rationales)
    if prerequisites is None:
        missing.append("prerequisites_acceptable")
    if edit_effort is None:
        missing.append("edit_effort")
    missing.extend(special_missing)
    metadata: dict[str, Any] = {
        "source_submission": str(source_path) if source_path else None,
        "source_rubric_version": payload.get("rubric_version"),
        "target_rubric_version": "instructional_design_human_rubric@0.2",
        "recovery_mode": "deterministic",
        "source_sections": [name for name in ("technical_review", "pedagogical_review") if name in payload],
        "mapped_fields": sorted(set(scores) | set(rationales) | {"machine_validity_observations"}),
        "unresolved_fields": sorted(set(missing)),
        "raw_legacy_fields_preserved": True,
        "legacy_rubric_scores": pedagogical.get("rubric_scores", []),
        "legacy_overall_edit_effort": next(
            (item.get("score") for item in pedagogical.get("rubric_scores", [])
             if isinstance(item, dict) and item.get("dimension") == "overall_edit_effort"),
            None,
        ),
        **special_meta,
    }
    draft: dict[str, Any] = {
        "review_id": review_id,
        "rubric_scores": scores,
        "rationales": rationales,
        "machine_validity_observations": _machine_observations(payload),
        "prerequisites_acceptable": prerequisites,
        "edit_effort": edit_effort,
        "special_question": special,
        "top_strengths": [],
        "top_issues": [],
    }
    canonical: dict[str, Any] | None = None
    if not missing and packet is not None:
        try:
            canonical = validate_id03c_submission(packet, draft).model_dump(mode="json")
        except ValueError:
            missing.append("canonical_validation")
    state = "CANONICAL_VALID" if canonical is not None else "NEEDS_REVIEWER_COMPLETION"
    metadata["unresolved_fields"] = sorted(set(missing))
    return RecoveryRecord(
        review_id=review_id,
        draft=draft,
        recovery_metadata=metadata,
        missing_required_fields=sorted(set(missing)),
        ambiguous_fields=special_missing,
        canonical_submission=canonical,
        state=state,
        source_path=str(source_path) if source_path else None,
    )


def recover_submission_directory(source_dir: Path) -> RecoveryBatch:
    records = [
        recover_submission(json.loads(path.read_text(encoding="utf-8")), source_path=path)
        for path in sorted(source_dir.glob("*/*.json"))
    ]
    return RecoveryBatch(records=records, source_submissions=len(records))


def _completion_request(record: RecoveryRecord, payload: dict[str, Any], fixture: str | None) -> dict[str, Any]:
    required: dict[str, Any] = {}
    for name in RUBRIC_DIMENSIONS:
        if f"rubric_scores.{name}" in record.missing_required_fields or f"rationales.{name}" in record.missing_required_fields:
            required[f"rubric_scores.{name}"] = {
                "type": "integer", "allowed_range": [1, 5], "rationale_required": True
            }
    if "prerequisites_acceptable" in record.missing_required_fields:
        required["prerequisites_acceptable"] = {"type": "boolean"}
    if any(name.startswith("special_question.") for name in record.missing_required_fields):
        required["special_question"] = {
            "answer": {"type": "enum", "allowed_values": ["YES", "PARTIALLY", "NO"]},
            "rationale_required": True,
        }
    if "edit_effort" in record.missing_required_fields:
        required["edit_effort"] = {
            "type": "enum", "allowed_values": ["none", "minor", "moderate", "major", "rewrite"]
        }
    return {
        "review_id": record.review_id,
        "reviewer_id": payload.get("reviewer_id"),
        "fixture_id": fixture,
        "instruction": "Complete only the fields listed in required_completion. Do not revise previously submitted judgement.",
        "required_completion": required,
        "original_relevant_comments": {
            "special_question": payload.get("pedagogical_review", {}).get("special_question"),
            "edit_effort": payload.get("pedagogical_review", {}).get("edit_effort"),
            "prerequisite_acceptance": payload.get("pedagogical_review", {}).get("prerequisite_acceptance"),
        },
    }


def write_recovery(batch: RecoveryBatch, *, output_dir: Path, packets_dir: Path | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment": "ID-03C.1", "source_experiment": "ID-03C",
        "source_submission_count": batch.source_submissions,
        "target_rubric_version": "instructional_design_human_rubric@0.2",
        "recovery_mode": "deterministic", "source_files_modified": 0, "status": "recovered",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    packet_map: dict[str, ID03CReviewPacket] = {}
    if packets_dir:
        for path in packets_dir.glob("review-*.json"):
            packet = ID03CReviewPacket.model_validate_json(path.read_text(encoding="utf-8"))
            packet_map[packet.review_id] = packet
    inventory: list[dict[str, Any]] = []
    missing_summary: dict[str, int] = {}
    ambiguous_summary: dict[str, int] = {}
    final_records: list[RecoveryRecord] = []
    for record in batch.records:
        if record.source_path is None:
            raise ValueError("recovery record is missing source_path")
        source_path = Path(record.source_path)
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        packet_for_record = packet_map.get(record.review_id)
        if packet_for_record is not None:
            record = recover_submission(payload, packet=packet_for_record, source_path=source_path)
        final_records.append(record)
        review_dir = output_dir / record.review_id
        review_dir.mkdir(exist_ok=True)
        if packet_for_record is not None and packets_dir is not None:
            packet_path = packets_dir / f"{record.review_id}.json"
            if packet_path.is_file():
                shutil.copyfile(packet_path, review_dir / "reviewer-packet.json")
        (review_dir / "canonical-draft.json").write_text(json.dumps({
            "state": record.state, "draft": record.draft,
            "recovery_metadata": record.recovery_metadata,
            "missing_required_fields": record.missing_required_fields,
            "ambiguous_fields": record.ambiguous_fields,
        }, indent=2, ensure_ascii=False) + "\n")
        if record.state != "CANONICAL_VALID":
            fixture = packet_for_record.fixture_id if packet_for_record else None
            (review_dir / "completion-request.json").write_text(
                json.dumps(_completion_request(record, payload, fixture), indent=2, ensure_ascii=False) + "\n"
            )
        for name in record.missing_required_fields:
            missing_summary[name] = missing_summary.get(name, 0) + 1
        for name in record.ambiguous_fields:
            ambiguous_summary[name] = ambiguous_summary.get(name, 0) + 1
        inventory.append({
            "review_id": record.review_id, "reviewer_id": payload.get("reviewer_id"),
            "fixture": packet_for_record.fixture_id if packet_for_record else None,
            "source_rubric_version": payload.get("rubric_version"),
            "target_rubric_version": "instructional_design_human_rubric@0.2",
            "recoverable_fields": record.recovery_metadata["mapped_fields"],
            "missing_fields": record.missing_required_fields, "ambiguous_fields": record.ambiguous_fields,
            "source_path": record.source_path,
            "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        })
    canonical_count = sum(record.state == "CANONICAL_VALID" for record in final_records)
    (output_dir / "recovery-inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n")
    (output_dir / "recovery-report.json").write_text(json.dumps({
        "source_submissions": batch.source_submissions, "canonical_valid": canonical_count,
        "needs_reviewer_completion": batch.source_submissions - canonical_count,
        "deterministically_mapped_fields": {
            "sequence_coherence": "course_sequence_coherence", "overall_edit_effort": "edit_effort"
        }, "missing_fields_summary": missing_summary, "ambiguous_fields_summary": ambiguous_summary,
        "source_files_modified": 0, "non_canonical_preliminary_signal": True,
    }, indent=2, ensure_ascii=False) + "\n")
    (output_dir / "validation-report.json").write_text(json.dumps({
        "source_submissions": batch.source_submissions, "source_files_modified": 0,
        "canonical_valid": canonical_count, "needs_reviewer_completion": batch.source_submissions - canonical_count,
        "all_drafts_state_explicit": True, "status": "valid",
    }, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover legacy ID-03C submissions")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--packets-dir", type=Path, required=True)
    args = parser.parse_args()
    batch = recover_submission_directory(args.source_dir)
    write_recovery(batch, output_dir=args.output_dir, packets_dir=args.packets_dir)
    print(json.dumps({"source_submissions": batch.source_submissions}))


if __name__ == "__main__":
    main()
