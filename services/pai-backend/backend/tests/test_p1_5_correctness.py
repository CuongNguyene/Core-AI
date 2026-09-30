from typing import Literal

from app.capability_analysis.domain_packs.it_ai import IT_AI_PACK
from app.capability_analysis.rules import evaluate_target
from app.capability_analysis.schemas import (
    CapabilityEvidenceStatus,
    CapabilityObservation,
    CapabilitySourceLocator,
    ProvisionalCapability,
    ProvisionalCurrentCapabilityProfile,
    TargetType,
    TargetUsageMode,
    VerificationStatus,
)
from app.capability_analysis.semantic_core.contracts import (
    EvidenceExpectation,
    EvidenceSemantics,
    EvidenceSourceKind,
    RequirementSemantics,
    SemanticContext,
    SemanticSourceLocator,
)
from app.capability_analysis.semantic_core.retrieval import assess_retrieval, retrieve_candidates
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)


def _locator() -> SemanticSourceLocator:
    return SemanticSourceLocator(
        document_id="cv-1",
        section="experience",
        start_offset=10,
        end_offset=40,
    )


def _evidence(
    ref: str,
    concepts: tuple[str, ...],
    *,
    context: SemanticContext = SemanticContext.USED_IN_EMPLOYMENT,
    source_kind: EvidenceSourceKind = EvidenceSourceKind.EMPLOYMENT,
    confidence: float = 0.95,
    excerpt: str = "Source-backed claim",
    participation: str | None = "implemented",
) -> EvidenceSemantics:
    return EvidenceSemantics(
        evidence_ref=ref,
        concepts=concepts,
        behaviors=(),
        objects=(),
        context=context,
        participation=participation,
        source_kind=source_kind,
        confidence=confidence,
        original_evidence_type="work_experience",
        source_locator=_locator(),
        source_value=concepts[0],
        source_excerpt=excerpt,
        provenance=(("source", "fixture"),),
        unresolved_fields=(),
    )


def _requirement(
    requirement_id: str,
    terms: list[str],
    *,
    dimension: CriterionDimension = CriterionDimension.SKILL,
    confidence_threshold: float = 0.8,
    logical_operator: Literal["AND", "OR"] = "AND",
    evidence_expectation: Literal[
        "demonstrated_usage", "education", "credential", "owned_outcome", "unknown"
    ]
    | None = None,
    threshold_source: str = "policy_default",
    threshold_policy_id: str | None = "capability-assessment-default",
    threshold_policy_version: str | None = "1",
) -> RoleRequirement:
    return RoleRequirement(
        id=requirement_id,
        criterion_dimension=dimension,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=terms,
        confidence_threshold=confidence_threshold,
        assessment_recommendation="review",
        rubric_version="rubric-v1",
        logical_operator=logical_operator,
        evidence_expectation=evidence_expectation,
        threshold_source=threshold_source,
        threshold_policy_id=threshold_policy_id,
        threshold_policy_version=threshold_policy_version,
    )


def _target(requirement: RoleRequirement) -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id="role-current",
        version="1.0",
        status=RoleProfileStatus.ACTIVE,
        source_jd_profile_id="jd-1",
        source_jd_profile_version=1,
        rule_set_version="rules-v1",
        policy_version="policy-v1",
        requirements=[requirement],
    )


def _profile(*evidence: EvidenceSemantics) -> ProvisionalCurrentCapabilityProfile:
    observation = CapabilityObservation(
        evidence_ref="capability-observation",
        source_locator=CapabilitySourceLocator(
            document_id="cv-1",
            section="experience",
            start_offset=10,
            end_offset=40,
        ),
        environment="employment",
        context="used_in_employment",
        participation="implemented",
        confidence=0.95,
    )
    capability = ProvisionalCapability(
        capability_id="fixture",
        status=CapabilityEvidenceStatus.SUPPORTED,
        verification_status=VerificationStatus.PROVISIONAL,
        observations=(observation,),
    )
    return ProvisionalCurrentCapabilityProfile(
        source_profile_id="cv-profile-1",
        source_profile_version=1,
        capabilities=(capability,),
        semantic_evidence=evidence,
    )


def test_education_support_is_direct_and_verification_is_separate() -> None:
    requirement = RequirementSemantics(
        requirement_id="degree",
        concepts=("data science",),
        behaviors=(),
        objects=(),
        constraints=(),
        evidence_expectation=EvidenceExpectation.EDUCATION,
        source_requirement_ref="jd-degree",
        source_locator=None,
        provenance=(),
        unresolved_fields=(),
    )
    result = assess_retrieval(
        requirement,
        retrieve_candidates(
            requirement,
            (
                _evidence(
                    "degree-education",
                    ("data science",),
                    context=SemanticContext.STUDIED,
                    source_kind=EvidenceSourceKind.EDUCATION,
                    excerpt="BS in Data Science",
                ),
            ),
        ),
        0.8,
    )

    assert result.status.value == "supported"
    assert result.eligible_candidate_count == 1
    assert result.decision_details.evidence_directness == "direct"
    assert result.decision_details.verification_required is True


