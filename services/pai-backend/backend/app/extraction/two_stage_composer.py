"""Deterministic adapter from experimental facts to the V2 extraction contract."""

from app.extraction.capability_discovery import CanonicalizedCapability
from app.extraction.capability_taxonomy import (
    TaxonomySelection,
    get_taxonomy,
    merge_taxonomy_selections,
    validate_taxonomy_selection,
)
from app.extraction.schemas import (
    CapabilityEvidence,
    CapabilityItem,
    CVFullExtractionOutputV2,
    EducationItem,
    EvidenceStrength,
    ExperienceItem,
    NativePdfLocator,
    ToolPlatformItem,
)
from app.extraction.two_stage_capability_schema import ExperimentalCvFacts


def _strength(texts: list[str], experience_count: int) -> EvidenceStrength:
    lowered = " ".join(texts).casefold()
    if experience_count >= 2:
        return EvidenceStrength.MULTIPLE_SUPPORTING_EXPERIENCES
    if any(word in lowered for word in ("reduced", "increased", "improved", "grew", "saved")):
        return EvidenceStrength.DEMONSTRATED_WITH_OUTCOME
    return EvidenceStrength.DEMONSTRATED_IN_ROLE


def _evidence(statement_id: str, facts: ExperimentalCvFacts, page_count: int) -> CapabilityEvidence:
    statements = {
        statement.statement_id: statement
        for experience in facts.experiences
        for statement in experience.statements
    }
    statement = statements.get(statement_id)
    if statement is None:
        raise ValueError(f"unknown_statement_ref:{statement_id}")
    if statement.document_id != facts.document_id:
        raise ValueError("document_id_mismatch")
    if statement.page_number > page_count:
        raise ValueError("page_out_of_range")
    return CapabilityEvidence(
        source_excerpt=statement.text,
        source_locator=NativePdfLocator(
            document_id=statement.document_id,
            page_number=statement.page_number,
        ),
        evidence_strength=EvidenceStrength.DEMONSTRATED_IN_ROLE,
        confidence=0.0,
    )


def compose_two_stage_output(
    facts: ExperimentalCvFacts,
    selection: TaxonomySelection,
    *,
    page_count: int,
) -> CVFullExtractionOutputV2:
    validate_taxonomy_selection(selection, facts)
    selection = merge_taxonomy_selections(selection)
    taxonomy = get_taxonomy(selection.taxonomy_id, selection.taxonomy_version)
    definitions = {item.id: item for item in taxonomy.capabilities}
    statement_to_experience = {
        statement.statement_id: experience.experience_id
        for experience in facts.experiences
        for statement in experience.statements
    }
    capabilities: list[CapabilityItem] = []
    for selected in selection.capabilities:
        definition = definitions[selected.capability_id]
        evidence = [
            _evidence(statement_id, facts, page_count)
            for statement_id in selected.supporting_statement_ids
        ]
        experience_refs = list(
            dict.fromkeys(statement_to_experience[ref] for ref in selected.supporting_statement_ids)
        )
        capabilities.append(
            CapabilityItem(
                raw_name=definition.name,
                canonical_name=definition.name,
                category=definition.category,
                evidence=[
                    item.model_copy(
                        update={
                            "evidence_strength": _strength(
                                [entry.source_excerpt for entry in evidence],
                                len(experience_refs),
                            )
                        }
                    )
                    for item in evidence
                ],
                supporting_experience_refs=experience_refs,
                evidence_strength=_strength(
                    [item.source_excerpt for item in evidence], len(experience_refs)
                ),
            )
        )

    experiences = [
        ExperienceItem(
            title=item.role,
            company=item.organization,
            responsibilities=[statement.text for statement in item.statements],
            evidence=[_evidence(statement.statement_id, facts, page_count) for statement in item.statements],
        )
        for item in facts.experiences
    ]
    tools = [
        ToolPlatformItem(
            name=item.name,
            evidence=[_evidence(ref, facts, page_count) for ref in item.supporting_statement_ids],
        )
        for item in facts.tools_platforms
    ]
    return CVFullExtractionOutputV2(
        experience=experiences,
        capabilities=capabilities,
        tools_platforms=tools,
        education=[EducationItem(degree=item.degree, field=item.field, institution=item.institution, year=item.year) for item in facts.education],
    )


def compose_discovered_output(
    facts: ExperimentalCvFacts,
    capabilities: list[CanonicalizedCapability],
    *,
    page_count: int,
) -> CVFullExtractionOutputV2:
    taxonomy = get_taxonomy("professional_capability_core", "0.1")
    definitions = {item.id: item for item in taxonomy.capabilities}
    statement_to_experience = {
        statement.statement_id: experience.experience_id
        for experience in facts.experiences
        for statement in experience.statements
    }
    composed: list[CapabilityItem] = []
    for item in capabilities:
        evidence = [
            _evidence(statement_id, facts, page_count)
            for statement_id in item.supporting_statement_ids
        ]
        experience_refs = list(
            dict.fromkeys(statement_to_experience[ref] for ref in item.supporting_statement_ids)
        )
        strength = _strength([entry.source_excerpt for entry in evidence], len(experience_refs))
        definition = definitions.get(item.canonical_capability_id or "")
        composed.append(
            CapabilityItem(
                raw_name=item.raw_name,
                canonical_name=item.canonical_name or item.raw_name,
                category=definition.category if definition is not None else None,
                evidence=[entry.model_copy(update={"evidence_strength": strength}) for entry in evidence],
                supporting_experience_refs=experience_refs,
                evidence_strength=strength,
                mapping_status=item.status,
            )
        )
    base = compose_two_stage_output(
        facts,
        TaxonomySelection(taxonomy_id="professional_capability_core", taxonomy_version="0.1"),
        page_count=page_count,
    )
    return base.model_copy(update={"capabilities": composed})
