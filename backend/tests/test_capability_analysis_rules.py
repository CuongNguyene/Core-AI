from datetime import UTC, datetime

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.capability_analysis.domain_packs.it_ai import IT_AI_PACK
from app.capability_analysis.rules import (
    _requires_production,
    _semantic_requirement,
    build_gap_overlap_links,
    build_preview_readiness,
    build_provisional_capability_profile,
    build_verification_queue,
    evaluate_target,
)
from app.capability_analysis.schemas import (
    CapabilityEvidenceStatus,
    TargetType,
    TargetUsageMode,
)
from app.extraction.evidence import EvidenceContext, EvidenceItem
from app.extraction.locators import SourceLocator
from app.extraction.profile import (
    CandidateProfile,
    EducationEntity,
    ExperienceEntity,
    ProjectEntity,
    SkillEntity,
)
from app.extraction.schemas import (
    CVExtractionOutput,
    DocumentKind,
    ExtractionProfile,
    ReviewState,
)
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)


def graph_evidence(
    *,
    confidence: float = 0.91,
    context: EvidenceContext = EvidenceContext.USED_IN_PRODUCTION,
    usage: str | None = "implemented",
    with_locator: bool = True,
    source_excerpt: str = "Implemented Python services.",
    offset: int = 10,
) -> EvidenceItem:
    return EvidenceItem(
        context=context,
        usage=usage,
        source_excerpt=source_excerpt,
        confidence=confidence,
        source_type="cv_section",
        source_locator=(
            SourceLocator(
                document_id="cv-document-1",
                section="experience",
                start_offset=offset,
                end_offset=offset + len(source_excerpt),
            )
            if with_locator
            else None
        ),
    )


def accepted_graph_cv(*skills: SkillEntity) -> ExtractionProfile:
    return ExtractionProfile(
        id="accepted-cv-profile-1",
        job_id="cv-job-1",
        document_id="cv-document-1",
        document_kind=DocumentKind.CV,
        owner_actor_id=LEARNER_ID,
        version=2,
        review_state=ReviewState.ACCEPTED,
        accepted_by=REVIEWER_ID,
        accepted_at=datetime(2026, 8, 6, tzinfo=UTC),
        output=CVExtractionOutput(skills=[], experience=[], education=[]),
        candidate_profile=CandidateProfile(skills=list(skills)),
        audit={},
    )


def target(
    target_id: str,
    *requirements: RoleRequirement,
    status: RoleProfileStatus = RoleProfileStatus.ACTIVE,
) -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id=target_id,
        version="1.0",
        status=status,
        source_jd_profile_id=f"jd-{target_id}",
        source_jd_profile_version=1,
        rule_set_version="rules-v1",
        policy_version="policy-v1",
        requirements=list(requirements),
    )


def requirement(
    requirement_id: str,
    *,
    terms: list[str],
    dimension: CriterionDimension = CriterionDimension.SKILL,
    classification: RequirementClassification = RequirementClassification.ROLE_CRITICAL,
    confidence_threshold: float = 0.8,
    conflicting_terms: list[str] | None = None,
) -> RoleRequirement:
    return RoleRequirement(
        id=requirement_id,
        criterion_dimension=dimension,
        classification=classification,
        evidence_terms=terms,
        conflicting_terms=conflicting_terms or [],
        confidence_threshold=confidence_threshold,
        assessment_recommendation="practical_task",
        rubric_version="rubric-v1",
    )


def test_graph_evidence_keeps_environment_participation_context_and_confidence() -> None:
    profile = accepted_graph_cv(SkillEntity(entity="Python", evidence=[graph_evidence()]))

    current = build_provisional_capability_profile(profile)

    observation = current.capabilities[0].observations[0]
    assert (observation.environment, observation.participation, observation.context) == (
        "production",
        "implemented",
        "used_in_production",
    )
    assert observation.confidence == 0.91
    assert observation.source_locator.document_id == "cv-document-1"


