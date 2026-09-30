from datetime import UTC, datetime

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.capability_analysis.semantic_core.adapters import adapt_role_requirement
from app.extraction.schemas import (
    DocumentKind,
    EvidenceStatus,
    EvidenceType,
    ExtractedClaim,
    ExtractionProfile,
    JDExtractionOutput,
    JDRequirementExtractionOutputV2,
    JDRequirementExtractionV2,
    JDRequirementModality,
    NativePdfLocator,
    RequirementFieldProvenance,
    ReviewState,
    SourceLocator,
)
from app.matching.schemas import CriterionDimension, RequirementClassification, RoleRequirement
from app.role_profile_authoring.source_adapter import adapt_jd_profile


def accepted_legacy(locator: bool = True) -> ExtractionProfile:
    source_locator = (
        SourceLocator(document_id="jd-1", section="required_skills", start_offset=0, end_offset=6)
        if locator
        else None
    )
    if locator:
        claim = ExtractedClaim(
            value="Python",
            evidence_type=EvidenceType.EXPLICIT_SKILL,
            confidence=0.9,
            evidence_status=EvidenceStatus.SUPPORTED,
            source_locator=source_locator,
            source_excerpt="Python",
        )
    else:
        claim = ExtractedClaim.model_construct(
            value="Python",
            evidence_type=EvidenceType.EXPLICIT_SKILL,
            confidence=0.9,
            evidence_status=EvidenceStatus.SUPPORTED,
            source_locator=None,
            source_excerpt="Python",
            evidence=[],
        )
    output = (
        JDExtractionOutput(required_skills=[claim], responsibilities=[], qualifications=[])
        if locator
        else JDExtractionOutput.model_construct(
            required_skills=[claim], responsibilities=[], qualifications=[]
        )
    )
    return ExtractionProfile(
        id="jd-accepted",
        job_id="job-jd-accepted",
        document_id="jd-1",
        document_kind=DocumentKind.JD,
        owner_actor_id=LEARNER_ID,
        version=1,
        review_state=ReviewState.ACCEPTED,
        accepted_by=REVIEWER_ID,
        accepted_at=datetime.now(UTC),
        output=output,
        audit={"provider": "fixture", "model": "fixture", "prompt_template_version": "1.0"},
    )



def test_legacy_adapter_preserves_source_and_reports_unrecoverable_semantics() -> None:
    adapted = adapt_jd_profile(accepted_legacy())

    assert adapted.source_schema == "legacy_v1"
    assert adapted.source_version == "1.1"
    assert adapted.requirements[0].evidence_terms == ["python"]
    assert adapted.requirements[0].provenance == {"evidence_terms": "jd_extraction"}
    assert adapted.requirements[0].source_locator is not None
    assert adapted.requirements[0].source_requirement_ref == "legacy.skill.1"
    assert {finding.code for finding in adapted.findings} >= {
        "legacy_missing_modality",
        "legacy_missing_logical_group",
        "legacy_missing_target_level",
    }
    assert adapted.requirements[0].confidence_threshold == 0.8
    assert adapted.requirements[0].threshold_source == "policy_default"
    assert adapted.requirements[0].threshold_policy_id == "capability-assessment-default"


def test_historical_role_requirement_does_not_claim_new_policy_for_implicit_threshold() -> None:
    requirement = {
        "id": "legacy-python",
        "criterion_dimension": "skill",
        "classification": "role_critical",
        "evidence_terms": ["python"],
        "confidence_threshold": 1.0,
        "assessment_recommendation": "review",
        "rubric_version": "rubric-v1",
    }

    historical = RoleRequirement.model_validate(requirement, strict=False)
    adapted = adapt_role_requirement(historical)

    assert adapted.threshold_source == "legacy_profile"
    assert adapted.threshold_policy_id is None
    assert adapted.threshold_policy_version is None


def test_legacy_adapter_blocks_when_locator_is_missing() -> None:
    adapted = adapt_jd_profile(accepted_legacy(locator=False))

    assert adapted.has_blocking
    assert "legacy_missing_provenance" in {finding.code for finding in adapted.findings}


