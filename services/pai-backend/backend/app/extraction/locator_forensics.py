"""Diagnostic-only locator probes.

This module never supplies a locator to production extraction.  It records
deterministic probes so a failed claim can be classified without weakening the
strict resolver or logging raw text in normal audit metadata.
"""

import hashlib
import re
import unicodedata
from typing import Any

from app.extraction.chunking import TextChunk
from app.extraction.fixtures import FixtureDocument


def _occurrences(text: str, needle: str) -> list[int]:
    if not needle:
        return []
    result: list[int] = []
    start = 0
    while True:
        index = text.find(needle, start)
        if index < 0:
            return result
        result.append(index)
        start = index + 1


def _whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00a0", " ")).strip()


def _unicode(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def _punctuation(value: str) -> str:
    return "".join(ch for ch in value if not unicodedata.category(ch).startswith("P"))


def _probe(text: str, excerpt: str, transform: Any) -> dict[str, object]:
    matches = _occurrences(transform(text), transform(excerpt))
    return {"matched": bool(matches), "match_count": len(matches)}


def _classify(
    *, raw_count: int, probes: dict[str, dict[str, object]], representation_matches: bool
) -> str | None:
    if not representation_matches:
        return "WRONG_TEXT_REPRESENTATION"
    if raw_count > 0:
        return None
    if any(_match_count(probe) > 1 for probe in probes.values()):
        return "AMBIGUOUS"
    if _match_count(probes["whitespace"]) == 1:
        return "WHITESPACE"
    if _match_count(probes["unicode"]) == 1:
        return "UNICODE"
    if _match_count(probes["punctuation"]) == 1:
        return "PUNCTUATION"
    return None


def _match_count(probe: dict[str, object]) -> int:
    value = probe.get("match_count")
    return value if isinstance(value, int) else 0


def collect_locator_forensics(
    chunk: TextChunk,
    document: FixtureDocument,
    model_source_excerpt: str,
    *,
    provider_input_text: str,
) -> dict[str, object]:
    """Return a privacy-sensitive debug record for one locator attempt.

    The caller must write this only to an explicitly enabled debug artifact;
    the production audit path should receive neither the excerpt nor chunk
    text. Canonical probes are observations and are not used for resolution.
    """

    raw_count = len(_occurrences(chunk.text, model_source_excerpt))
    probes = {
        "whitespace": _probe(chunk.text, model_source_excerpt, _whitespace),
        "unicode": _probe(chunk.text, model_source_excerpt, _unicode),
        "punctuation": _probe(chunk.text, model_source_excerpt, _punctuation),
    }
    canonical_probe = _probe(
        chunk.text,
        model_source_excerpt,
        lambda value: _whitespace(_unicode(value)),
    )
    provider_hash = hashlib.sha256(provider_input_text.encode("utf-8")).hexdigest()
    source_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
    representation_matches = provider_hash == source_hash
    failure_class = _classify(
        raw_count=raw_count,
        probes=probes,
        representation_matches=representation_matches,
    )
    return {
        "document_id": document.document_id,
        "chunk_id": str(chunk.ordinal),
        "chunk_ordinal": chunk.ordinal,
        "chunk_start_offset": chunk.start_offset,
        "chunk_end_offset": chunk.end_offset,
        "model_source_excerpt": model_source_excerpt,
        "provider_input_text_hash": provider_hash,
        "locator_source_text_hash": source_hash,
        "raw_exact_match": raw_count == 1,
        "raw_match_count": raw_count,
        "canonical_exact_match": bool(canonical_probe["matched"]),
        "canonical_match_count": canonical_probe["match_count"],
        "diagnostic_matches": probes,
        "canonicalization_probe": {
            "whitespace_only": probes["whitespace"]["matched"],
            "unicode_only": probes["unicode"]["matched"],
            "punctuation_only": probes["punctuation"]["matched"],
        },
        "locator_status": "resolved" if raw_count == 1 else "unresolved",
        "failure_class": failure_class,
    }