def test_semantic_project_model_evaluation_is_retrieved_but_remains_project_strength() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            *[],
        ).model_copy(
            update={
                "candidate_profile": CandidateProfile(
                    projects=[
                            ProjectEntity(
                                name="model evaluation",
                            evidence=[
                                graph_evidence(
                                    context=EvidenceContext.USED_IN_PROJECT,
                                    source_excerpt="Developed and evaluated CNN models with evaluation metrics",
                                )
                            ],
                        )
                    ]
                )
            }
        )
    )
    analysis = evaluate_target(
        current,
        target(
            "role-current",
            requirement(
                "evaluation",
                terms=["model design", "model training", "model evaluation"],
            ),
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assessment = analysis.assessments[0]
    assert assessment.evidence_status.value == "requires_verification"
    assert assessment.evidence_strength.value == "project"


def test_contextual_responsibility_is_not_scored_as_capability_gap() -> None:
    responsibility = RoleRequirement(
        id="monthly-reports",
        criterion_dimension=None,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=["prepare monthly financial reports"],
        modality="responsibility",
        confidence_threshold=0.8,
        assessment_recommendation="review",
        rubric_version="rubric-v1",
    )
    skill = requirement("python", terms=["python"])

    analysis = evaluate_target(
        build_provisional_capability_profile(
            accepted_graph_cv(SkillEntity(entity="Python", evidence=[graph_evidence()]))
        ),
        target("role-current", responsibility, skill),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assert [assessment.requirement_id for assessment in analysis.assessments] == ["python"]
    assert all(gap.requirement_id != "monthly-reports" for gap in analysis.gaps)


def test_unspecified_scope_context_is_not_scored_as_capability_gap() -> None:
    exclusion = RoleRequirement(
        id="warehouse-out-of-scope",
        criterion_dimension=None,
        classification=RequirementClassification.UNCLASSIFIED,
        evidence_terms=["warehouse knowledge is not required"],
        modality="unspecified",
        confidence_threshold=0.8,
        assessment_recommendation="context_only",
        rubric_version="rubric-v1",
    )
    skill = requirement("python", terms=["python"])

    analysis = evaluate_target(
        build_provisional_capability_profile(
            accepted_graph_cv(SkillEntity(entity="Python", evidence=[graph_evidence()]))
        ),
        target("role-current", exclusion, skill),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assert [assessment.requirement_id for assessment in analysis.assessments] == ["python"]
    assert all(gap.requirement_id != "warehouse-out-of-scope" for gap in analysis.gaps)


def test_mixed_role_profile_only_assesses_candidate_evaluable_requirements() -> None:
    contextual = [
        RoleRequirement(
            id=f"responsibility-{index}",
            criterion_dimension=None,
            classification=RequirementClassification.ROLE_CRITICAL,
            evidence_terms=[f"responsibility {index}"],
            modality="responsibility",
            confidence_threshold=0.8,
            assessment_recommendation="review",
            rubric_version="rubric-v1",
        )
        for index in range(15)
    ]
    exclusions = [
        RoleRequirement(
            id=f"exclusion-{index}",
            criterion_dimension=None,
            classification=RequirementClassification.UNCLASSIFIED,
            evidence_terms=[f"excluded criterion {index}"],
            modality="unspecified",
            confidence_threshold=0.8,
            assessment_recommendation="context_only",
            rubric_version="rubric-v1",
        )
        for index in range(3)
    ]
    scoreable = [
        requirement(
            f"scoreable-{index}",
            terms=[f"criterion {index}"],
            dimension=dimension,
        )
        for index, dimension in enumerate(
            [
                CriterionDimension.SKILL,
                CriterionDimension.EXPERIENCE,
                CriterionDimension.EDUCATION,
                CriterionDimension.CREDENTIAL,
                CriterionDimension.QUALIFICATION,
            ]
            * 5
        )
    ]

    analysis = evaluate_target(
        build_provisional_capability_profile(
            accepted_graph_cv(SkillEntity(entity="Python", evidence=[graph_evidence()]))
        ),
        target("role-current", *scoreable, *contextual, *exclusions),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assert len(analysis.assessments) == 25
    assert {assessment.requirement_id for assessment in analysis.assessments} == {
        item.id for item in scoreable
    }


def test_all_candidate_evaluable_dimensions_are_assessed() -> None:
    requirements = [
        requirement("skill", terms=["Python"], dimension=CriterionDimension.SKILL),
        requirement("experience", terms=["Python"], dimension=CriterionDimension.EXPERIENCE),
        requirement("education", terms=["Python"], dimension=CriterionDimension.EDUCATION),
        requirement("credential", terms=["Python"], dimension=CriterionDimension.CREDENTIAL),
        requirement(
            "qualification", terms=["Python"], dimension=CriterionDimension.QUALIFICATION
        ),
    ]

    analysis = evaluate_target(
        build_provisional_capability_profile(
            accepted_graph_cv(SkillEntity(entity="Python", evidence=[graph_evidence()]))
        ),
        target("role-current", *requirements),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assert [assessment.requirement_id for assessment in analysis.assessments] == [
        "credential",
        "education",
        "experience",
        "qualification",
        "skill",
    ]


def test_logical_or_is_satisfied_by_one_matching_candidate_capability() -> None:
    either = requirement("python-or-docker", terms=["Python", "Docker"])
    either = either.model_copy(update={"logical_operator": "OR"})

    analysis = evaluate_target(
        build_provisional_capability_profile(
            accepted_graph_cv(SkillEntity(entity="Docker", evidence=[graph_evidence()]))
        ),
        target("role-current", either),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assert len(analysis.assessments) == 1
    assert analysis.assessments[0].evidence_status.value == "supported"
    assert analysis.gaps == []


def test_preview_assessment_persistence_contract_excludes_raw_document_content() -> None:
    profile = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Python",
                evidence=[graph_evidence(source_excerpt="PRIVATE RAW CV TEXT")],
            )
        )
    )
    analysis = evaluate_target(
        profile,
        target("role-current", requirement("python", terms=["Python"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assert "PRIVATE RAW CV TEXT" not in str(analysis.model_dump(mode="json"))


def test_production_context_mismatch_preserves_retrieved_project_evidence_refs() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            *[],
        ).model_copy(
            update={
                "candidate_profile": CandidateProfile(
                    projects=[
                        ProjectEntity(
                            name="deployment-a",
                            evidence=[
                                graph_evidence(
                                    context=EvidenceContext.USED_IN_PROJECT,
                                    source_excerpt="Deployed a realtime dashboard",
                                ),
                                graph_evidence(
                                    context=EvidenceContext.USED_IN_PROJECT,
                                    source_excerpt="Released the dashboard from a project environment",
                                    offset=80,
                                ),
                            ],
                        )
                    ]
                )
            }
        )
    )
    analysis = evaluate_target(
        current,
        target(
            "role-current",
            requirement("production", terms=["deployment-a", "production"]),
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assessment = analysis.assessments[0]
    assert assessment.evidence_status.value == "context_mismatch"
    assert assessment.matched_evidence_refs
    assert assessment.evidence_strength.value == "project"
    assert assessment.retrieved_candidate_count == 2
    assert assessment.eligible_candidate_count == 0


def test_production_phrase_preserves_identity_remainder_for_candidate_retrieval() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv().model_copy(
            update={
                "candidate_profile": CandidateProfile(
                    projects=[
                        ProjectEntity(
                            name="deployment",
                            evidence=[
                                graph_evidence(
                                    context=EvidenceContext.USED_IN_PROJECT,
                                    source_excerpt="Deployed a project dashboard",
                                )
                            ],
                        )
                    ]
                )
            }
        )
    )

    analysis = evaluate_target(
        current,
        target(
            "role-current",
            requirement("production-deployment", terms=["production deployment"]),
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assessment = analysis.assessments[0]
    assert assessment.retrieved_candidate_count == 1
    assert assessment.eligible_candidate_count == 0
    assert assessment.evidence_status.value == "context_mismatch"


def test_authored_production_token_bridge_is_provenanced_and_not_inferred() -> None:
    with_production = requirement(
        "deployment-production",
        terms=["deployment-a", "production deployment"],
    ).model_copy(update={"source_requirement_ref": "jd-requirement-7"})
    without_production = requirement("deployment", terms=["deployment-a"])
    preproduction = requirement(
        "preproduction-deployment",
        terms=["preproduction deployment"],
    )

    assert _requires_production(with_production) is True
    semantics = _semantic_requirement(with_production, production_required=True)
    assert semantics.concepts == ("deployment-a", "deployment")
    assert len(semantics.constraints) == 1
    constraint = semantics.constraints[0]
    assert constraint.dimension.value == "context"
    assert constraint.values == ("used_in_production", "owned_system")
    assert constraint.source_field == "evidence_terms:legacy_exact_production"
    assert constraint.source_reference == "jd-requirement-7"

    assert _requires_production(without_production) is False
    generic = _semantic_requirement(without_production, production_required=False)
    assert generic.concepts == ("deployment-a",)
    assert generic.constraints == ()

    assert _requires_production(preproduction) is False
    preproduction_semantics = _semantic_requirement(
        preproduction,
        production_required=False,
    )
    assert preproduction_semantics.concepts == ("preproduction deployment",)
    assert preproduction_semantics.constraints == ()


def test_requirement_assessment_projects_source_kind_aware_candidate_eligibility() -> None:
    profile = accepted_graph_cv(*[]).model_copy(
        update={
            "candidate_profile": CandidateProfile(
                education=[
                    EducationEntity(
                        institution="Example University",
                        field="Field A",
                        evidence=[
                            graph_evidence(
                                context=EvidenceContext.STUDIED,
                                source_excerpt="Studied Field A",
                                offset=10,
                            )
                        ],
                    )
                ],
                skills=[
                    SkillEntity(
                        entity="Field A",
                        evidence=[
                            graph_evidence(
                                context=EvidenceContext.USED_IN_EMPLOYMENT,
                                source_excerpt="Applied Field A at work",
                                offset=40,
                            )
                        ],
                    )
                ],
            )
        }
    )
    current = build_provisional_capability_profile(profile)

    assessment = evaluate_target(
        current,
        target(
            "role-current",
            requirement(
                "field-education",
                terms=["Field A"],
                dimension=CriterionDimension.EDUCATION,
            ),
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    education_refs = {
        observation.evidence_ref
        for observation in current.semantic_evidence
        if observation.context.value == EvidenceContext.STUDIED.value
        and observation.concepts == ("Field A",)
    }
    assert assessment.evidence_status.value == "supported"
    assert assessment.retrieved_candidate_count == 2
    assert assessment.eligible_candidate_count == 1
    assert set(assessment.matched_evidence_refs) == education_refs


def test_analysis_projection_preserves_source_kind_independently_from_context() -> None:
    profile = accepted_graph_cv(*[]).model_copy(
        update={
            "candidate_profile": CandidateProfile(
                employment_history=[
                    ExperienceEntity(
                        name="Field A",
                        evidence=[
                            graph_evidence(
                                context=EvidenceContext.USED_IN_EMPLOYMENT,
                                source_excerpt="Employment observation",
                                offset=10,
                            )
                        ],
                    )
                ],
                skills=[
                    SkillEntity(
                        entity="Field A",
                        evidence=[
                            graph_evidence(
                                context=EvidenceContext.USED_IN_EMPLOYMENT,
                                source_excerpt="Skill observation",
                                offset=40,
                            )
                        ],
                    )
                ],
            )
        }
    )

    current = build_provisional_capability_profile(profile)

    assert [item.context.value for item in current.semantic_evidence] == [
        "used_in_employment",
        "used_in_employment",
    ]
    assert [item.source_kind.value for item in current.semantic_evidence] == [
        "employment",
        "skill",
    ]
    assert all(item.concepts == ("Field A",) for item in current.semantic_evidence)


def test_assessment_does_not_apply_pre_pack_aliases_to_raw_concepts() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Apache Kafka",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.USED_IN_EMPLOYMENT,
                        source_excerpt="Used Apache Kafka at work",
                    )
                ],
            )
        )
    )

    assessment = evaluate_target(
        current,
        target("role-current", requirement("kafka", terms=["Kafka"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert assessment.evidence_status.value == "not_found_in_evidence"
    assert assessment.retrieved_candidate_count == 0


def test_assessment_applies_aliases_only_from_explicit_selected_pack() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Apache Kafka",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.USED_IN_EMPLOYMENT,
                        source_excerpt="Used Apache Kafka at work",
                    )
                ],
            )
        )
    )

    assessment = evaluate_target(
        current,
        target("role-current", requirement("kafka", terms=["Kafka"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
        domain_packs=(IT_AI_PACK,),
    ).assessments[0]

    assert assessment.evidence_status.value == "supported"
    assert assessment.retrieved_candidate_count == 1
    assert assessment.eligible_candidate_count == 1


def test_selected_it_pack_preserves_core_identity_fallback_for_unknown_same_text() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Generic Capability",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.USED_IN_EMPLOYMENT,
                        source_excerpt="Used Generic Capability at work",
                    )
                ],
            )
        )
    )

    assessment = evaluate_target(
        current,
        target(
            "role-current",
            requirement("generic", terms=["Generic Capability"]),
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
        domain_packs=(IT_AI_PACK,),
    ).assessments[0]

    assert assessment.evidence_status.value == "supported"
    assert assessment.retrieved_candidate_count == 1


def test_provisional_profile_does_not_select_it_alias_pack_implicitly() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Apache Kafka",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.USED_IN_PROJECT,
                        source_excerpt="Used Apache Kafka in a project",
                    )
                ],
            )
        )
    )

    assert {item.capability_id for item in current.capabilities} == {"apache_kafka"}
    assert all(item.capability_id != "kafka" for item in current.capabilities)


