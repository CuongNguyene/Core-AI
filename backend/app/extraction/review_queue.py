"""Deterministic human-review queue for unresolved locator claims."""

import hashlib
from collections.abc import Sequence


def build_semantic_grounding_review_queue(
    corpus: dict[str, object], manifest: Sequence[dict[str, object]]
) -> dict[str, object]:
    domain_by_job = {str(item.get("job_id")): item.get("domain") for item in manifest}
    items: list[dict[str, object]] = []
    records = corpus.get("instrumented_claims", [])
    if not isinstance(records, list):
        records = []
    for record in records:
        if not isinstance(record, dict) or record.get("locator_status") != "unresolved":
            continue
        job_id = str(record.get("job_id", ""))
        key = "|".join(
            str(record.get(name, ""))
            for name in ("document_id", "job_id", "chunk_id", "field_name", "claim_value")
        )
        review_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        diagnostic_matches = record.get("diagnostic_matches", {})
        if not isinstance(diagnostic_matches, dict):
            diagnostic_matches = {}
        review_label = (
            "AMBIGUOUS_SOURCE"
            if record.get("failure_class") == "AMBIGUOUS"
            else None
        )
        items.append(
            {
                "review_id": review_id,
                "domain": domain_by_job.get(job_id),
                "document_id": record.get("document_id"),
                "job_id": record.get("job_id"),
                "chunk_id": record.get("chunk_id"),
                "field_name": record.get("field_name"),
                "claim_value": record.get("claim_value"),
                "locator_status": "unresolved",
                "current_failure_class": record.get("failure_class"),
                "raw_match_count": record.get("raw_match_count"),
                "canonical_match_count": record.get("canonical_match_count"),
                "diagnostic_matches": {
                    name: bool(
                        isinstance(diagnostic_matches.get(name), dict)
                        and diagnostic_matches[name].get("matched")
                    )
                    for name in ("whitespace", "unicode", "punctuation")
                },
                "provider_input_matches_locator_source": (
                    record.get("provider_input_text_hash")
                    == record.get("locator_source_text_hash")
                ),
                "debug_artifact_ref": f"debug/{job_id}.json",
                "review_label": review_label,
                "reviewer_note": None,
            }
        )
    items.sort(key=lambda item: str(item["review_id"]))
    return {
        "schema_version": "semantic_grounding_review_queue@1",
        "review_state": "pending_reviewer",
        "allowed_review_labels": [
            "G_PARAPHRASED_SOURCE",
            "H_UNSUPPORTED_SOURCE",
            "SOURCE_RELATION_UNCLEAR",
            "AMBIGUOUS_SOURCE",
            "FORMAT_ONLY",
        ],
        "items": items,
    }
