import unicodedata
from dataclasses import dataclass

from app.extraction.chunking import TextChunk
from app.extraction.entity_normalization import normalize_entity
from app.extraction.evidence import (
    EvidenceContext,
    EvidenceEntity,
    EvidenceExtractionOutput,
    EvidenceItem,
)
from app.extraction.fixtures import FixtureDocument
from app.extraction.locator_forensics import collect_locator_forensics
from app.extraction.normalization import normalization_key
from app.extraction.schemas import (
    CVChunkExtractionOutput,
    CVExtractionOutput,
    CVFullExtractionOutput,
    EvidenceReference,
    EvidenceStatus,
    EvidenceType,
    ExtractedClaim,
    JDChunkExtractionOutput,
    JDExtractionOutput,
    JDFullExtractionOutput,
    SourceLocator,
)

ChunkExtractionOutput = CVChunkExtractionOutput | JDChunkExtractionOutput
FinalExtractionOutput = CVExtractionOutput | JDExtractionOutput
FullExtractionOutput = CVFullExtractionOutput | JDFullExtractionOutput


class ChunkLocatorError(ValueError):
    def __init__(self, chunk_ordinal: int, message: str) -> None:
        self.chunk_ordinal = chunk_ordinal
        super().__init__(message)


_EVIDENCE_PRIORITY = {
    EvidenceContext.OWNED_SYSTEM: 7,
    EvidenceContext.USED_IN_PRODUCTION: 6,
    EvidenceContext.USED_IN_PROJECT: 5,
    EvidenceContext.USED_IN_RESEARCH: 4,
    EvidenceContext.STUDIED: 3,
    EvidenceContext.MENTIONED: 2,
    EvidenceContext.LED_TEAM: 7,
}


def merge_evidence_outputs(outputs: list[EvidenceExtractionOutput]) -> EvidenceExtractionOutput:
    """Merge entity evidence by canonical identity without losing contexts."""
    grouped: dict[tuple[str, str], EvidenceEntity] = {}
    for output in outputs:
        for entity in output.entities:
            normalized = normalize_entity(entity.name)
            key = (entity.entity_type.casefold(), normalized.normalization_key)
            current = grouped.get(key)
            if current is None:
                grouped[key] = entity.model_copy(
                    update={
                        "name": normalized.canonical_value,
                        "original_value": entity.original_value or entity.name,
                        "canonical_value": normalized.canonical_value,
                        "evidence": list(entity.evidence),
                    }
                )
                continue
            evidence = list(current.evidence)
            for candidate in entity.evidence:
                _merge_evidence_item(evidence, candidate)
            grouped[key] = current.model_copy(update={"evidence": evidence})
    return EvidenceExtractionOutput(entities=list(grouped.values()))


def _merge_evidence_item(evidence: list[EvidenceItem], candidate: EvidenceItem) -> None:
    for index, existing in enumerate(evidence):
        if (
            existing.context is candidate.context
            and existing.source_excerpt == candidate.source_excerpt
        ):
            if _entity_evidence_strength(candidate) > _entity_evidence_strength(existing):
                evidence[index] = candidate
            return
    evidence.append(candidate)
    evidence.sort(key=_entity_evidence_strength, reverse=True)


def _entity_evidence_strength(item: EvidenceItem) -> tuple[int, float]:
    return (_EVIDENCE_PRIORITY[item.context], item.confidence)


def locate_candidate(chunk: TextChunk, document: FixtureDocument, excerpt: str) -> SourceLocator:
    locator, _ = _resolve_candidate(chunk, document, excerpt)
    return locator


def _resolve_candidate(
    chunk: TextChunk, document: FixtureDocument, excerpt: str
) -> tuple[SourceLocator, str]:
    normalized_text = _normalized_locator_text(chunk.text)
    normalized_excerpt = _normalize_locator_excerpt(excerpt)
    occurrences = _find_occurrences(normalized_text.value, normalized_excerpt)
    if len(occurrences) > 1:
        raise ChunkLocatorError(chunk.ordinal, "source excerpt must appear exactly once in chunk")
    if not occurrences or not normalized_excerpt:
        raise ChunkLocatorError(chunk.ordinal, "source excerpt must appear exactly once in chunk")
    normalized_start = occurrences[0]
    normalized_end = normalized_start + len(normalized_excerpt)
    local_start = normalized_text.starts[normalized_start]
    local_end = normalized_text.ends[normalized_end - 1]
    canonical_excerpt = chunk.text[local_start:local_end]
    start_offset = chunk.start_offset + local_start
    end_offset = start_offset + len(canonical_excerpt)
    if document.content[start_offset:end_offset] != canonical_excerpt:
        raise ChunkLocatorError(chunk.ordinal, "source excerpt does not map to document content")
    return (
        SourceLocator(
            document_id=document.document_id,
            section=_section_for(document.content, start_offset),
            start_offset=start_offset,
            end_offset=end_offset,
        ),
        canonical_excerpt,
    )


