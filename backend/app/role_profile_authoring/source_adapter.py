import re
from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field

from app.capability_analysis.policy import (
    ASSESSMENT_CONFIDENCE_POLICY_ID,
    ASSESSMENT_CONFIDENCE_POLICY_VERSION,
    ASSESSMENT_CONFIDENCE_THRESHOLD,
)
from app.extraction.locators import SourceLocator
from app.extraction.schemas import (
    DocumentKind,
    EvidenceStatus,
    ExtractionProfile,
    JDExtractionOutput,
    JDRequirementExtractionOutputV2,
    JDRequirementModality,
    NativePdfLocator,
    ProviderPdfLocator,
    ReviewState,
)
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleRequirement,
)
from app.role_profile_authoring.quality_gate import evaluate_role_profile_draft
from app.role_profile_authoring.schemas import (
    DuplicateCandidateGroup,
    QualityFindingSeverity,
    RequirementFinding,
)


class JDSourceAdaptation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    requirements: list[RoleRequirement] = Field(default_factory=list)
    source_schema: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    findings: list[RequirementFinding] = Field(default_factory=list)
    duplicate_candidate_groups: list[DuplicateCandidateGroup] = Field(default_factory=list)

    @property
    def has_blocking(self) -> bool:
        return any(item.severity is QualityFindingSeverity.BLOCKING for item in self.findings)


def adapt_jd_profile(source: ExtractionProfile) -> JDSourceAdaptation:
    if source.document_kind is not DocumentKind.JD or source.review_state is not ReviewState.ACCEPTED:
        raise ValueError("only accepted JD profiles can be adapted")
    output = source.output
    if isinstance(output, JDRequirementExtractionOutputV2):
        return _adapt_v2(output)
    if isinstance(output, JDExtractionOutput):
        return _adapt_legacy(output)
    raise ValueError("source profile is not a JD extraction output")


def _adapt_v2(output: JDRequirementExtractionOutputV2) -> JDSourceAdaptation:
    requirements: list[RoleRequirement] = []
    findings: list[RequirementFinding] = []
    for index, item in enumerate(output.requirements, start=1):
        if item.evidence_status is not EvidenceStatus.SUPPORTED:
            continue
        if isinstance(item.source_locator, ProviderPdfLocator):
            findings.append(
                _finding(
                    item.requirement_id,
                    "unbound_pdf_locator",
                    QualityFindingSeverity.ERROR,
                    "source_locator",
                )
            )
            continue
        if item.criterion_dimension is None and item.modality not in {
            JDRequirementModality.RESPONSIBILITY,
            JDRequirementModality.UNSPECIFIED,
        }:
            findings.append(
                _finding(
                    item.requirement_id,
                    "missing_criterion_dimension",
                    QualityFindingSeverity.ERROR,
                    "criterion_dimension",
                )
            )
            continue
        token = _token(item.statement or "requirement")
        requirements.append(
            RoleRequirement(
                id=item.requirement_id or f"jd-v2-{index}-{token}",
                criterion_dimension=(
                    CriterionDimension(item.criterion_dimension)
                    if item.criterion_dimension is not None
                    else None
                ),
                classification=_classification_for(item.modality),
                evidence_terms=item.evidence_terms or [item.statement or token],
                conflicting_terms=item.conflicting_terms,
                confidence_threshold=ASSESSMENT_CONFIDENCE_THRESHOLD,
                assessment_recommendation="practical_task",
                rubric_version="rubric-v1",
                priority=item.priority,
                target_level=item.target_level,
                observable_behaviors=item.observable_behaviors,
                evidence_constraints=item.evidence_constraints,
                modality=item.modality.value if item.modality else None,
                logical_group=item.logical_group,
                logical_operator=item.logical_operator,
                threshold_source="policy_default",
                threshold_policy_id=ASSESSMENT_CONFIDENCE_POLICY_ID,
                threshold_policy_version=ASSESSMENT_CONFIDENCE_POLICY_VERSION,
                source_locator=(
                    item.source_locator
                    if isinstance(item.source_locator, (SourceLocator, NativePdfLocator))
                    else None
                ),
                source_requirement_ref=item.requirement_id,
                provenance={
                    **{key: value.value for key, value in item.provenance.items()},
                    "evidence_terms": "jd_extraction",
                    **({"modality": "jd_extraction"} if item.modality else {}),
                    **({"target_level": "jd_extraction"} if item.target_level else {}),
                    **({"priority": "jd_extraction"} if item.priority else {}),
                    **({"logical_group": "jd_extraction"} if item.logical_group else {}),
                    **(
                        {"observable_behaviors": "jd_extraction"}
                        if item.observable_behaviors
                        else {}
                    ),
                    **(
                        {"evidence_constraints": "jd_extraction"}
                        if item.evidence_constraints
                        else {}
                    ),
                },
            )
        )
    _, gate_findings, _ = evaluate_role_profile_draft(
        requirements,
        source_jd_profile_id="v2-source",
        source_jd_profile_version=1,
        source_schema="jd_requirement_extraction",
        source_version="2.2",
    )
    findings.extend(gate_findings)
    if not requirements:
        findings.append(_finding(None, "no_recoverable_requirements", QualityFindingSeverity.BLOCKING, None))
    return JDSourceAdaptation(
        requirements=requirements,
        source_schema="jd_requirement_extraction",
        source_version="2.0",
        findings=findings,
        duplicate_candidate_groups=detect_duplicate_candidates(requirements),
    )


