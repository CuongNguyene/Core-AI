"""Strict deterministic merge of ID-03C completion deltas."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from app.instructional_design.blinded_review_id03c import (
    ID03CReviewPacket,
    validate_id03c_submission,
)

_RUBRIC_FIELDS = (
    "objective_measurability", "objective_assessment_alignment", "evidence_validity",
    "cognitive_alignment", "prerequisite_quality", "course_sequence_coherence",
    "instruction_assessment_alignment", "scope_balance", "workload_time_realism",
    "domain_appropriateness",
)


@dataclass
class MergeResult:
    state: str
    merged: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    completed_fields: list[str] = field(default_factory=list)
    unexpected_fields: list[str] = field(default_factory=list)


def _flatten_completion(completion: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for name, value in completion.get("rubric_scores", {}).items():
        flat[f"rubric_scores.{name}"] = value
    for name, value in completion.get("rationales", {}).items():
        flat[f"rationales.{name}"] = value
    if "prerequisites_acceptable" in completion:
        flat["prerequisites_acceptable"] = completion["prerequisites_acceptable"]
    special = completion.get("special_question")
    if isinstance(special, dict):
        if "answer" in special:
            flat["special_question.answer"] = special["answer"]
        if "rationale" in special:
            flat["special_question.rationale"] = special["rationale"]
    if "edit_effort" in completion:
        flat["edit_effort"] = completion["edit_effort"]
    return flat


def _requested_fields(request: dict[str, Any]) -> set[str]:
    fields = set(request.get("required_completion", {}))
    expanded: set[str] = set()
    for name in fields:
        if name.startswith("rubric_scores."):
            dimension = name.split(".", 1)[1]
            expanded.update({f"rubric_scores.{dimension}", f"rationales.{dimension}"})
        elif name == "special_question":
            expanded.update({"special_question.answer", "special_question.rationale"})
        else:
            expanded.add(name)
    return expanded


def _draft_value(draft: dict[str, Any], path: str) -> Any:
    section, field = path.split(".", 1) if "." in path else (path, None)
    if field is None:
        return draft.get(section)
    return draft.get(section, {}).get(field) if isinstance(draft.get(section), dict) else None


def _set_draft_value(draft: dict[str, Any], path: str, value: Any) -> None:
    if "." not in path:
        draft[path] = value
        return
    section, field = path.split(".", 1)
    if not isinstance(draft.get(section), dict):
        draft[section] = {}
    draft[section][field] = value


def _validate_value(path: str, value: Any) -> str | None:
    if path.startswith("rubric_scores."):
        if type(value) is not int or not 1 <= value <= 5:
            return f"invalid rubric score: {path}"
    elif path.startswith("rationales.") or path == "special_question.rationale":
        if not isinstance(value, str) or not value.strip():
            return f"invalid rationale: {path}"
    elif path == "prerequisites_acceptable" and type(value) is not bool:
        return "prerequisites_acceptable must be a strict boolean"
    elif path == "special_question.answer" and value not in {"YES", "PARTIALLY", "NO"}:
        return "invalid special question answer"
    return None


def merge_completion(
    draft: dict[str, Any],
    request: dict[str, Any],
    submission: dict[str, Any],
    *,
    expected_reviewer_id: str,
    packet: ID03CReviewPacket | None = None,
) -> MergeResult:
    merged = deepcopy(draft)
    errors: list[str] = []
    review_id = submission.get("review_id")
    reviewer_id = submission.get("reviewer_id")
    if review_id != draft.get("review_id"):
        errors.append("review_id mismatch")
    if reviewer_id != expected_reviewer_id:
        errors.append("reviewer_id mismatch")
    completion = submission.get("completion")
    if not isinstance(completion, dict):
        errors.append("completion object is required")
        return MergeResult("INVALID_COMPLETION", merged, errors)
    requested = _requested_fields(request)
    flat = _flatten_completion(completion)
    unexpected = [name for name in flat if name not in requested]
    conflicts = [
        name for name in unexpected
        if _draft_value(draft, name) is not None
    ]
    if conflicts:
        errors.extend(f"completion attempts to overwrite resolved field: {name}" for name in conflicts)
        return MergeResult("CONFLICT", merged, errors, unexpected_fields=unexpected)
    if unexpected:
        errors.extend(f"unexpected completion field: {name}" for name in unexpected)
        return MergeResult("INVALID_COMPLETION", merged, errors, unexpected_fields=unexpected)
    for name, value in flat.items():
        error = _validate_value(name, value)
        if error:
            errors.append(error)
    missing = sorted(name for name in requested if name not in flat)
    if errors:
        return MergeResult("INVALID_COMPLETION", merged, errors)
    if missing:
        return MergeResult("INCOMPLETE", merged, [f"missing completion field: {name}" for name in missing])
    for name, value in flat.items():
        _set_draft_value(merged, name, value)
    required_missing = [
        f"rubric_scores.{name}" for name in _RUBRIC_FIELDS if _draft_value(merged, f"rubric_scores.{name}") is None
    ]
    required_missing.extend(
        f"rationales.{name}" for name in _RUBRIC_FIELDS if _draft_value(merged, f"rationales.{name}") is None
    )
    required_missing.extend(name for name in ("prerequisites_acceptable", "edit_effort", "special_question") if _draft_value(merged, name) is None)
    if required_missing:
        return MergeResult("INCOMPLETE", merged, [f"canonical field missing: {name}" for name in required_missing])
    if packet is not None:
        try:
            validate_id03c_submission(packet, merged)
        except ValueError as exc:
            return MergeResult("INCOMPLETE", merged, [str(exc)])
    return MergeResult("CANONICAL_VALID", merged, completed_fields=sorted(flat))