def test_v2_adapter_preserves_explicit_requirement_semantics_and_provenance() -> None:
    source = accepted_legacy().model_copy(
        update={
            "output": JDRequirementExtractionOutputV2(
                requirements=[
                    JDRequirementExtractionV2(
                        requirement_id="mentor",
                        statement="Mentoring junior engineers",
                        criterion_dimension=None,
                        modality=JDRequirementModality.RESPONSIBILITY,
                        logical_group="team-leadership",
                        evidence_terms=["mentoring junior engineers"],
                        confidence=0.92,
                        evidence_status=EvidenceStatus.SUPPORTED,
                        source_locator=SourceLocator(
                            document_id="jd-1",
                            section="responsibilities",
                            start_offset=0,
                            end_offset=28,
                        ),
                        source_excerpt="Mentoring junior engineers",
                        provenance={
                            "modality": RequirementFieldProvenance.JD_EXTRACTION,
                            "criterion_dimension": RequirementFieldProvenance.JD_EXTRACTION,
                        },
                    )
                ]
            )
        }
    )
    adapted = adapt_jd_profile(source)

    requirement = adapted.requirements[0]
    assert adapted.source_schema == "jd_requirement_extraction"
    assert requirement.modality == "responsibility"
    assert requirement.logical_group == "team-leadership"
    assert requirement.provenance["logical_group"] == "jd_extraction"
    assert requirement.provenance["criterion_dimension"] == "jd_extraction"
    assert requirement.source_locator is not None
    assert requirement.source_locator.document_id == "jd-1"
    assert requirement.source_requirement_ref == "mentor"


def test_v2_contract_preserves_responsibility_without_candidate_dimension() -> None:
    source = accepted_legacy().model_copy(
        update={
            "output": JDRequirementExtractionOutputV2(
                requirements=[
                    JDRequirementExtractionV2(
                        requirement_id="monthly-reports",
                        statement="Prepare monthly financial reports",
                        criterion_dimension=None,
                        modality=JDRequirementModality.RESPONSIBILITY,
                        evidence_terms=["prepare monthly financial reports"],
                        confidence=0.94,
                        evidence_status=EvidenceStatus.SUPPORTED,
                        source_locator=SourceLocator(
                            document_id="jd-1",
                            section="responsibilities",
                            start_offset=0,
                            end_offset=37,
                        ),
                        source_excerpt="Prepare monthly financial reports",
                    )
                ]
            )
        }
    )

    adapted = adapt_jd_profile(source)

    assert len(adapted.requirements) == 1
    assert adapted.requirements[0].criterion_dimension is None
    assert adapted.requirements[0].modality == "responsibility"


def test_v2_contract_supports_credential_and_qualification_dimensions() -> None:
    output = JDRequirementExtractionOutputV2(
        requirements=[
            JDRequirementExtractionV2(
                requirement_id="pmp",
                statement="PMP certification preferred",
                criterion_dimension="credential",
                modality=JDRequirementModality.PREFERRED,
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_locator=SourceLocator(
                    document_id="jd-1", section="preferred", start_offset=0, end_offset=29
                ),
                source_excerpt="PMP certification preferred",
            ),
            JDRequirementExtractionV2(
                requirement_id="other",
                statement="Other explicit qualification",
                criterion_dimension="qualification",
                modality=JDRequirementModality.MUST,
                confidence=0.9,
                evidence_status=EvidenceStatus.SUPPORTED,
                source_locator=SourceLocator(
                    document_id="jd-1", section="required", start_offset=30, end_offset=59
                ),
                source_excerpt="Other explicit qualification",
            ),
        ]
    )

    source = accepted_legacy().model_copy(update={"output": output})
    adapted = adapt_jd_profile(source)

    assert [item.criterion_dimension.value for item in adapted.requirements] == [
        "credential",
        "qualification",
    ]
    assert adapted.requirements[0].modality == "preferred"
    assert adapted.requirements[1].modality == "must"