def test_capability_status_does_not_override_candidate_derived_assessment() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Concept",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.USED_IN_EMPLOYMENT,
                        source_excerpt="Used Concept at work",
                        offset=10,
                    ),
                    graph_evidence(
                        context=EvidenceContext.USED_IN_EMPLOYMENT,
                        source_excerpt="No Concept production experience",
                        offset=50,
                    ),
                ],
            )
        )
    )
    assert current.capabilities[0].status is CapabilityEvidenceStatus.CONFLICTING

    assessment = evaluate_target(
        current,
        target("role-current", requirement("concept", terms=["Concept"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert assessment.evidence_status.value == "supported"
    assert assessment.retrieved_candidate_count == 2
    assert assessment.eligible_candidate_count == 2


def test_profile_labels_source_backed_partial_insufficient_and_unobserved_evidence() -> None:
    profile = accepted_graph_cv(
        SkillEntity(entity="Docker", evidence=[graph_evidence(confidence=0.91)]),
        SkillEntity(entity="FastAPI", evidence=[graph_evidence(confidence=0.4)]),
        SkillEntity(entity="Kubernetes", evidence=[graph_evidence(with_locator=False)]),
        SkillEntity(entity="Terraform"),
        SkillEntity(
            entity="Python",
            evidence=[
                graph_evidence(source_excerpt="Implemented Python services."),
                graph_evidence(source_excerpt="No Python production experience.", offset=50),
            ],
        ),
    )

    current = build_provisional_capability_profile(profile)

    assert {item.capability_id: item.status for item in current.capabilities} == {
        "docker": CapabilityEvidenceStatus.SUPPORTED,
        "fastapi": CapabilityEvidenceStatus.PARTIAL,
        "kubernetes": CapabilityEvidenceStatus.INSUFFICIENT,
        "python": CapabilityEvidenceStatus.CONFLICTING,
        "terraform": CapabilityEvidenceStatus.NOT_FOUND_IN_EVIDENCE,
    }
    assert (
        len(
            next(
                item for item in current.capabilities if item.capability_id == "python"
            ).observations
        )
        == 2
    )


def test_graph_evidence_preserves_missing_usage_as_missing_participation() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(SkillEntity(entity="Python", evidence=[graph_evidence(usage=None)]))
    )

    assert current.capabilities[0].observations[0].participation is None


def test_missing_requirement_has_empty_evidence_references_without_claiming_absence() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(SkillEntity(entity="Python", evidence=[graph_evidence()]))
    )

    analysis = evaluate_target(
        current,
        target("role-current", requirement("go", terms=["Go"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.OFFICIAL,
    )

    gap = analysis.gaps[0]
    assert gap.matched_evidence_refs == []
    assert gap.missing_signals == [
        "No matching source-backed evidence was found; this does not establish absence of capability."
    ]


def test_low_confidence_creates_gap_without_capability_status_override() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(entity="FastAPI", evidence=[graph_evidence(confidence=0.4)]),
            SkillEntity(
                entity="Python",
                evidence=[
                    graph_evidence(source_excerpt="Implemented Python services."),
                    graph_evidence(source_excerpt="No Python production experience.", offset=50),
                ],
            ),
        )
    )

    analysis = evaluate_target(
        current,
        target(
            "role-current",
            requirement("fastapi", terms=["FastAPI"]),
            requirement("python", terms=["Python"]),
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.OFFICIAL,
    )

    gaps = {gap.requirement_id: gap for gap in analysis.gaps}
    assert gaps["fastapi"].matched_evidence_refs
    assert gaps["fastapi"].missing_signals == [
        "Source-backed evidence is incomplete or below the target confidence threshold."
    ]
    assert "python" not in gaps
    python = next(item for item in analysis.assessments if item.requirement_id == "python")
    assert python.evidence_status.value == "supported"
    assert python.retrieved_candidate_count == 2
    assert python.eligible_candidate_count == 2


def test_conflict_detection_does_not_treat_nosql_as_sql() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="SQL",
                evidence=[
                    graph_evidence(source_excerpt="Built NoSQL data services."),
                    graph_evidence(source_excerpt="No SQL production experience.", offset=50),
                ],
            )
        )
    )

    assert current.capabilities[0].status is CapabilityEvidenceStatus.SUPPORTED


def test_same_requirement_has_independent_current_and_future_gaps_and_priorities() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(SkillEntity(entity="Python", evidence=[graph_evidence(confidence=0.4)]))
    )
    current_analysis = evaluate_target(
        current,
        target("role-current", requirement("python", terms=["Python"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.OFFICIAL,
    )
    future_analysis = evaluate_target(
        current,
        target("role-future", requirement("python", terms=["Python"])),
        TargetType.FUTURE_ROLE,
        TargetUsageMode.OFFICIAL,
    )

    current_gap = current_analysis.gaps[0]
    future_gap = future_analysis.gaps[0]
    assert current_gap.id != future_gap.id
    assert current_gap.target_type is TargetType.CURRENT_ROLE
    assert future_gap.target_type is TargetType.FUTURE_ROLE
    assert current_gap.missing_priority_inputs == [
        "business_impact",
        "risk",
        "frequency",
        "deadline",
        "manager_confirmation",
    ]
    assert current_gap.rationale != future_gap.rationale


def test_preview_analysis_warns_without_creating_a_combined_score() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(SkillEntity(entity="Python", evidence=[graph_evidence(confidence=0.4)]))
    )

    analysis = evaluate_target(
        current,
        target(
            "role-future",
            requirement("python", terms=["Python"]),
            status=RoleProfileStatus.PROVISIONAL,
        ),
        TargetType.FUTURE_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assert analysis.warning_codes == ["future_target_profile_provisional"]
    assert not hasattr(analysis, "combined_readiness_score")


def test_work_evidence_outranks_mention_for_generic_requirement() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Python",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.MENTIONED,
                        source_excerpt="Python.",
                        offset=10,
                    ),
                    graph_evidence(
                        context=EvidenceContext.USED_IN_EMPLOYMENT,
                        source_excerpt="Used Python at work.",
                        offset=30,
                    ),
                ],
            )
        )
    )

    assessment = evaluate_target(
        current,
        target("role-current", requirement("python", terms=["Python"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert assessment.evidence_status.value == "supported"
    assert assessment.evidence_strength.value == "work"
    assert len(assessment.matched_evidence_refs) == 1


def test_explicit_mention_requires_verification_for_generic_requirement() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Docker",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.MENTIONED,
                        source_excerpt="Docker.",
                    )
                ],
            )
        )
    )

    assessment = evaluate_target(
        current,
        target("role-current", requirement("docker", terms=["Docker"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert assessment.evidence_status.value == "requires_verification"
    assert assessment.evidence_strength.value == "mention"


def test_project_usage_supports_generic_requirement_but_not_explicit_production_requirement() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Docker",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.USED_IN_PROJECT,
                        source_excerpt="Used Docker in a capstone project.",
                    )
                ],
            )
        )
    )

    generic = evaluate_target(
        current,
        target("role-current", requirement("docker", terms=["Docker"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]
    production = evaluate_target(
        current,
        target(
            "role-current",
            requirement("docker-production", terms=["Docker", "production"]),
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert generic.evidence_status.value == "supported"
    assert generic.production_required is False
    assert production.evidence_status.value == "context_mismatch"
    assert production.production_required is True
    assert production.matched_evidence_refs


def test_work_without_production_excerpt_cannot_satisfy_production_requirement() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Docker",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.USED_IN_EMPLOYMENT,
                        source_excerpt="Used Docker for development tooling.",
                    )
                ],
            )
        )
    )

    assessment = evaluate_target(
        current,
        target(
            "role-current",
            requirement("docker-production", terms=["Docker", "production"]),
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert assessment.evidence_status.value == "context_mismatch"
    assert assessment.matched_evidence_refs


def test_production_words_in_excerpt_do_not_change_employment_context() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Docker",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.USED_IN_EMPLOYMENT,
                        source_excerpt="Operated Docker workloads in production.",
                    )
                ],
            )
        )
    )

    assessment = evaluate_target(
        current,
        target(
            "role-current",
            requirement("docker-production", terms=["Docker", "production"]),
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert assessment.evidence_status.value == "context_mismatch"
    assert assessment.evidence_strength.value == "work"


def test_source_grounded_production_context_is_eligible_for_production_requirement() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Docker",
                evidence=[
                    graph_evidence(
                        context=EvidenceContext.USED_IN_PRODUCTION,
                        source_excerpt="Operated Docker workloads in a source-labelled environment.",
                    )
                ],
            )
        )
    )

    assessment = evaluate_target(
        current,
        target(
            "role-current",
            requirement("docker-production", terms=["Docker", "production"]),
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert assessment.evidence_status.value == "supported"
    assert assessment.evidence_strength.value == "production"


def test_missing_target_level_does_not_create_a_level_gap_and_missing_evidence_is_not_absence() -> None:
    analysis = evaluate_target(
        build_provisional_capability_profile(
            accepted_graph_cv(SkillEntity(entity="Python", evidence=[graph_evidence()]))
        ),
        target("role-current", requirement("mlops", terms=["MLOps"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    assessment = analysis.assessments[0]
    gap = analysis.gaps[0]
    assert assessment.evidence_status.value == "not_found_in_evidence"
    assert all("level" not in signal.casefold() for signal in gap.missing_signals)
    assert "does not establish absence" in " ".join(gap.missing_signals).casefold()


def test_same_inputs_produce_deterministic_preview_assessment_structure() -> None:
    profile = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(
                entity="Python",
                evidence=[graph_evidence(context=EvidenceContext.USED_IN_EMPLOYMENT)],
            )
        )
    )
    role = target("role-current", requirement("python", terms=["Python"]))

    first = evaluate_target(profile, role, TargetType.CURRENT_ROLE, TargetUsageMode.PREVIEW)
    second = evaluate_target(profile, role, TargetType.CURRENT_ROLE, TargetUsageMode.PREVIEW)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_preview_readiness_and_verification_queue_are_explicitly_provisional() -> None:
    analysis = evaluate_target(
        build_provisional_capability_profile(
            accepted_graph_cv(
                SkillEntity(
                    entity="Docker",
                    evidence=[graph_evidence(context=EvidenceContext.MENTIONED)],
                )
            )
        ),
        target("role-current", requirement("docker", terms=["Docker"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    )

    readiness = build_preview_readiness(analysis)
    queue = build_verification_queue(analysis)

    assert readiness.analysis_mode is TargetUsageMode.PREVIEW
    assert readiness.final_competency_decision_prohibited is True
    assert readiness.capability_verification_status == "provisional"
    assert not hasattr(readiness, "combined_readiness_score")
    assert [item.status.value for item in queue] == ["recommended"]
    assert all(item.status.value != "verified" for item in queue)


def test_overlap_links_use_shared_evidence_keys_without_merging_gaps() -> None:
    current = build_provisional_capability_profile(
        accepted_graph_cv(
            SkillEntity(entity="Python", evidence=[graph_evidence(confidence=0.4)]),
            SkillEntity(
                entity="FastAPI",
                evidence=[graph_evidence(confidence=0.4, offset=50)],
            ),
        )
    )
    different_id_same_evidence_current = evaluate_target(
        current,
        target("role-current", requirement("python-depth", terms=["Python"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.OFFICIAL,
    )
    different_id_same_evidence_future = evaluate_target(
        current,
        target("role-future", requirement("python-api", terms=["Python"])),
        TargetType.FUTURE_ROLE,
        TargetUsageMode.OFFICIAL,
    )
    same_id_different_evidence_current = evaluate_target(
        current,
        target("role-current", requirement("runtime-framework", terms=["Python"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.OFFICIAL,
    )
    same_id_different_evidence_future = evaluate_target(
        current,
        target("role-future", requirement("runtime-framework", terms=["FastAPI"])),
        TargetType.FUTURE_ROLE,
        TargetUsageMode.OFFICIAL,
    )
    no_evidence_go_current = evaluate_target(
        current,
        target("role-current", requirement("go-foundations", terms=["Go"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.OFFICIAL,
    )
    no_evidence_go_future = evaluate_target(
        current,
        target("role-future", requirement("go-practice", terms=["GO"])),
        TargetType.FUTURE_ROLE,
        TargetUsageMode.OFFICIAL,
    )
    unrelated_no_evidence_future = evaluate_target(
        current,
        target("role-future", requirement("ruby-practice", terms=["Ruby"])),
        TargetType.FUTURE_ROLE,
        TargetUsageMode.OFFICIAL,
    )

    links = build_gap_overlap_links(
        different_id_same_evidence_current, different_id_same_evidence_future
    )

    assert len(links) == 1
    assert (links[0].source_gap_id, links[0].target_gap_id, links[0].shared_theme) == (
        different_id_same_evidence_current.gaps[0].id,
        different_id_same_evidence_future.gaps[0].id,
        "python",
    )
    assert (
        build_gap_overlap_links(
            same_id_different_evidence_current, same_id_different_evidence_future
        )
        == []
    )
    assert (
        different_id_same_evidence_current.gaps[0].id
        != different_id_same_evidence_future.gaps[0].id
    )
    assert [
        (link.source_gap_id, link.target_gap_id, link.shared_theme)
        for link in build_gap_overlap_links(no_evidence_go_current, no_evidence_go_future)
    ] == [
        (
            no_evidence_go_current.gaps[0].id,
            no_evidence_go_future.gaps[0].id,
            "go",
        )
    ]
    assert build_gap_overlap_links(no_evidence_go_current, unrelated_no_evidence_future) == []
