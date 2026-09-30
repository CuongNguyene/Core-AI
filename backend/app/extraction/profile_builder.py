from collections.abc import Iterable

from app.extraction.evidence import EvidenceContext, EvidenceItem
from app.extraction.normalization import canonicalize_entity, normalization_key
from app.extraction.profile import (
    CandidateProfile,
    CapabilityActivity,
    CredentialEntity,
    EducationEntity,
    ExperienceEntity,
    ProfileFinding,
    ProjectEntity,
    PublicationEntity,
    ResearchEntity,
    SkillEntity,
)
from app.extraction.schemas import CVExtractionOutput, EvidenceType, ExtractedClaim


def map_evidence_type_to_context(evidence_type: EvidenceType) -> EvidenceContext:
    return {
        EvidenceType.EXPLICIT_SKILL: EvidenceContext.MENTIONED,
        EvidenceType.WORK_EXPERIENCE: EvidenceContext.USED_IN_EMPLOYMENT,
        EvidenceType.PROJECT_USAGE: EvidenceContext.USED_IN_PROJECT,
        EvidenceType.EDUCATION: EvidenceContext.STUDIED,
        EvidenceType.PUBLICATION: EvidenceContext.USED_IN_RESEARCH,
        EvidenceType.CERTIFICATION: EvidenceContext.CREDENTIALED,
        EvidenceType.UNKNOWN: EvidenceContext.UNKNOWN,
    }[evidence_type]


def build_candidate_profile(
    *,
    skills: Iterable[ExtractedClaim],
    experience: Iterable[ExtractedClaim],
    education: Iterable[ExtractedClaim],
) -> CandidateProfile:
    """Project accepted legacy CV claims without discarding evidence semantics."""
    grouped: dict[tuple[str, str], tuple[str, list[EvidenceItem]]] = {}
    findings: list[ProfileFinding] = []
    activities: list[tuple[str, EvidenceItem]] = []
    for bucket, claims in (("skills", skills), ("experience", experience), ("education", education)):
        for claim in claims:
            if claim.evidence_status.value != "supported" or claim.value is None:
                if claim.evidence_status.value in {"unknown", "insufficient"}:
                    findings.append(ProfileFinding(code="claim_not_supported", severity="INFO"))
                continue
            entity_type = _entity_type(claim.evidence_type, bucket)
            if entity_type is None:
                activity_evidence = _evidence_item(claim)
                if _looks_like_activity(claim.value):
                    activities.append((claim.value, activity_evidence))
                else:
                    findings.append(ProfileFinding(code="unclassified_evidence", severity="INFO"))
                continue
            key = (entity_type, normalization_key(claim.value))
            display, evidence = grouped.get(key, (canonicalize_entity(claim.value), []))
            candidate = _evidence_item(claim)
            _append_evidence(evidence, candidate)
            grouped[key] = (display, evidence)

    profile = CandidateProfile(findings=findings)
    profile.activities.extend(
        CapabilityActivity(statement=statement, evidence=[evidence])
        for statement, evidence in activities
    )
    for (entity_type, normalized), (display, evidence) in grouped.items():
        entity_id = f"{entity_type}:{normalized}"
        if entity_type == "skill":
            profile.skills.append(SkillEntity(entity_id=entity_id, entity=display, evidence=evidence))
        elif entity_type == "employment":
            profile.employment_history.append(
                ExperienceEntity(entity_id=entity_id, name=display, evidence=evidence)
            )
        elif entity_type == "project":
            profile.projects.append(ProjectEntity(entity_id=entity_id, name=display, evidence=evidence))
        elif entity_type == "research":
            profile.research_work.append(ResearchEntity(entity_id=entity_id, name=display, evidence=evidence))
        elif entity_type == "education":
            profile.education.append(
                EducationEntity(entity_id=entity_id, institution=display, evidence=evidence)
            )
        elif entity_type == "publication":
            profile.publications.append(
                PublicationEntity(entity_id=entity_id, title=display, evidence=evidence)
            )
        elif entity_type == "credential":
            profile.credentials.append(
                CredentialEntity(entity_id=entity_id, name=display, evidence=evidence)
            )
    return profile


def build_candidate_profile_from_output(output: CVExtractionOutput) -> CandidateProfile:
    return build_candidate_profile(
        skills=output.skills, experience=output.experience, education=output.education
    )


def _entity_type(evidence_type: EvidenceType, bucket: str) -> str | None:
    if evidence_type is EvidenceType.UNKNOWN and bucket == "skills":
        return "skill"
    if evidence_type is EvidenceType.WORK_EXPERIENCE and bucket == "experience":
        return "employment"
    if evidence_type is EvidenceType.PROJECT_USAGE:
        return "project" if bucket == "experience" else "skill"
    return {
        EvidenceType.EXPLICIT_SKILL: "skill",
        EvidenceType.WORK_EXPERIENCE: "skill",
        EvidenceType.PUBLICATION: "publication",
        EvidenceType.EDUCATION: "education",
        EvidenceType.CERTIFICATION: "credential",
    }.get(evidence_type)


def _evidence_item(claim: ExtractedClaim) -> EvidenceItem:
    assert claim.value is not None
    return EvidenceItem(
        context=map_evidence_type_to_context(claim.evidence_type),
        usage=f"legacy_{claim.evidence_type.value}",
        source_excerpt=claim.source_excerpt or claim.value,
        confidence=claim.confidence,
        source_type="legacy_cv_field",
        source_locator=claim.source_locator,
        original_evidence_type=claim.evidence_type.value,
    )


def _looks_like_activity(value: str | None) -> bool:
    if not value:
        return False
    activity_terms = (
        "built ",
        "developed ",
        "designed ",
        "deployed ",
        "evaluated ",
        "managed ",
        "mentored ",
        "pipeline ",
        "dashboard ",
    )
    return len(value.split()) >= 3 and value.casefold().startswith(activity_terms)


def _append_evidence(evidence: list[EvidenceItem], candidate: EvidenceItem) -> None:
    for index, existing in enumerate(evidence):
        if (
            existing.context is candidate.context
            and existing.source_excerpt == candidate.source_excerpt
            and existing.source_locator == candidate.source_locator
        ):
            if candidate.confidence > existing.confidence:
                evidence[index] = candidate
            return
    evidence.append(candidate)