def test_v2_adapter_preserves_native_pdf_locator_and_logical_or() -> None:
    source = accepted_legacy().model_copy(
        update={
            "output": JDRequirementExtractionOutputV2(
                requirements=[
                    JDRequirementExtractionV2(
                        requirement_id="pmp-or-equivalent",
                        statement="PMP or equivalent certification",
                        criterion_dimension="credential",
                        modality=JDRequirementModality.PREFERRED,
                        logical_group="certification",
                        logical_operator="OR",
                        evidence_terms=["PMP", "equivalent certification"],
                        confidence=0.95,
                        evidence_status=EvidenceStatus.SUPPORTED,
                        source_locator=NativePdfLocator(
                            document_id="jd-1", page_number=2, section="preferred"
                        ),
                        source_excerpt="PMP or equivalent certification",
                    )
                ]
            )
        }
    )

    adapted = adapt_jd_profile(source)
    requirement = adapted.requirements[0]

    assert isinstance(requirement.source_locator, NativePdfLocator)
    assert requirement.source_locator.model_dump() == {
        "document_id": "jd-1",
        "page_number": 2,
        "section": "preferred",
    }
    assert requirement.logical_group == "certification"
    assert requirement.logical_operator == "OR"
    assert requirement.source_requirement_ref == "pmp-or-equivalent"


def test_v2_adapter_fails_closed_for_missing_dimension_on_non_responsibility() -> None:
    source = accepted_legacy().model_copy(
        update={
            "output": JDRequirementExtractionOutputV2(
                requirements=[
                    JDRequirementExtractionV2(
                        requirement_id="missing-dimension",
                        statement="Strong SQL",
                        criterion_dimension=None,
                        modality=JDRequirementModality.MUST,
                        evidence_terms=["strong sql"],
                        confidence=0.9,
                        evidence_status=EvidenceStatus.SUPPORTED,
                        source_locator=SourceLocator(
                            document_id="jd-1",
                            section="required",
                            start_offset=0,
                            end_offset=11,
                        ),
                        source_excerpt="Strong SQL",
                    )
                ]
            )
        }
    )

    adapted = adapt_jd_profile(source)

    assert adapted.requirements == []
    assert any(
        finding.code == "missing_criterion_dimension"
        and finding.requirement_id == "missing-dimension"
        for finding in adapted.findings
    )


def test_v2_adapter_preserves_unspecified_scope_context_without_scoring_dimension() -> None:
    source = accepted_legacy().model_copy(
        update={
            "output": JDRequirementExtractionOutputV2(
                requirements=[
                    JDRequirementExtractionV2(
                        requirement_id="warehouse-out-of-scope",
                        statement="Warehouse knowledge is not required",
                        criterion_dimension=None,
                        modality=JDRequirementModality.UNSPECIFIED,
                        evidence_terms=["warehouse knowledge is not required"],
                        confidence=0.96,
                        evidence_status=EvidenceStatus.SUPPORTED,
                        source_locator=SourceLocator(
                            document_id="jd-1",
                            section="scope",
                            start_offset=0,
                            end_offset=39,
                        ),
                        source_excerpt="Warehouse knowledge is not required",
                    )
                ]
            )
        }
    )

    adapted = adapt_jd_profile(source)

    assert len(adapted.requirements) == 1
    assert adapted.requirements[0].criterion_dimension is None
    assert adapted.requirements[0].modality == "unspecified"


def test_legacy_explicit_or_phrase_is_represented_as_or_without_domain_inference() -> None:
    source = accepted_legacy().model_copy(
        update={
            "output": JDExtractionOutput(
                required_skills=[],
                responsibilities=[],
                qualifications=[
                    ExtractedClaim(
                        value="Bachelor or Master degree in Computer Science or Data Science",
                        evidence_type=EvidenceType.EDUCATION,
                        confidence=0.99,
                        evidence_status=EvidenceStatus.SUPPORTED,
                        source_locator=SourceLocator(
                            document_id="jd-1",
                            section="qualifications",
                            start_offset=0,
                            end_offset=75,
                        ),
                        source_excerpt="Bachelor or Master degree in Computer Science or Data Science",
                    )
                ],
            )
        }
    )

    adapted = adapt_jd_profile(source)

    assert adapted.requirements[0].logical_operator == "OR"