def test_education_evidence_does_not_satisfy_demonstrated_work_requirement() -> None:
    requirement = RequirementSemantics(
        requirement_id="practice",
        concepts=("ifrs",),
        behaviors=(),
        objects=(),
        constraints=(),
        evidence_expectation=EvidenceExpectation.DEMONSTRATED_USAGE,
        source_requirement_ref="jd-practice",
        source_locator=None,
        provenance=(),
        unresolved_fields=(),
    )
    result = assess_retrieval(
        requirement,
        retrieve_candidates(
            requirement,
            (
                _evidence(
                    "ifrs-education",
                    ("ifrs",),
                    context=SemanticContext.STUDIED,
                    source_kind=EvidenceSourceKind.EDUCATION,
                ),
            ),
        ),
        0.8,
    )

    assert result.eligible_candidate_count == 0
    assert result.decision_details.reason_codes == ("EVIDENCE_TYPE_INCOMPATIBLE",)


def test_credential_requirement_is_direct_but_still_provisional() -> None:
    requirement = RequirementSemantics(
        requirement_id="credential",
        concepts=("cpa",),
        behaviors=(),
        objects=(),
        constraints=(),
        evidence_expectation=EvidenceExpectation.CREDENTIAL,
        source_requirement_ref="jd-credential",
        source_locator=None,
        provenance=(),
        unresolved_fields=(),
    )
    result = assess_retrieval(
        requirement,
        retrieve_candidates(
            requirement,
            (
                _evidence(
                    "cpa-credential",
                    ("cpa",),
                    context=SemanticContext.CREDENTIALED,
                    source_kind=EvidenceSourceKind.CREDENTIAL,
                    excerpt="CPA credential",
                ),
            ),
        ),
        0.8,
    )

    assert result.status.value == "supported"
    assert result.decision_details.evidence_directness == "direct"
    assert result.decision_details.verification_required is True


