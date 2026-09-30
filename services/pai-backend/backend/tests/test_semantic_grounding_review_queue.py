from app.extraction.review_queue import build_semantic_grounding_review_queue


def test_queue_is_deterministic_and_keeps_semantic_labels_reviewer_owned() -> None:
    corpus = {
        "instrumented_claims": [
            {
                "document_id": "doc-1",
                "job_id": "job-1",
                "chunk_id": "2",
                "field_name": "experience",
                "claim_value": "Built APIs",
                "locator_status": "unresolved",
                "failure_class": "AMBIGUOUS",
                "raw_match_count": 2,
                "canonical_match_count": 2,
                "diagnostic_matches": {
                    "whitespace": {"matched": True, "match_count": 2},
                    "unicode": {"matched": False, "match_count": 0},
                    "punctuation": {"matched": False, "match_count": 0},
                },
                "provider_input_text_hash": "same",
                "locator_source_text_hash": "same",
            }
        ]
    }
    manifest = [{"job_id": "job-1", "domain": "IT_test"}]

    first = build_semantic_grounding_review_queue(corpus, manifest)
    second = build_semantic_grounding_review_queue(corpus, manifest)

    assert first == second
    item = first["items"][0]
    assert item["domain"] == "IT_test"
    assert item["review_label"] == "AMBIGUOUS_SOURCE"
    assert item["reviewer_note"] is None
    assert "model_source_excerpt" not in item