def test_legacy_adapter_maps_qualifications_and_classification_conservatively() -> None:
    def claim(value: str, section: str, start: int) -> ExtractedClaim:
        return ExtractedClaim(
            value=value,
            evidence_type=EvidenceType.EXPLICIT_SKILL,
            confidence=0.9,
            evidence_status=EvidenceStatus.SUPPORTED,
            source_locator=SourceLocator(
                document_id="jd-1", section=section, start_offset=start, end_offset=start + len(value)
            ),
            source_excerpt=value,
        )

    source = accepted_legacy().model_copy(
        update={
            "output": JDExtractionOutput(
                required_skills=[
                    claim("Python", "required_skills", 0),
                    claim("Hiểu biết về hệ thống phân tán là lợi thế", "required_skills", 10),
                ],
                responsibilities=[
                    claim("Kinh nghiệm xây dựng và vận hành giải pháp AI end-to-end", "responsibilities", 20)
                ],
                qualifications=[
                    claim("Tối thiểu 1+ năm kinh nghiệm AI/ML", "qualifications", 30),
                    claim("Tốt nghiệp đại học ngành Khoa học Máy tính", "qualifications", 40),
                    claim("Kinh nghiệm làm việc trong môi trường đa chức năng", "qualifications", 50),
                ],
            )
        }
    )

    adapted = adapt_jd_profile(source)
    requirements = {requirement.evidence_terms[0]: requirement for requirement in adapted.requirements}

    assert requirements["tối thiểu 1+ năm kinh nghiệm ai/ml"].criterion_dimension is CriterionDimension.EXPERIENCE
    assert requirements["kinh nghiệm xây dựng và vận hành giải pháp ai end-to-end"].criterion_dimension is CriterionDimension.EXPERIENCE
    assert requirements["kinh nghiệm làm việc trong môi trường đa chức năng"].criterion_dimension is CriterionDimension.EXPERIENCE
    assert requirements["tốt nghiệp đại học ngành khoa học máy tính"].criterion_dimension is CriterionDimension.EDUCATION
    assert requirements["hiểu biết về hệ thống phân tán là lợi thế"].classification is RequirementClassification.PREFERRED
    assert requirements["python"].classification is RequirementClassification.UNCLASSIFIED
    assert any(
        finding.code == "legacy_uncertain_priority" and finding.requirement_id == requirements["python"].id
        for finding in adapted.findings
    )


def test_legacy_adapter_detects_duplicate_candidates_without_merging_requirements() -> None:
    def claim(value: str, section: str, start: int) -> ExtractedClaim:
        return ExtractedClaim(
            value=value,
            evidence_type=EvidenceType.EXPLICIT_SKILL,
            confidence=0.9,
            evidence_status=EvidenceStatus.SUPPORTED,
            source_locator=SourceLocator(
                document_id="jd-1", section=section, start_offset=start, end_offset=start + len(value)
            ),
            source_excerpt=value,
        )

    source = accepted_legacy().model_copy(
        update={
            "output": JDExtractionOutput(
                required_skills=[claim("Thiết kế mô hình ML/DL", "required_skills", 0)],
                responsibilities=[claim("Thiết kế mô hình ML DL", "responsibilities", 20)],
                qualifications=[],
            )
        }
    )

    adapted = adapt_jd_profile(source)

    assert len(adapted.requirements) == 2
    assert len(adapted.duplicate_candidate_groups) == 1
    group = adapted.duplicate_candidate_groups[0]
    assert set(group.requirement_ids) == {requirement.id for requirement in adapted.requirements}
    assert group.merge_recommended is True
    assert group.reviewer_required is True