def test_shared_locator_does_not_make_sibling_claims_tensorflow_matches() -> None:
    shared_excerpt = "Python, PyTorch, TensorFlow, SQL"
    evidence = tuple(
        _evidence(
            name,
            (name,),
            excerpt=shared_excerpt,
        )
        for name in ("Python", "PyTorch", "TensorFlow", "SQL")
    )
    profile = _profile(*evidence)
    result = evaluate_target(
        profile,
        _target(_requirement("tensorflow", ["TensorFlow"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
        domain_packs=(IT_AI_PACK,),
    ).assessments[0]

    assert result.retrieved_candidate_count == 1
    assert result.eligible_candidate_count == 1
    assert result.matched_evidence_refs == ["TensorFlow"]


def test_shared_locator_does_not_make_sibling_claims_docker_matches() -> None:
    shared_excerpt = "Azure, Docker, Git, Slurm"
    evidence = tuple(
        _evidence(name, (name,), excerpt=shared_excerpt)
        for name in ("Azure", "Docker", "Git", "Slurm")
    )
    profile = _profile(*evidence)
    result = evaluate_target(
        profile,
        _target(_requirement("docker", ["Docker"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
        domain_packs=(IT_AI_PACK,),
    ).assessments[0]

    assert result.retrieved_candidate_count == 1
    assert result.matched_evidence_refs == ["Docker"]


def test_claim_isolation_preserves_explicit_apache_kafka_alias() -> None:
    evidence = (
        _evidence("apache-kafka", ("Apache Kafka",), excerpt="Apache Kafka and Apache Spark"),
        _evidence("spark", ("Spark",), excerpt="Apache Kafka and Apache Spark"),
    )
    profile = _profile(*evidence)
    result = evaluate_target(
        profile,
        _target(_requirement("kafka", ["Kafka"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
        domain_packs=(IT_AI_PACK,),
    ).assessments[0]

    assert result.retrieved_candidate_count == 1
    assert result.matched_evidence_refs == ["apache-kafka"]


def test_context_mismatch_exposes_the_authored_constraint() -> None:
    result = evaluate_target(
        _profile(
            _evidence(
                "deployment-project",
                ("deployment",),
                context=SemanticContext.USED_IN_PROJECT,
                source_kind=EvidenceSourceKind.PROJECT,
            )
        ),
        _target(_requirement("production-deployment", ["deployment", "production"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert result.evidence_status.value == "context_mismatch"
    assert "EVIDENCE_CONTEXT_MISMATCH" in result.decision_details.reason_codes


def test_explicit_mention_exposes_verification_reason() -> None:
    result = evaluate_target(
        _profile(
            _evidence(
                "docker-mention",
                ("Docker",),
                context=SemanticContext.MENTIONED,
                source_kind=EvidenceSourceKind.SKILL,
                participation=None,
                excerpt="Docker",
            )
        ),
        _target(_requirement("docker", ["Docker"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
        domain_packs=(IT_AI_PACK,),
    ).assessments[0]

    assert result.evidence_status.value == "requires_verification"
    assert "EXPLICIT_MENTION_ONLY" in result.decision_details.reason_codes
    assert "EVIDENCE_TYPE_INCOMPATIBLE" in result.decision_details.reason_codes


def test_not_found_assessment_exposes_structured_reason() -> None:
    result = evaluate_target(
        _profile(),
        _target(_requirement("mlops", ["MLOps"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert result.evidence_status.value == "not_found_in_evidence"
    assert "NO_RELEVANT_EVIDENCE" in result.decision_details.reason_codes


def test_confidence_insufficient_exposes_observed_and_required_thresholds() -> None:
    result = evaluate_target(
        _profile(_evidence("python", ("Python",), confidence=0.6)),
        _target(_requirement("python", ["Python"], confidence_threshold=0.8)),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert result.evidence_status.value == "insufficient"
    assert "CONFIDENCE_BELOW_THRESHOLD" in result.decision_details.reason_codes
    assert result.decision_details.observed_confidence == 0.6
    assert result.decision_details.required_confidence == 0.8


def test_python_work_support_has_no_invented_target_signal() -> None:
    result = evaluate_target(
        _profile(_evidence("python-work", ("Python",), confidence=0.95)),
        _target(_requirement("python", ["Python"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert result.evidence_status.value == "supported"
    assert result.decision_details.missing_signals == []
    assert result.decision_details.evidence_directness == "direct"
    assert result.decision_details.reason_codes == []


def test_or_group_data_science_satisfies_one_of_education_fields() -> None:
    result = evaluate_target(
        _profile(
            _evidence(
                "data-science-degree",
                ("data science",),
                context=SemanticContext.STUDIED,
                source_kind=EvidenceSourceKind.EDUCATION,
                excerpt="BS in Data Science",
            )
        ),
        _target(
            _requirement(
                "degree-field",
                ["computer science", "ai", "machine learning", "data science", "equivalent"],
                dimension=CriterionDimension.EDUCATION,
                logical_operator="OR",
            )
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert result.evidence_status.value == "supported"
    assert result.decision_details.supported_signals == ["data science"]
    assert result.decision_details.missing_signals == []


def test_confidence_threshold_provenance_explains_explicit_one_point_zero_policy() -> None:
    result = evaluate_target(
        _profile(_evidence("python-work", ("Python",), confidence=0.95)),
        _target(
            _requirement(
                "python",
                ["Python"],
                confidence_threshold=1.0,
                threshold_source="assessment_policy",
                threshold_policy_id="strict-preview-policy",
                threshold_policy_version="3",
            )
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert result.evidence_status.value == "insufficient"
    assert result.decision_details.observed_confidence == 0.95
    assert result.decision_details.required_confidence == 1.0
    assert result.decision_details.threshold_source == "assessment_policy"
    assert result.decision_details.threshold_policy_id == "strict-preview-policy"
    assert result.decision_details.threshold_policy_version == "3"


def test_plain_capability_requirement_does_not_invent_usage_constraint() -> None:
    plain = evaluate_target(
        _profile(
            _evidence(
                "docker-mention",
                ("Docker",),
                context=SemanticContext.MENTIONED,
                source_kind=EvidenceSourceKind.SKILL,
                participation=None,
                excerpt="Docker",
            )
        ),
        _target(_requirement("docker", ["Docker"])),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]
    demonstrated = evaluate_target(
        _profile(
            _evidence(
                "docker-mention",
                ("Docker",),
                context=SemanticContext.MENTIONED,
                source_kind=EvidenceSourceKind.SKILL,
                participation=None,
                excerpt="Docker",
            )
        ),
        _target(
            _requirement(
                "docker-usage",
                ["Docker"],
                evidence_expectation="demonstrated_usage",
            )
        ),
        TargetType.CURRENT_ROLE,
        TargetUsageMode.PREVIEW,
    ).assessments[0]

    assert plain.retrieved_candidate_count == 1
    assert plain.eligible_candidate_count == 1
    assert plain.evidence_status.value == "requires_verification"
    assert demonstrated.retrieved_candidate_count == 1
    assert demonstrated.eligible_candidate_count == 0
    assert demonstrated.evidence_status.value == "requires_verification"
