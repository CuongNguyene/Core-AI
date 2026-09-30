"""Source-preserving adapters into the domain-neutral semantic contracts."""

from collections.abc import Iterable
from dataclasses import dataclass

from app.capability_analysis.evidence_index import EvidenceIndex
from app.capability_analysis.semantic_core.contracts import (
    EvidenceExpectation,
    EvidenceSemantics,
    EvidenceSourceKind,
    RequirementSemantics,
    SemanticConstraint,
    SemanticConstraintDimension,
    SemanticConstraintOperator,
    SemanticContext,
    SemanticLogicalOperator,
    SemanticSourceLocator,
)
from app.extraction.evidence import EvidenceItem
from app.extraction.locators import SourceLocator
from app.extraction.profile import CandidateProfile
from app.extraction.schemas import NativePdfLocator
from app.matching.schemas import CriterionDimension, RoleRequirement

_EXPECTATION_BY_DIMENSION = {
    CriterionDimension.SKILL: EvidenceExpectation.UNKNOWN,
    CriterionDimension.EXPERIENCE: EvidenceExpectation.UNKNOWN,
    CriterionDimension.EDUCATION: EvidenceExpectation.EDUCATION,
    CriterionDimension.CREDENTIAL: EvidenceExpectation.CREDENTIAL,
    CriterionDimension.QUALIFICATION: EvidenceExpectation.UNKNOWN,
}


@dataclass(frozen=True, slots=True)
class _EntityProjection:
    source_kind: EvidenceSourceKind
    source_value: str
    concepts: tuple[str, ...]
    behaviors: tuple[str, ...]
    objects: tuple[str, ...]
    entity_ref: str
    evidence: tuple[EvidenceItem, ...]


def adapt_role_requirement(requirement: RoleRequirement) -> RequirementSemantics:
    """Adapt only authored fields; opaque constraints remain unresolved declarations."""
    constraints = tuple(
        SemanticConstraint(
            dimension=SemanticConstraintDimension.UNRESOLVED,
            operator=SemanticConstraintOperator.DECLARED,
            values=(value,),
            source_field="evidence_constraints",
            source_reference=requirement.source_requirement_ref,
        )
        for value in requirement.evidence_constraints
    )
    evidence_expectation = (
        _EXPECTATION_BY_DIMENSION.get(
            requirement.criterion_dimension,
            EvidenceExpectation.UNKNOWN,
        )
        if requirement.criterion_dimension is not None
        else EvidenceExpectation.UNKNOWN
    )
    if requirement.evidence_expectation is not None:
        evidence_expectation = EvidenceExpectation(requirement.evidence_expectation)
    unresolved = [
        field
        for field, value in (
            ("observable_behaviors", requirement.observable_behaviors),
            ("target_level", requirement.target_level),
            ("modality", requirement.modality),
            ("logical_group", requirement.logical_group),
        )
        if not value
    ]
    if evidence_expectation is EvidenceExpectation.UNKNOWN:
        unresolved.append("evidence_expectation")
    threshold_source = requirement.threshold_source
    threshold_policy_id = requirement.threshold_policy_id
    threshold_policy_version = requirement.threshold_policy_version
    # Profiles persisted before threshold provenance was introduced have no fields-set
    # markers for the new metadata. Preserve their historical 1.0 threshold without
    # misattributing it to the current policy default (0.8).
    if (
        requirement.confidence_threshold == 1.0
        and "threshold_source" not in requirement.model_fields_set
        and "threshold_policy_id" not in requirement.model_fields_set
        and "threshold_policy_version" not in requirement.model_fields_set
    ):
        threshold_source = "legacy_profile"
        threshold_policy_id = None
        threshold_policy_version = None
    return RequirementSemantics(
        requirement_id=requirement.id,
        concepts=tuple(requirement.evidence_terms),
        behaviors=tuple(requirement.observable_behaviors),
        objects=(),
        constraints=constraints,
        evidence_expectation=evidence_expectation,
        source_requirement_ref=requirement.source_requirement_ref,
        source_locator=_adapt_locator(requirement.source_locator),
        provenance=tuple(sorted(requirement.provenance.items())),
        unresolved_fields=tuple(unresolved),
        logical_operator=SemanticLogicalOperator(requirement.logical_operator),
        threshold_source=threshold_source,
        threshold_policy_id=threshold_policy_id,
        threshold_policy_version=threshold_policy_version,
    )