def merge_chunk_outputs(
    document: FixtureDocument,
    chunks: list[TextChunk],
    outputs: list[ChunkExtractionOutput],
    *,
    forensics_records: list[dict[str, object]] | None = None,
    provider_input_text_by_ordinal: dict[int, str] | None = None,
) -> FinalExtractionOutput:
    if len(chunks) != len(outputs):
        raise ValueError("chunks and outputs must have the same length")
    if not outputs:
        raise ValueError("at least one chunk output is required")

    output_type = type(outputs[0])
    if any(type(output) is not output_type for output in outputs):
        raise ValueError("all chunk outputs must use the same schema")

    merged_fields: dict[str, list[ExtractedClaim]] = {
        field_name: [] for field_name in _field_names_for_output(output_type)
    }
    seen_other: set[tuple[str, EvidenceStatus, EvidenceType, str | None]] = set()

    for chunk, output in zip(chunks, outputs, strict=True):
        for field_name in merged_fields:
            for claim in getattr(output, field_name):
                contextual_evidence_type = _evidence_type_for_bucket(
                    field_name, claim.evidence_type
                )
                if claim.evidence_status is EvidenceStatus.SUPPORTED:
                    forensic_record: dict[str, object] | None = None
                    if forensics_records is not None:
                        forensic_record = collect_locator_forensics(
                            chunk,
                            document,
                            claim.source_excerpt or "",
                            provider_input_text=(
                                provider_input_text_by_ordinal or {}
                            ).get(chunk.ordinal, chunk.text),
                        )
                        forensic_record["field_name"] = field_name
                        forensic_record["claim_value"] = claim.value
                        forensics_records.append(forensic_record)
                    try:
                        locator, canonical_excerpt = _resolve_candidate(
                            chunk, document, claim.source_excerpt or ""
                        )
                    except ChunkLocatorError:
                        unresolved_key = (
                            field_name,
                            EvidenceStatus.INSUFFICIENT,
                            contextual_evidence_type,
                            claim.value,
                        )
                        if unresolved_key not in seen_other:
                            seen_other.add(unresolved_key)
                            merged_fields[field_name].append(
                                ExtractedClaim(
                                    value=None,
                                    evidence_type=contextual_evidence_type,
                                    confidence=claim.confidence,
                                    evidence_status=EvidenceStatus.INSUFFICIENT,
                                    unresolved_reason="locator_unresolved",
                                )
                            )
                        continue
                    if forensic_record is not None:
                        forensic_record["locator_status"] = "resolved"
                        forensic_record["failure_class"] = None
                    normalized_value = _normalize_value(claim.value or "")
                    _merge_supported_claim(
                        merged_fields[field_name],
                        normalized_value,
                        claim.value,
                        contextual_evidence_type,
                        claim.confidence,
                        locator,
                        canonical_excerpt,
                    )
                else:
                    dedupe_key = (
                        field_name,
                        claim.evidence_status,
                        contextual_evidence_type,
                        claim.value,
                    )
                    if dedupe_key in seen_other:
                        continue
                    seen_other.add(dedupe_key)
                    merged_fields[field_name].append(
                        ExtractedClaim(
                            value=None,
                            evidence_type=contextual_evidence_type,
                            confidence=claim.confidence,
                            evidence_status=claim.evidence_status,
                        )
                    )

    if output_type is CVChunkExtractionOutput:
        return CVExtractionOutput(**merged_fields)
    if output_type is JDChunkExtractionOutput:
        return JDExtractionOutput(**merged_fields)
    raise ValueError("Unsupported chunk output schema")


