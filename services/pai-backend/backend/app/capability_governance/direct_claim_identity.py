"""Stable, bounded identities for direct course capability claims."""

from __future__ import annotations

import hashlib
import json


def make_direct_claim_source_id(*, course_ref: str, claim_id: str) -> str:
    """Hash a structured course/claim pair without normalizing either value."""
    if not isinstance(course_ref, str) or not course_ref.strip():
        raise ValueError("course_ref_required")
    if not isinstance(claim_id, str) or not claim_id.strip():
        raise ValueError("claim_id_required")

    canonical = json.dumps(
        {"claim_id": claim_id, "course_ref": course_ref},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"dc1_{hashlib.sha256(canonical).hexdigest()}"
