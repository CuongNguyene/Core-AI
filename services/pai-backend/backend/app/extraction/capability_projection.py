"""Deterministic V2 capability aggregation and legacy compatibility adapters."""

import re
from collections.abc import Callable, Iterable
from typing import Any

from app.extraction.jd_requirement_validation import resolve_exact_source_excerpt
from app.extraction.locators import SourceLocator
from app.extraction.profile import CandidateProfile
from app.extraction.profile_builder import build_candidate_profile_from_output
from app.extraction.schemas import (
    CapabilityEvidence,
    CapabilityItem,
    CVExtractionOutput,
    CVFullExtractionOutputV2,
    EducationItem,
    EvidenceReference,
    EvidenceStatus,
    EvidenceStrength,
    EvidenceType,
    ExperienceItem,
    ExtractedClaim,
    NativePdfLocator,
    ToolPlatformItem,
)

_ALIASES = {
    "project development management": "Project Management",
    "project delivery management": "Project Management",
    "project management": "Project Management",
    "omni channel": "Omnichannel Commerce",
    "omni-channel": "Omnichannel Commerce",
    "omnichannel": "Omnichannel Commerce",
    "o2o commerce": "Omnichannel Commerce",
}


def aggregate_capabilities(items: Iterable[CapabilityItem]) -> list[CapabilityItem]:
    grouped: dict[str, CapabilityItem] = {}
    for item in items:
        canonical_name = _bounded_canonical_name(item.raw_name, item.canonical_name)
        existing = grouped.get(canonical_name)
        if existing is None:
            grouped[canonical_name] = item.model_copy(update={"canonical_name": canonical_name})
            continue
        evidence = list(existing.evidence)
        for candidate in item.evidence:
            if not any(
                current.source_locator == candidate.source_locator
                and current.source_excerpt == candidate.source_excerpt
                for current in evidence
            ):
                evidence.append(candidate)
        refs = list(dict.fromkeys(existing.supporting_experience_refs + item.supporting_experience_refs))
        updated = existing.model_copy(
            update={
                "canonical_name": canonical_name,
                "evidence": evidence,
                "supporting_experience_refs": refs,
            }
        )
        grouped[canonical_name] = updated

    result: list[CapabilityItem] = []
    for item in grouped.values():
        distinct_ref_count = len(set(item.supporting_experience_refs))
        if distinct_ref_count >= 2:
            item = item.model_copy(
                update={"evidence_strength": EvidenceStrength.MULTIPLE_SUPPORTING_EXPERIENCES}
            )
        result.append(item)
    return result


def project_v2_to_legacy(
    output: CVFullExtractionOutputV2, parsed_document: str | None = None
) -> CVExtractionOutput:
    capabilities = aggregate_capabilities(output.capabilities)
    return CVExtractionOutput(
        skills=[
            *[
                claim
                for item in capabilities
                if (claim := _try_project(_capability_claim, item, parsed_document)) is not None
            ],
            *[
                claim
                for item in output.tools_platforms
                if (claim := _try_project(_tool_claim, item, parsed_document)) is not None
            ],
        ],
        experience=[
            claim
            for item in output.experience
            if item.evidence
            if (claim := _try_project(_experience_claim, item, parsed_document)) is not None
        ],
        education=[
            claim
            for item in output.education
            if item.evidence
            if (claim := _try_project(_education_claim, item, parsed_document)) is not None
        ],
    )


def project_v2_to_candidate_profile(
    output: CVFullExtractionOutputV2, parsed_document: str | None = None
) -> CandidateProfile:
    return build_candidate_profile_from_output(project_v2_to_legacy(output, parsed_document))


def bind_v2_document_evidence(
    output: CVFullExtractionOutputV2, *, document_id: str, document: str
) -> CVFullExtractionOutputV2:
    """Resolve provider evidence against backend-owned CV text before validation."""

    def bind_evidence(evidence: CapabilityEvidence) -> CapabilityEvidence:
        locator = evidence.source_locator
        if isinstance(locator, NativePdfLocator):
            return evidence.model_copy(
                update={"source_locator": locator.model_copy(update={"document_id": document_id})}
            )
        resolved = resolve_exact_source_excerpt(document, evidence.source_excerpt)
        return evidence.model_copy(
            update={
                "source_locator": SourceLocator(
                    document_id=document_id,
                    section=locator.section or "document",
                    start_offset=resolved.start_offset,
                    end_offset=resolved.end_offset,
                ),
                "source_excerpt": document[resolved.start_offset : resolved.end_offset],
            }
        )

    return output.model_copy(
        update={
            "capabilities": [
                item.model_copy(update={"evidence": [bind_evidence(e) for e in item.evidence]})
                for item in output.capabilities
            ],
            "tools_platforms": [
                item.model_copy(update={"evidence": [bind_evidence(e) for e in item.evidence]})
                for item in output.tools_platforms
            ],
            "experience": [
                item.model_copy(update={"evidence": [bind_evidence(e) for e in item.evidence]})
                for item in output.experience
            ],
            "education": [
                item.model_copy(update={"evidence": [bind_evidence(e) for e in item.evidence]})
                for item in output.education
            ],
        }
    )