def map_full_document_output(
    document: FixtureDocument, output: FullExtractionOutput
) -> FinalExtractionOutput:
    """Map full-document evidence to deterministic document-level locators."""
    if isinstance(output, CVFullExtractionOutput):
        field_names = ("skills", "experience", "education")
    elif isinstance(output, JDFullExtractionOutput):
        field_names = ("required_skills", "responsibilities", "qualifications")
    else:
        raise ValueError("Unsupported full-document output schema")

    mapped_fields: dict[str, list[ExtractedClaim]] = {name: [] for name in field_names}
    seen_unresolved: set[tuple[str, EvidenceStatus, EvidenceType, str | None]] = set()
    for field_name in field_names:
        for claim in getattr(output, field_name):
            evidence_type = _evidence_type_for_bucket(field_name, claim.evidence_type)
            if claim.evidence_status != "supported":
                status = EvidenceStatus(claim.evidence_status)
                key = (field_name, status, evidence_type, claim.value)
                if key not in seen_unresolved:
                    seen_unresolved.add(key)
                    mapped_fields[field_name].append(
                        ExtractedClaim(
                            value=None,
                            evidence_type=evidence_type,
                            confidence=claim.confidence,
                            evidence_status=status,
                        )
                    )
                continue

            try:
                locator, canonical_excerpt = locate_document_excerpt(
                    document, claim.source_excerpt or ""
                )
            except ValueError:
                key = (field_name, EvidenceStatus.INSUFFICIENT, evidence_type, claim.value)
                if key not in seen_unresolved:
                    seen_unresolved.add(key)
                    mapped_fields[field_name].append(
                        ExtractedClaim(
                            value=None,
                            evidence_type=evidence_type,
                            confidence=claim.confidence,
                            evidence_status=EvidenceStatus.INSUFFICIENT,
                            unresolved_reason="locator_unresolved",
                        )
                    )
                continue

            _merge_supported_claim(
                mapped_fields[field_name],
                _normalize_value(claim.value or ""),
                claim.value,
                evidence_type,
                claim.confidence,
                locator,
                canonical_excerpt,
            )

    if isinstance(output, CVFullExtractionOutput):
        return CVExtractionOutput(**mapped_fields)
    return JDExtractionOutput(**mapped_fields)


def locate_document_excerpt(
    document: FixtureDocument, excerpt: str
) -> tuple[SourceLocator, str]:
    normalized_text = _normalized_locator_text(document.content)
    normalized_excerpt = _normalize_locator_excerpt(excerpt)
    occurrences = _find_occurrences(normalized_text.value, normalized_excerpt)
    if len(occurrences) != 1 or not normalized_excerpt:
        raise ValueError("source excerpt must appear exactly once in document")

    normalized_start = occurrences[0]
    normalized_end = normalized_start + len(normalized_excerpt)
    local_start = normalized_text.starts[normalized_start]
    local_end = normalized_text.ends[normalized_end - 1]
    canonical_excerpt = document.content[local_start:local_end]
    return (
        SourceLocator(
            document_id=document.document_id,
            section=_section_for(document.content, local_start),
            start_offset=local_start,
            end_offset=local_start + len(canonical_excerpt),
        ),
        canonical_excerpt,
    )


def _field_names_for_output(output_type: type[ChunkExtractionOutput]) -> tuple[str, str, str]:
    if output_type is CVChunkExtractionOutput:
        return ("skills", "experience", "education")
    if output_type is JDChunkExtractionOutput:
        return ("required_skills", "responsibilities", "qualifications")
    raise ValueError("Unsupported chunk output schema")


def _evidence_type_for_bucket(field_name: str, evidence_type: EvidenceType) -> EvidenceType:
    """Apply only structural source-context corrections available in v1.1 buckets."""
    if field_name == "experience" and evidence_type is EvidenceType.EXPLICIT_SKILL:
        return EvidenceType.WORK_EXPERIENCE
    if field_name == "education" and evidence_type in {
        EvidenceType.EXPLICIT_SKILL,
        EvidenceType.WORK_EXPERIENCE,
        EvidenceType.PROJECT_USAGE,
    }:
        return EvidenceType.EDUCATION
    return evidence_type


