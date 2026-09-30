from collections.abc import Iterable

from app.extraction.evidence import EvidenceItem, RelationEntityType
from app.extraction.normalization import canonicalize_entity, normalization_key
from app.extraction.profile import (
    CandidateProfile,
    EducationEntity,
    ExperienceEntity,
    ProjectEntity,
    PublicationEntity,
    RelationExtractionOutput,
    ResearchEntity,
    SkillEntity,
)
from app.extraction.profile_builder import build_candidate_profile_from_output
from app.extraction.schemas import CVExtractionOutput


def merge_relation_evidence(
    full_document: RelationExtractionOutput,
    section_extraction: RelationExtractionOutput | Iterable[RelationExtractionOutput] | None = None,
) -> CandidateProfile:
    """Merge relation context with grounded section evidence into a profile."""
    grouped: dict[tuple[RelationEntityType, str], tuple[str, list[EvidenceItem]]] = {}
    sections = (
        [section_extraction]
        if isinstance(section_extraction, RelationExtractionOutput)
        else list(section_extraction or [])
    )
    streams: Iterable[tuple[RelationExtractionOutput, str]] = [
        (full_document, "full_document"),
        *[(section, "section_extraction") for section in sections],
    ]
    for output, source_type in streams:
        for relation in output.relations:
            key = (relation.entity_type, normalization_key(relation.entity))
            display_name, evidence = grouped.get(key, (canonicalize_entity(relation.entity), []))
            item = EvidenceItem(
                context=relation.context,
                usage=relation.usage,
                source_excerpt=relation.source_excerpt,
                confidence=relation.confidence,
                source_type=source_type,
                source_locator=relation.source_locator,
            )
            _append_stronger_evidence(evidence, item)
            grouped[key] = (display_name, evidence)

    profile = CandidateProfile()
    for (entity_type, normalized), (display_name, evidence) in grouped.items():
        entity_id = f"{entity_type.value}:{normalized}"
        entity = _profile_entity(entity_type, entity_id, display_name, evidence)
        if entity_type is RelationEntityType.SKILL:
            profile.skills.append(entity)  # type: ignore[arg-type]
        elif entity_type is RelationEntityType.EMPLOYMENT:
            profile.employment_history.append(entity)  # type: ignore[arg-type]
        elif entity_type is RelationEntityType.PROJECT:
            profile.projects.append(entity)  # type: ignore[arg-type]
        elif entity_type is RelationEntityType.RESEARCH:
            profile.research_work.append(entity)  # type: ignore[arg-type]
        elif entity_type is RelationEntityType.EDUCATION:
            profile.education.append(entity)  # type: ignore[arg-type]
        elif entity_type is RelationEntityType.PUBLICATION:
            profile.publications.append(entity)  # type: ignore[arg-type]
    return profile


def profile_from_legacy_cv(output: CVExtractionOutput) -> CandidateProfile:
    """Adapt the compatibility CV schema into graph entities.

    This adapter is intentionally conservative: legacy fields provide entity
    categories, but do not justify stronger usage claims. New relation
    extraction should be preferred whenever available.
    """
    return build_candidate_profile_from_output(output)


def _append_stronger_evidence(evidence: list[EvidenceItem], candidate: EvidenceItem) -> None:
    for index, existing in enumerate(evidence):
        if (
            existing.context is candidate.context
            and existing.source_excerpt == candidate.source_excerpt
        ):
            if candidate.confidence > existing.confidence:
                evidence[index] = candidate
            return
    evidence.append(candidate)


def _profile_entity(
    entity_type: RelationEntityType,
    entity_id: str,
    display_name: str,
    evidence: list[EvidenceItem],
) -> (
    ExperienceEntity
    | ProjectEntity
    | ResearchEntity
    | EducationEntity
    | PublicationEntity
    | SkillEntity
):
    if entity_type is RelationEntityType.SKILL:
        return SkillEntity(entity_id=entity_id, entity=display_name, evidence=evidence)
    if entity_type is RelationEntityType.EMPLOYMENT:
        return ExperienceEntity(entity_id=entity_id, name=display_name, evidence=evidence)
    if entity_type is RelationEntityType.PROJECT:
        return ProjectEntity(entity_id=entity_id, name=display_name, evidence=evidence)
    if entity_type is RelationEntityType.RESEARCH:
        return ResearchEntity(entity_id=entity_id, name=display_name, evidence=evidence)
    if entity_type is RelationEntityType.EDUCATION:
        return EducationEntity(entity_id=entity_id, institution=display_name, evidence=evidence)
    return PublicationEntity(entity_id=entity_id, title=display_name, evidence=evidence)