def validate_v2_document_evidence(
    output: CVFullExtractionOutputV2,
    document: str,
    *,
    input_mode: object | None = None,
    page_count: int | None = None,
    expected_document_id: str | None = None,
) -> None:
    """Fail closed when a model locator/excerpt is not grounded in the document."""
    for item in _iter_v2_evidence(output):
        locator = item.source_locator
        if (
            isinstance(locator, NativePdfLocator)
            and expected_document_id is not None
            and locator.document_id != expected_document_id
        ):
            raise ValueError("locator_document_id_mismatch")
        if isinstance(locator, NativePdfLocator):
            if page_count is not None and locator.page_number > page_count:
                raise ValueError("native_pdf_invalid_page")
            continue
        locator_text = document[locator.start_offset : locator.end_offset]
        if locator_text != item.source_excerpt:
            raise ValueError("V2 evidence locator does not resolve to the exact source excerpt")


def _iter_v2_evidence(output: CVFullExtractionOutputV2) -> Iterable[CapabilityEvidence]:
    for capability in output.capabilities:
        yield from capability.evidence
    for tool in output.tools_platforms:
        yield from tool.evidence
    for experience in output.experience:
        yield from experience.evidence
    for education in output.education:
        yield from education.evidence


def _bounded_canonical_name(raw_name: str, proposed: str) -> str:
    for candidate in (raw_name, proposed):
        key = re.sub(r"\s+", " ", candidate.strip().casefold())
        if key in _ALIASES:
            return _ALIASES[key]
    return proposed.strip()


def _resolve_legacy_locator(
    evidence: CapabilityEvidence, parsed_document: str | None
) -> SourceLocator:
    locator = evidence.source_locator
    if isinstance(locator, SourceLocator):
        return locator
    if parsed_document is None:
        raise ValueError("native evidence cannot be projected without parsed document support")
    start = parsed_document.find(evidence.source_excerpt)
    if start < 0:
        raise ValueError("native evidence excerpt cannot resolve to parsed document")
    return SourceLocator(
        document_id=locator.document_id,
        section=locator.section or f"page-{locator.page_number}",
        start_offset=start,
        end_offset=start + len(evidence.source_excerpt),
    )


def _try_project(
    function: Callable[[Any, str | None], ExtractedClaim],
    item: Any,
    parsed_document: str | None,
) -> ExtractedClaim | None:
    try:
        return function(item, parsed_document)
    except ValueError:
        return None


def _capability_claim(
    item: CapabilityItem, parsed_document: str | None = None
) -> ExtractedClaim:
    first = item.evidence[0]
    references = [
        EvidenceReference(
            evidence_type=EvidenceType.EXPLICIT_SKILL,
            confidence=evidence.confidence,
            source_locator=_resolve_legacy_locator(evidence, parsed_document),
            source_excerpt=evidence.source_excerpt,
        )
        for evidence in item.evidence
    ]
    return ExtractedClaim(
        value=item.canonical_name,
        evidence_type=EvidenceType.EXPLICIT_SKILL,
        confidence=max(evidence.confidence for evidence in item.evidence),
        evidence_status=EvidenceStatus.SUPPORTED,
        source_locator=_resolve_legacy_locator(first, parsed_document),
        source_excerpt=first.source_excerpt,
        evidence=references,
    )


def _experience_claim(
    item: ExperienceItem, parsed_document: str | None = None
) -> ExtractedClaim:
    first = item.evidence[0]
    return ExtractedClaim(
        value=item.title,
        evidence_type=EvidenceType.WORK_EXPERIENCE,
        confidence=max(evidence.confidence for evidence in item.evidence),
        evidence_status=EvidenceStatus.SUPPORTED,
        source_locator=_resolve_legacy_locator(first, parsed_document),
        source_excerpt=first.source_excerpt,
    )


def _tool_claim(item: ToolPlatformItem, parsed_document: str | None = None) -> ExtractedClaim:
    first = item.evidence[0]
    return ExtractedClaim(
        value=item.name,
        evidence_type=EvidenceType.EXPLICIT_SKILL,
        confidence=max(evidence.confidence for evidence in item.evidence),
        evidence_status=EvidenceStatus.SUPPORTED,
        source_locator=_resolve_legacy_locator(first, parsed_document),
        source_excerpt=first.source_excerpt,
        evidence=[
            EvidenceReference(
                evidence_type=EvidenceType.EXPLICIT_SKILL,
                confidence=evidence.confidence,
                source_locator=_resolve_legacy_locator(evidence, parsed_document),
                source_excerpt=evidence.source_excerpt,
            )
            for evidence in item.evidence
        ],
    )


def _education_claim(
    item: EducationItem, parsed_document: str | None = None
) -> ExtractedClaim:
    first = item.evidence[0]
    value = " — ".join(part for part in (item.degree, item.field, item.institution) if part)
    return ExtractedClaim(
        value=value,
        evidence_type=EvidenceType.EDUCATION,
        confidence=max(evidence.confidence for evidence in item.evidence),
        evidence_status=EvidenceStatus.SUPPORTED,
        source_locator=_resolve_legacy_locator(first, parsed_document),
        source_excerpt=first.source_excerpt,
    )