def _merge_supported_claim(
    claims: list[ExtractedClaim],
    normalized_value: str,
    value: str | None,
    evidence_type: EvidenceType,
    confidence: float,
    locator: SourceLocator,
    source_excerpt: str,
) -> None:
    reference = EvidenceReference(
        evidence_type=evidence_type,
        confidence=confidence,
        source_locator=locator,
        source_excerpt=source_excerpt,
    )
    existing_index = next(
        (
            index
            for index, existing in enumerate(claims)
            if _normalize_value(existing.value or "") == normalized_value
        ),
        None,
    )
    if existing_index is None:
        claims.append(
            ExtractedClaim(
                value=value,
                evidence_type=evidence_type,
                confidence=confidence,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_locator=locator,
                source_excerpt=source_excerpt,
                evidence=[reference],
            )
        )
        return

    existing = claims[existing_index]
    references = list(existing.evidence)
    same_type_index = next(
        (index for index, item in enumerate(references) if item.evidence_type is evidence_type),
        None,
    )
    if same_type_index is None:
        references.append(reference)
    elif confidence > references[same_type_index].confidence:
        references[same_type_index] = reference

    primary = max(references, key=_evidence_strength)
    claims[existing_index] = existing.model_copy(
        update={
            "evidence_type": primary.evidence_type,
            "confidence": primary.confidence,
            "source_locator": primary.source_locator,
            "source_excerpt": primary.source_excerpt,
            "evidence": references,
        }
    )


def _evidence_strength(reference: EvidenceReference) -> tuple[float, int]:
    priorities = {
        EvidenceType.EXPLICIT_SKILL: 6,
        EvidenceType.WORK_EXPERIENCE: 5,
        EvidenceType.PROJECT_USAGE: 4,
        EvidenceType.CERTIFICATION: 3,
        EvidenceType.EDUCATION: 3,
        EvidenceType.PUBLICATION: 2,
        EvidenceType.UNKNOWN: 0,
    }
    return reference.confidence, priorities[reference.evidence_type]


def _find_occurrences(text: str, excerpt: str) -> list[int]:
    if not excerpt:
        return []
    occurrences: list[int] = []
    start = 0
    while True:
        index = text.find(excerpt, start)
        if index == -1:
            break
        occurrences.append(index)
        start = index + 1
    return occurrences


@dataclass(frozen=True, slots=True)
class _NormalizedLocatorText:
    value: str
    starts: tuple[int, ...]
    ends: tuple[int, ...]


def _normalized_locator_text(text: str) -> _NormalizedLocatorText:
    """Normalize only formatting while retaining a map to original offsets."""
    normalized_chars: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    cluster: list[str] = []
    cluster_start = 0

    def flush_cluster() -> None:
        if not cluster:
            return
        normalized = unicodedata.normalize("NFKC", "".join(cluster))
        for character in normalized:
            normalized_chars.append(character)
            starts.append(cluster_start)
            ends.append(cluster_start + len(cluster))
        cluster.clear()

    for index, character in enumerate(text):
        if cluster and unicodedata.combining(character):
            cluster.append(character)
            continue
        flush_cluster()
        cluster_start = index
        cluster.append(character)
    flush_cluster()

    collapsed_chars: list[str] = []
    collapsed_starts: list[int] = []
    collapsed_ends: list[int] = []
    for character, start, end in zip(normalized_chars, starts, ends, strict=True):
        if character == "\u00a0" or character.isspace():
            if collapsed_chars and collapsed_chars[-1] == " ":
                collapsed_ends[-1] = end
            else:
                collapsed_chars.append(" ")
                collapsed_starts.append(start)
                collapsed_ends.append(end)
            continue
        collapsed_chars.append(character)
        collapsed_starts.append(start)
        collapsed_ends.append(end)
    return _NormalizedLocatorText(
        value="".join(collapsed_chars),
        starts=tuple(collapsed_starts),
        ends=tuple(collapsed_ends),
    )


def _normalize_locator_excerpt(excerpt: str) -> str:
    return _normalized_locator_text(excerpt).value.strip()


def _normalize_value(value: str) -> str:
    return normalization_key(value)


def _section_for(content: str, start_offset: int) -> str:
    preceding = content[:start_offset]
    section = preceding.rsplit("\n", maxsplit=1)[-1].split(":", maxsplit=1)[0].strip().lower()
    return section or "profile"