def adapt_evidence_index(index: EvidenceIndex) -> tuple[EvidenceSemantics, ...]:
    """Return one semantic value per actual EvidenceItem without flattening contexts."""
    observations: list[EvidenceSemantics] = []
    for entity_position, entity in enumerate(_project_entities(index.candidate_profile)):
        for evidence_position, evidence in enumerate(entity.evidence):
            if evidence.source_locator is None:
                continue
            unresolved = [
                field
                for field, value in (
                    ("participation", evidence.usage),
                    ("original_evidence_type", evidence.original_evidence_type),
                )
                if value is None
            ]
            if evidence.context.value == SemanticContext.UNKNOWN.value:
                unresolved.append("context")
            observations.append(
                EvidenceSemantics(
                    evidence_ref=_evidence_ref(
                        index.source,
                        entity,
                        entity_position,
                        evidence_position,
                        evidence.source_locator,
                    ),
                    concepts=entity.concepts,
                    behaviors=entity.behaviors,
                    objects=entity.objects,
                    context=SemanticContext(evidence.context.value),
                    participation=evidence.usage,
                    source_kind=entity.source_kind,
                    confidence=evidence.confidence,
                    original_evidence_type=evidence.original_evidence_type,
                    source_locator=_adapt_locator(evidence.source_locator),
                    source_value=entity.source_value,
                    source_excerpt=evidence.source_excerpt,
                    provenance=(
                        ("evidence_index_source", index.source),
                        ("entity_ref", entity.entity_ref),
                        ("source_type", evidence.source_type),
                    ),
                    unresolved_fields=tuple(unresolved),
                )
            )
    return tuple(observations)


def _project_entities(profile: CandidateProfile) -> Iterable[_EntityProjection]:
    for position, employment in enumerate(profile.employment_history):
        yield _EntityProjection(
            source_kind=EvidenceSourceKind.EMPLOYMENT,
            source_value=employment.name,
            concepts=_values(employment.name, employment.role),
            behaviors=(),
            objects=_values(employment.organization),
            entity_ref=employment.entity_id or f"employment_history:{position}",
            evidence=tuple(employment.evidence),
        )
    for position, project in enumerate(profile.projects):
        yield _simple_projection(
            EvidenceSourceKind.PROJECT,
            project.name,
            project.entity_id,
            position,
            project.evidence,
        )
    for position, research in enumerate(profile.research_work):
        yield _simple_projection(
            EvidenceSourceKind.RESEARCH,
            research.name,
            research.entity_id,
            position,
            research.evidence,
        )
    for position, education in enumerate(profile.education):
        yield _EntityProjection(
            source_kind=EvidenceSourceKind.EDUCATION,
            source_value=education.field or education.degree or education.institution,
            concepts=_values(education.field, education.degree),
            behaviors=(),
            objects=(education.institution,),
            entity_ref=education.entity_id or f"education:{position}",
            evidence=tuple(education.evidence),
        )
    for position, publication in enumerate(profile.publications):
        yield _EntityProjection(
            source_kind=EvidenceSourceKind.PUBLICATION,
            source_value=publication.title,
            concepts=(publication.title,),
            behaviors=(),
            objects=_values(publication.venue),
            entity_ref=publication.entity_id or f"publication:{position}",
            evidence=tuple(publication.evidence),
        )
    for position, skill in enumerate(profile.skills):
        yield _simple_projection(
            EvidenceSourceKind.SKILL, skill.entity, skill.entity_id, position, skill.evidence
        )
    for position, credential in enumerate(profile.credentials):
        yield _simple_projection(
            EvidenceSourceKind.CREDENTIAL,
            credential.name,
            credential.entity_id,
            position,
            credential.evidence,
        )
    for position, activity in enumerate(profile.activities):
        yield _EntityProjection(
            source_kind=EvidenceSourceKind.ACTIVITY,
            source_value=activity.statement,
            concepts=tuple(activity.related_entities),
            behaviors=(activity.statement,),
            objects=(),
            entity_ref=activity.entity_id or f"activity:{position}",
            evidence=tuple(activity.evidence),
        )


def _simple_projection(
    source_kind: EvidenceSourceKind,
    value: str,
    entity_id: str | None,
    position: int,
    evidence: list[EvidenceItem],
) -> _EntityProjection:
    return _EntityProjection(
        source_kind=source_kind,
        source_value=value,
        concepts=(value,),
        behaviors=(),
        objects=(),
        entity_ref=entity_id or f"{source_kind.value}:{position}",
        evidence=tuple(evidence),
    )


def _values(*values: str | None) -> tuple[str, ...]:
    return tuple(value for value in values if value)


def _adapt_locator(
    locator: SourceLocator | NativePdfLocator | None,
) -> SemanticSourceLocator | None:
    if locator is None:
        return None
    if isinstance(locator, NativePdfLocator):
        return SemanticSourceLocator(
            document_id=locator.document_id,
            section=locator.section,
            page_number=locator.page_number,
        )
    return SemanticSourceLocator(
        document_id=locator.document_id,
        section=locator.section,
        start_offset=locator.start_offset,
        end_offset=locator.end_offset,
    )


def _evidence_ref(
    index_source: str,
    entity: _EntityProjection,
    entity_position: int,
    evidence_position: int,
    locator: SourceLocator | None,
) -> str:
    prefix = index_source
    if locator is not None:
        prefix = ":".join(
            (
                locator.document_id,
                locator.section,
                str(locator.start_offset),
                str(locator.end_offset),
            )
        )
    return ":".join(
        (
            prefix,
            entity.source_kind.value,
            entity.entity_ref,
            str(entity_position),
            str(evidence_position),
        )
    )