def _adapt_legacy(output: JDExtractionOutput) -> JDSourceAdaptation:
    requirements: list[RoleRequirement] = []
    for prefix, claims in (
        ("skill", output.required_skills),
        ("responsibility", output.responsibilities),
        ("qualification", output.qualifications),
    ):
        for index, claim in enumerate(claims, start=1):
            # Null/unsupported placeholders must not become role requirements.
            if claim.evidence_status is not EvidenceStatus.SUPPORTED or claim.value is None:
                continue
            token = _token(claim.value)
            requirements.append(
                RoleRequirement(
                    id=f"jd-{prefix}-{index}-{token}",
                    criterion_dimension=_dimension_for_legacy(prefix, claim.value),
                    classification=_classification_for_legacy(prefix, claim.value),
                    evidence_terms=[claim.value.lower()],
                    confidence_threshold=ASSESSMENT_CONFIDENCE_THRESHOLD,
                    assessment_recommendation="practical_task",
                    rubric_version="rubric-v1",
                    provenance={"evidence_terms": "jd_extraction"},
                    source_locator=claim.source_locator,
                    source_requirement_ref=f"legacy.{prefix}.{index}",
                    logical_operator=("OR" if _contains_explicit_or(claim.value) else "AND"),
                    threshold_source="policy_default",
                    threshold_policy_id=ASSESSMENT_CONFIDENCE_POLICY_ID,
                    threshold_policy_version=ASSESSMENT_CONFIDENCE_POLICY_VERSION,
                )
            )
    _, findings, _ = evaluate_role_profile_draft(
        requirements,
        source_jd_profile_id="legacy-source",
        source_jd_profile_version=1,
        source_schema="legacy_v1",
        source_version="1.1",
    )
    if not requirements:
        findings.append(
            _finding(None, "legacy_no_recoverable_requirements", QualityFindingSeverity.BLOCKING, None)
        )
    return JDSourceAdaptation(
        requirements=requirements,
        source_schema="legacy_v1",
        source_version="1.1",
        findings=findings,
        duplicate_candidate_groups=detect_duplicate_candidates(requirements),
    )


def _dimension_for_legacy(prefix: str, value: str) -> CriterionDimension:
    if prefix == "responsibility":
        return CriterionDimension.EXPERIENCE
    if prefix != "qualification":
        return CriterionDimension.SKILL
    normalized = value.casefold()
    if any(term in normalized for term in ("kinh nghiệm", "experience", "năm", "tháng", "year", "month")):
        return CriterionDimension.EXPERIENCE
    if any(term in normalized for term in ("chứng chỉ", "certificate", "certification", "license", "licence")):
        return CriterionDimension.CREDENTIAL
    if any(term in normalized for term in ("đại học", "university", "bachelor", "master", "degree", "ngành", "major")):
        return CriterionDimension.EDUCATION
    return CriterionDimension.QUALIFICATION


def _classification_for_legacy(prefix: str, value: str) -> RequirementClassification:
    if _is_advantage(value):
        return RequirementClassification.PREFERRED
    if prefix == "responsibility":
        return RequirementClassification.ROLE_CRITICAL
    return RequirementClassification.UNCLASSIFIED


def _classification_for(modality: JDRequirementModality | None) -> RequirementClassification:
    if modality is JDRequirementModality.MUST:
        return RequirementClassification.ROLE_CRITICAL
    if modality is JDRequirementModality.PREFERRED:
        return RequirementClassification.PREFERRED
    if modality is JDRequirementModality.RESPONSIBILITY:
        return RequirementClassification.ROLE_CRITICAL
    return RequirementClassification.UNCLASSIFIED


def detect_duplicate_candidates(requirements: list[RoleRequirement]) -> list[DuplicateCandidateGroup]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for requirement in requirements:
        normalized = _normalize(" ".join(requirement.evidence_terms))
        grouped[normalized].append(requirement.id)
    return [
        DuplicateCandidateGroup(
            group_id=f"duplicate-{index}",
            requirement_ids=ids,
            reason="Normalized evidence terms overlap across independent source locators.",
            merge_recommended=True,
            reviewer_required=True,
        )
        for index, (_, ids) in enumerate(sorted(grouped.items()), start=1)
        if len(ids) > 1
    ]


def _is_advantage(value: str) -> bool:
    normalized = _normalize(value)
    return any(term in normalized for term in ("là lợi thế", "la loi the", "advantage", "nice to have"))


def _contains_explicit_or(value: str) -> bool:
    return re.search(r"(?<!\w)(?:or|hoặc)(?!\w)", value.casefold()) is not None


def _normalize(value: str) -> str:
    return re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE).strip()


def _token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80] or "requirement"


def _finding(
    requirement_id: str | None, code: str, severity: QualityFindingSeverity, field: str | None
) -> RequirementFinding:
    return RequirementFinding(
        requirement_id=requirement_id,
        code=code,
        severity=severity,
        field=field,
        message=code.replace("_", " ") + ".",
    )
