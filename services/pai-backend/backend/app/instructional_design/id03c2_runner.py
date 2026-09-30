"""Run the ID-03C.2 completion merge without mutating any source artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from app.instructional_design.blinded_review_id03c import ID03CReviewPacket
from app.instructional_design.blinded_review_id03c1_recovery import recover_submission
from app.instructional_design.blinded_review_id03c2_merge import merge_completion


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def run_merge(
    *,
    recovery_dir: Path,
    source_submissions_dir: Path,
    completion_dir: Path,
    packets_dir: Path,
    output_dir: Path,
    reviewer_id_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    reviewer_id_aliases = reviewer_id_aliases or {}
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment": "ID-03C.2",
        "source_recovery": "ID-03C.1",
        "operation": "reviewer_completion_merge",
        "expected_reviewers": 2,
        "expected_reviews_per_reviewer": 5,
        "expected_completion_submissions": 10,
        "rubric_version": "instructional_design_human_rubric@0.2",
        "merge_mode": "deterministic",
        "source_mutation_allowed": False,
        "reviewer_id_aliases": reviewer_id_aliases,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    source_files = sorted(source_submissions_dir.glob("*/*.json"))
    completion_files = sorted(completion_dir.glob("*/*.json"))
    source_map: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
    source_hashes = {str(path): _sha(path) for path in source_files}
    for path in source_files:
        payload = _load_json(path)
        key = (payload.get("review_id", ""), payload.get("reviewer_id", ""))
        source_map[key] = (path, payload)
    packet_map = {
        packet.review_id: packet
        for path in packets_dir.glob("review-*.json")
        for packet in [ID03CReviewPacket.model_validate_json(path.read_text(encoding="utf-8"))]
    }
    canonical_hashes = {
        str(path): _sha(path)
        for path in recovery_dir.glob("review-*/canonical-draft.json")
    }
    inventory: list[dict[str, Any]] = []
    merge_results: list[dict[str, Any]] = []
    canonical_dir = output_dir / "canonical-submissions"
    failed_dir = output_dir / "failed-submissions"
    canonical_dir.mkdir(exist_ok=True)
    failed_dir.mkdir(exist_ok=True)

    for completion_path in completion_files:
        completion = _load_json(completion_path)
        key = (completion.get("review_id", ""), completion.get("reviewer_id", ""))
        review_id, reviewer_id = key
        source_entry = source_map.get(key)
        resolved_reviewer_id = reviewer_id
        if source_entry is None and reviewer_id in reviewer_id_aliases:
            resolved_reviewer_id = reviewer_id_aliases[reviewer_id]
            source_entry = source_map.get((review_id, resolved_reviewer_id))
        source_path = source_entry[0] if source_entry else None
        requested_record = recover_submission(source_entry[1], source_path=source_path) if source_entry else None
        request_path = recovery_dir / review_id / "completion-request.json"
        requested_fields = set(requested_record.missing_required_fields if requested_record else [])
        if "special_question.answer" in requested_fields:
            requested_fields.add("special_question.rationale")
        requested_field_list = sorted(requested_fields)
        submitted_fields: list[str] = []
        raw_completion = completion.get("completion")
        if isinstance(raw_completion, dict):
            submitted_fields.extend(f"rubric_scores.{name}" for name in raw_completion.get("rubric_scores", {}))
            submitted_fields.extend(f"rationales.{name}" for name in raw_completion.get("rationales", {}))
            if "prerequisites_acceptable" in raw_completion:
                submitted_fields.append("prerequisites_acceptable")
            if isinstance(raw_completion.get("special_question"), dict):
                submitted_fields.extend(f"special_question.{name}" for name in raw_completion["special_question"])
        unexpected = sorted(set(submitted_fields) - set(requested_field_list))
        missing = sorted(set(requested_field_list) - set(submitted_fields))
        inventory_item = {
            "review_id": review_id,
            "reviewer_id": reviewer_id,
            "resolved_reviewer_id": resolved_reviewer_id if source_entry else None,
            "completion_submission_path": str(completion_path),
            "matching_canonical_draft": str(recovery_dir / review_id / "canonical-draft.json"),
            "matching_completion_request": str(request_path),
            "source_sha256": _sha(completion_path),
            "requested_fields": requested_field_list,
            "submitted_fields": submitted_fields,
            "unexpected_fields": unexpected,
            "missing_requested_fields": missing,
        }
        if source_entry is None or review_id not in packet_map:
            result_state = "INVALID_COMPLETION"
            result_errors = ["completion has no matching source submission or packet"]
            merged = None
        else:
            draft = recover_submission(source_entry[1], packet=packet_map[review_id], source_path=source_path).draft
            request: dict[str, Any] = {"required_completion": {name: {} for name in requested_field_list}}
            normalized_completion = deepcopy(completion)
            normalized_completion["reviewer_id"] = resolved_reviewer_id
            result = merge_completion(
                draft,
                request,
                normalized_completion,
                expected_reviewer_id=resolved_reviewer_id,
                packet=packet_map[review_id],
            )
            result_state, result_errors, merged = result.state, result.errors, result.merged
        inventory_item["state"] = result_state
        inventory.append(inventory_item)
        merge_item = {
            "review_id": review_id,
            "reviewer_id": reviewer_id,
            "resolved_reviewer_id": resolved_reviewer_id if source_entry else None,
            "state": result_state,
            "errors": result_errors,
            "completed_fields": sorted(set(submitted_fields) - set(unexpected)),
            "existing_judgement_overwrites": 0,
            "conflict_attempt": result_state == "CONFLICT",
        }
        if merged is not None and result_state == "CANONICAL_VALID":
            final = {
                "state": result_state,
                "submission": merged,
                "recovery_metadata": {
                    "source_submission": str(source_path),
                    "source_submission_sha256": _sha(source_path) if source_path else None,
                    "recovery_version": "ID-03C.1",
                },
                "completion_metadata": {
                    "completion_submission": str(completion_path),
                    "completion_submission_sha256": _sha(completion_path),
                    "completed_fields": sorted(set(submitted_fields) - set(unexpected)),
                    "merge_mode": "deterministic",
                },
            }
            (canonical_dir / f"{reviewer_id}--{review_id}.json").write_text(
                json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            merge_item["canonical_submission"] = str(canonical_dir / f"{reviewer_id}--{review_id}.json")
        else:
            diagnostic = {**merge_item, "completion_submission": str(completion_path), "requested_fields": requested_field_list}
            (failed_dir / f"{reviewer_id}--{review_id}.json").write_text(
                json.dumps(diagnostic, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        merge_results.append(merge_item)

    states = {state: sum(item["state"] == state for item in merge_results) for state in (
        "CANONICAL_VALID", "INCOMPLETE", "CONFLICT", "INVALID_COMPLETION"
    )}
    reviewer_counts: dict[str, dict[str, int]] = {}
    for item in merge_results:
        reviewer_counts.setdefault(item.get("resolved_reviewer_id", item["reviewer_id"]), {"expected": 5, "valid": 0})
        if item["state"] == "CANONICAL_VALID":
            reviewer_counts[item["reviewer_id"]]["valid"] += 1
    all_sources_unchanged = all(_sha(Path(path)) == digest for path, digest in source_hashes.items())
    all_drafts_unchanged = all(_sha(Path(path)) == digest for path, digest in canonical_hashes.items())
    summary = {
        "total_completion_submissions": len(completion_files),
        "states": states,
        "reviewers": reviewer_counts,
        "required_fields_missing": sum(len(item["missing_requested_fields"]) for item in inventory),
        "ready_for_sme_analysis": states["CANONICAL_VALID"] == 10 and all_sources_unchanged and all_drafts_unchanged,
        "existing_judgement_overwrites": sum(item["existing_judgement_overwrites"] for item in merge_results),
    }
    (output_dir / "completion-inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "merge-results.json").write_text(json.dumps(merge_results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "canonical-review-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "validation-report.json").write_text(json.dumps({
        **summary,
        "source_submissions_modified": 0 if all_sources_unchanged else 1,
        "canonical_drafts_modified_in_place": 0 if all_drafts_unchanged else 1,
        "completion_submissions_modified": 0,
        "status": "valid" if all_sources_unchanged and all_drafts_unchanged else "integrity_failure",
    }, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge ID-03C.2 reviewer completion submissions")
    parser.add_argument("--recovery-dir", type=Path, required=True)
    parser.add_argument("--source-submissions-dir", type=Path, required=True)
    parser.add_argument("--completion-dir", type=Path, required=True)
    parser.add_argument("--packets-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reviewer-id-alias", action="append", default=[])
    args = parser.parse_args()
    aliases = {}
    for item in args.reviewer_id_alias:
        source, separator, target = item.partition("=")
        if not separator or not source or not target:
            raise SystemExit("--reviewer-id-alias must use submitted_id=source_id")
        aliases[source] = target
    values = vars(args)
    values["reviewer_id_aliases"] = aliases
    values.pop("reviewer_id_alias", None)
    print(json.dumps(run_merge(**values), ensure_ascii=False))


if __name__ == "__main__":
    main()
