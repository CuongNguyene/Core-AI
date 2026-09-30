from collections.abc import Iterable

from app.extraction.graph_merge import merge_relation_evidence
from app.extraction.profile import CandidateProfile, RelationExtractionOutput
from app.extraction.router import ExtractionMode, choose_extraction_mode


def build_candidate_profile(
    text: str,
    full_document: RelationExtractionOutput,
    section_outputs: Iterable[RelationExtractionOutput] = (),
    threshold: int = 12_000,
) -> CandidateProfile:
    """Build a candidate graph after hybrid model calls have completed.

    The full-document relation output supplies cross-section context. For large
    documents, section outputs add grounded evidence; for small documents the
    full output is intentionally the only stream. This function performs no
    model calls and is deterministic, making it safe to rerun in a golden
    harness.
    """
    mode = choose_extraction_mode(text, threshold=threshold)
    grounded = list(section_outputs) if mode is ExtractionMode.SECTION_BASED else []
    return merge_relation_evidence(full_document, grounded)
