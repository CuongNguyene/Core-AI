from app.extraction.evidence import EvidenceContext, RelationClaim, RelationEntityType
from app.extraction.fixtures import FixtureDocument
from app.extraction.profile import RelationExtractionOutput
from app.extraction.relation import EntityRelationOutput, SectionEvidenceOutput
from app.extraction.relation_mapper import map_relation_to_evidence_context
from app.extraction.schemas import SourceLocator


def relation_output_to_graph_input(
    output: EntityRelationOutput,
    document: FixtureDocument,
) -> RelationExtractionOutput:
    claims: list[RelationClaim] = []
    for relation in output.relations:
        locator = locate_exact(document, relation.evidence_excerpt)
        context = map_relation_to_evidence_context(
            relation.relation,
            relation.subject,
            relation.object,
            source_excerpt=relation.evidence_excerpt,
        )
        claims.append(
            RelationClaim(
                entity=relation.subject,
                entity_type=RelationEntityType.SKILL,
                context=context,
                usage=f"{relation.relation.value} {relation.object}",
                confidence=relation.confidence,
                source_excerpt=relation.evidence_excerpt,
                source_locator=locator,
            )
        )
        if relation.relation.value in {"used_in", "worked_on", "published"}:
            related_type = (
                RelationEntityType.RESEARCH
                if context is EvidenceContext.USED_IN_RESEARCH
                else RelationEntityType.PROJECT
            )
            claims.append(
                RelationClaim(
                    entity=relation.object,
                    entity_type=related_type,
                    context=context,
                    usage=f"{relation.relation.value} {relation.subject}",
                    confidence=relation.confidence,
                    source_excerpt=relation.evidence_excerpt,
                    source_locator=locator,
                )
            )
    return RelationExtractionOutput(relations=claims)


def section_evidence_to_graph_input(
    output: SectionEvidenceOutput,
    document: FixtureDocument,
    section_type: str,
) -> RelationExtractionOutput:
    claims: list[RelationClaim] = []
    for entity in output.entities:
        for evidence in entity.evidence:
            locator = locate_exact(document, evidence.source_excerpt)
            context = evidence.context
            if context is EvidenceContext.MENTIONED and evidence.usage:
                context = map_relation_to_evidence_context(
                    "used_in", entity.name, evidence.usage, section_type, evidence.source_excerpt
                )
            entity_type = _entity_type(entity.entity_type)
            claims.append(
                RelationClaim(
                    entity=entity.name,
                    entity_type=entity_type,
                    context=context,
                    usage=evidence.usage,
                    confidence=evidence.confidence,
                    source_excerpt=evidence.source_excerpt,
                    source_locator=locator,
                )
            )
    return RelationExtractionOutput(relations=claims)


def locate_exact(document: FixtureDocument, excerpt: str) -> SourceLocator:
    start = document.content.find(excerpt)
    if start < 0 or document.content.find(excerpt, start + 1) >= 0:
        raise ValueError("source excerpt must occur exactly once in document")
    return SourceLocator(
        document_id=document.document_id,
        section="document",
        start_offset=start,
        end_offset=start + len(excerpt),
    )


def _entity_type(value: str) -> RelationEntityType:
    normalized = value.casefold()
    return {
        "project": RelationEntityType.PROJECT,
        "research": RelationEntityType.RESEARCH,
        "education": RelationEntityType.EDUCATION,
        "publication": RelationEntityType.PUBLICATION,
        "employment": RelationEntityType.EMPLOYMENT,
    }.get(normalized, RelationEntityType.SKILL)
