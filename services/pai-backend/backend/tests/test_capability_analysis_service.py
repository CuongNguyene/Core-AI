from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.authorization.fixtures import LEARNER_ID, ORG_PAI_ID, REVIEWER_ID, SME_ID
from app.authorization.schemas import ActorContext, Role
from app.capability_analysis import service as capability_analysis_service_module
from app.capability_analysis.domain_packs.contracts import DomainPackReference
from app.capability_analysis.domain_packs.it_ai import IT_AI_PACK
from app.capability_analysis.domain_packs.registry import DomainPackRegistry
from app.capability_analysis.errors import (
    CandidateProfileNotAnalyzableError,
    CapabilityAnalysisAccessDeniedError,
    ExtractionProfileNotAcceptedError,
    FutureTargetNotUsableError,
    HumanAssistedReanalysisValidationError,
    SemanticPolicyNotConfiguredError,
    SemanticPolicyUnavailableError,
)
from app.capability_analysis.repository import InMemoryCapabilityGapPortfolioRepository
from app.capability_analysis.rules import build_provisional_capability_profile
from app.capability_analysis.schemas import (
    CreateCapabilityGapAnalysisRequest,
    HumanAssistedEvidenceSelection,
    TargetType,
    TargetUsageMode,
)
from app.capability_analysis.service import CapabilityGapAnalysisService
from app.extraction.evidence import EvidenceContext, EvidenceItem
from app.extraction.locators import SourceLocator
from app.extraction.profile import CandidateProfile, SkillEntity
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.schemas import (
    CVExtractionOutput,
    DocumentKind,
    ExtractionJob,
    ExtractionProfile,
    JDExtractionOutput,
    JobStatus,
    ReviewState,
)
from app.matching.repository import InMemoryRoleProfileRepository
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleProfileSemanticPolicy,
    RoleProfileSemanticPolicyMapping,
    RoleProfileStatus,
    RoleRequirement,
    SemanticPolicySelectionSource,
)
from app.semantic_policy.repository import InMemorySemanticPolicyRepository
from app.semantic_policy.schemas import SemanticPolicy, SemanticPolicyRef, SemanticPolicyStatus
from app.semantic_policy.service import SemanticPolicyResolver
from tests.test_matching_repository import active_role

TEST_SEMANTIC_POLICY = RoleProfileSemanticPolicy(
    core_version="semantic-core-v1",
    pack_refs=(DomainPackReference(pack_id="it_ai", version="1"),),
)


def learner() -> ActorContext:
    return ActorContext(
        actor_id=LEARNER_ID, organization_id=ORG_PAI_ID, roles=frozenset({Role.LEARNER})
    )


def reviewer() -> ActorContext:
    return ActorContext(
        actor_id=REVIEWER_ID, organization_id=ORG_PAI_ID, roles=frozenset({Role.REVIEWER})
    )


def request(
    *, current: str = "role-current", future: str | None = None
) -> CreateCapabilityGapAnalysisRequest:
    return CreateCapabilityGapAnalysisRequest(
        cv_profile_id="cv-profile-1",
        current_target_profile_id=current,
        future_target_profile_id=future,
        correlation_id="capability-correlation-1",
    )


def accepted_cv(state: ReviewState = ReviewState.ACCEPTED) -> ExtractionProfile:
    return ExtractionProfile(
        id="cv-profile-1",
        job_id="cv-job-1",
        document_id="cv-document-1",
        document_kind=DocumentKind.CV,
        owner_actor_id=LEARNER_ID,
        version=3,
        review_state=state,
        accepted_by=REVIEWER_ID if state is ReviewState.ACCEPTED else None,
        accepted_at=(
            datetime(2026, 8, 6, tzinfo=UTC)
            if state is ReviewState.ACCEPTED
            else None
        ),
        output=CVExtractionOutput(skills=[], experience=[], education=[]),
        candidate_profile=CandidateProfile(
            skills=[
                SkillEntity(
                    entity="Python",
                    evidence=[
                        EvidenceItem(
                            context=EvidenceContext.USED_IN_PRODUCTION,
                            usage="implemented",
                            source_excerpt="Implemented Python services.",
                            confidence=0.91,
                            source_locator=SourceLocator(
                                document_id="cv-document-1",
                                section="experience",
                                start_offset=0,
                                end_offset=28,
                            ),
                        )
                    ],
                )
            ]
        ),
        audit={},
    )


def accepted_jd() -> ExtractionProfile:
    return ExtractionProfile(
        id="jd-profile-1",
        job_id="jd-job-1",
        document_id="jd-document-1",
        document_kind=DocumentKind.JD,
        owner_actor_id=REVIEWER_ID,
        version=1,
        review_state=ReviewState.ACCEPTED,
        accepted_by=REVIEWER_ID,
        accepted_at=datetime(2026, 8, 6, tzinfo=UTC),
        output=JDExtractionOutput(required_skills=[], responsibilities=[], qualifications=[]),
        audit={},
    )


async def service_with(
    *,
    cv_state: ReviewState = ReviewState.ACCEPTED,
    roles_statuses: list[RoleProfileStatus] | None = None,
    semantic_policy: RoleProfileSemanticPolicy | None = TEST_SEMANTIC_POLICY,
    semantic_policy_mappings: tuple[RoleProfileSemanticPolicyMapping, ...] = (),
    pack_registry: DomainPackRegistry | None = None,
    target_requirements: list[RoleRequirement] | None = None,
) -> tuple[
    CapabilityGapAnalysisService,
    InMemoryExtractionRepository,
    InMemoryCapabilityGapPortfolioRepository,
]:
    extraction = InMemoryExtractionRepository()
    for job, profile in (("cv-job-1", accepted_cv(cv_state)), ("jd-job-1", accepted_jd())):
        await extraction.enqueue(
            ExtractionJob(
                id=job,
                document_id=profile.document_id,
                document_kind=profile.document_kind,
                owner_actor_id=profile.owner_actor_id,
                correlation_id=f"corr-{job}",
                status=JobStatus.QUEUED,
            )
        )
        await extraction.mark_succeeded(job, profile)
    statuses = roles_statuses or [RoleProfileStatus.ACTIVE]
    roles = [
        active_role().model_copy(
            update={
                "id": "role-current",
                "version": str(index + 1),
                "status": status,
                "semantic_policy": semantic_policy,
                "requirements": target_requirements or active_role().requirements,
            }
        )
        for index, status in enumerate(statuses)
    ]
    portfolios = InMemoryCapabilityGapPortfolioRepository()
    return (
        CapabilityGapAnalysisService(
            extraction,
            InMemoryRoleProfileRepository(
                roles,
                semantic_policy_mappings=semantic_policy_mappings,
            ),
            portfolios,
            domain_pack_registry=pack_registry or DomainPackRegistry((IT_AI_PACK,)),
        ),
        extraction,
        portfolios,
    )


@pytest.mark.asyncio
async def test_current_provisional_target_is_allowed_with_warning() -> None:
    service, _, _ = await service_with(roles_statuses=[RoleProfileStatus.PROVISIONAL])

    portfolio = await service.create(request(), learner())

    assert portfolio.current_role.usage_mode is TargetUsageMode.PREVIEW
    assert portfolio.current_role.warning_codes == ["current_target_profile_provisional"]
    assert portfolio.snapshot_schema_version == "capability-gap-preview-v1"
    assert portfolio.preview_readiness is not None
    assert portfolio.preview_readiness.analysis_mode is TargetUsageMode.PREVIEW
    assert portfolio.preview_readiness.final_competency_decision_prohibited is True
    assert all(item.status.value in {"pending", "recommended"} for item in portfolio.verification_queue)


@pytest.mark.asyncio
async def test_human_assisted_reanalysis_creates_new_analysis_from_exact_source_versions() -> None:
    requirements = [
        RoleRequirement(
            id="requirement-python",
            criterion_dimension=CriterionDimension.SKILL,
            classification=RequirementClassification.ROLE_CRITICAL,
            evidence_terms=["Python"],
            confidence_threshold=0.8,
            assessment_recommendation="practical_task",
            rubric_version="rubric-v1",
        )
    ]
    service, extraction, portfolios = await service_with(
        roles_statuses=[RoleProfileStatus.PROVISIONAL], target_requirements=requirements
    )
    source = await service.create(
        request(),
        learner(),
        candidate_id=uuid4(),
        idempotency_key="source-analysis-1",
    )
    cv_profile = await extraction.get_profile("cv-profile-1")
    assert cv_profile is not None
    evidence_ref = build_provisional_capability_profile(cv_profile).semantic_evidence[0].evidence_ref

    result = await service.create_human_assisted_reanalysis(
        source_analysis_id=source.id,
        evidence_selections=[
            HumanAssistedEvidenceSelection(
                requirement_id="requirement-python",
                selected_evidence_refs=[evidence_ref],
            )
        ],
        actor=reviewer(),
        idempotency_key="assisted-analysis-1",
    )

    assert result.analysis.id != source.id
    assert result.analysis.cv_profile_id == source.cv_profile_id
    assert result.analysis.cv_profile_version == source.cv_profile_version
    assert result.analysis.current_target_version == source.current_target_version
    assert result.provenance.source_analysis_id == source.id
    assert result.analysis.current_role.assessments[0].matched_evidence_refs == [evidence_ref]
    assert await portfolios.get(source.id) == source

    retry = await service.create_human_assisted_reanalysis(
        source_analysis_id=source.id,
        evidence_selections=[
            HumanAssistedEvidenceSelection(
                requirement_id="requirement-python",
                selected_evidence_refs=[evidence_ref],
            )
        ],
        actor=reviewer(),
        idempotency_key="assisted-analysis-1",
    )

    assert retry.analysis.id == result.analysis.id
    assert len(
        [
            event
            for event in portfolios.audit_events
            if event["action"] == "CAPABILITY_GAP_HUMAN_ASSISTED_REANALYSIS_CREATED"
        ]
    ) == 1


async def _assisted_fixture(
    *, target_requirements: list[RoleRequirement] | None = None
) -> tuple[
    CapabilityGapAnalysisService,
    InMemoryExtractionRepository,
    InMemoryCapabilityGapPortfolioRepository,
    str,
    str,
]:
    service, extraction, portfolios = await service_with(target_requirements=target_requirements)
    source = await service.create(
        request(), learner(), candidate_id=uuid4(), idempotency_key="assisted-source"
    )
    profile = await extraction.get_profile(source.cv_profile_id)
    assert profile is not None
    ref = build_provisional_capability_profile(profile).semantic_evidence[0].evidence_ref
    return service, extraction, portfolios, source.id, ref


@pytest.mark.asyncio
async def test_human_assisted_reanalysis_rejects_unknown_evidence_ref() -> None:
    service, _, _, source_id, _ = await _assisted_fixture()

    with pytest.raises(HumanAssistedReanalysisValidationError):
        await service.create_human_assisted_reanalysis(
            source_analysis_id=source_id,
            evidence_selections=[
                HumanAssistedEvidenceSelection(
                    requirement_id="python",
                    selected_evidence_refs=["unknown-evidence"],
                )
            ],
            actor=learner(),
            idempotency_key="assisted-invalid-evidence",
        )


@pytest.mark.asyncio
async def test_human_assisted_reanalysis_rejects_requirement_outside_source_scope() -> None:
    service, _, _, source_id, ref = await _assisted_fixture()

    with pytest.raises(HumanAssistedReanalysisValidationError):
        await service.create_human_assisted_reanalysis(
            source_analysis_id=source_id,
            evidence_selections=[
                HumanAssistedEvidenceSelection(
                    requirement_id="requirement-not-in-role",
                    selected_evidence_refs=[ref],
                )
            ],
            actor=learner(),
            idempotency_key="assisted-invalid-requirement",
        )


@pytest.mark.asyncio
async def test_human_assisted_reanalysis_rejects_context_only_requirement() -> None:
    responsibility = RoleRequirement(
        id="responsibility-only",
        criterion_dimension=None,
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=["Prepare reports"],
        confidence_threshold=0.8,
        assessment_recommendation="review",
        rubric_version="rubric-v1",
        modality="RESPONSIBILITY",
    )
    service, _, _, source_id, ref = await _assisted_fixture(target_requirements=[responsibility])

    with pytest.raises(HumanAssistedReanalysisValidationError):
        await service.create_human_assisted_reanalysis(
            source_analysis_id=source_id,
            evidence_selections=[
                HumanAssistedEvidenceSelection(
                    requirement_id="responsibility-only",
                    selected_evidence_refs=[ref],
                )
            ],
            actor=learner(),
            idempotency_key="assisted-invalid-context",
        )


@pytest.mark.asyncio
async def test_empty_accepted_cv_profile_is_not_reported_as_idempotency_conflict() -> None:
    service, extraction, _ = await service_with()
    profile = await extraction.get_profile("cv-profile-1")
    assert profile is not None
    extraction._profiles[profile.id] = profile.model_copy(  # type: ignore[attr-defined]
        update={"candidate_profile": CandidateProfile()}, deep=True
    )

    with pytest.raises(CandidateProfileNotAnalyzableError):
        await service.create(
            request(),
            learner(),
            idempotency_key="empty-capabilities-001",
        )


@pytest.mark.asyncio
async def test_canonical_profile_adapter_does_not_run_a_second_current_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, _ = await service_with()
    original_evaluate_target = capability_analysis_service_module.evaluate_target
    evaluations = 0

    def count_and_evaluate(*args: object, **kwargs: object) -> object:
        nonlocal evaluations
        evaluations += 1
        return original_evaluate_target(*args, **kwargs)

    monkeypatch.setattr(capability_analysis_service_module, "evaluate_target", count_and_evaluate)

    portfolio = await service.create(request(), learner())

    assert evaluations == 1
    assert portfolio.current_role.assessments


@pytest.mark.asyncio
async def test_evidence_for_gap_resolves_canonical_semantic_reference() -> None:
    requirements = [
        active_role().requirements[0].model_copy(update={"confidence_threshold": 1.0}),
        RoleRequirement(
            id="missing-kubernetes",
            criterion_dimension=CriterionDimension.SKILL,
            classification=RequirementClassification.PREFERRED,
            evidence_terms=["Kubernetes"],
            confidence_threshold=0.8,
            assessment_recommendation="practical_task",
            rubric_version="1.0",
        ),
    ]
    service, _, _ = await service_with(target_requirements=requirements)
    portfolio = await service.create(request(), learner())
    gap = next((item for item in portfolio.current_role.gaps if item.matched_evidence_refs), None)

    assert gap is not None
    items = await service.evidence_for_gap(portfolio, gap.id)

    assert items
    assert {item.evidence_ref for item in items} == set(gap.matched_evidence_refs)
    assert all(item.source_excerpt for item in items)


@pytest.mark.asyncio
async def test_evidence_for_gap_with_no_references_returns_empty() -> None:
    requirements = [
        RoleRequirement(
            id="missing-kubernetes",
            criterion_dimension=CriterionDimension.SKILL,
            classification=RequirementClassification.PREFERRED,
            evidence_terms=["Kubernetes"],
            confidence_threshold=0.8,
            assessment_recommendation="practical_task",
            rubric_version="1.0",
        )
    ]
    service, _, _ = await service_with(target_requirements=requirements)
    portfolio = await service.create(request(), learner())
    gap = next((item for item in portfolio.current_role.gaps if not item.matched_evidence_refs), None)

    assert gap is not None
    assert await service.evidence_for_gap(portfolio, gap.id) == ()


@pytest.mark.asyncio
async def test_current_and_future_targets_resolve_independent_explicit_policy_versions() -> None:
    extraction = InMemoryExtractionRepository()
    for job, profile in (("cv-job-1", accepted_cv()), ("jd-job-1", accepted_jd())):
        await extraction.enqueue(
            ExtractionJob(
                id=job,
                document_id=profile.document_id,
                document_kind=profile.document_kind,
                owner_actor_id=profile.owner_actor_id,
                correlation_id=f"corr-{job}",
                status=JobStatus.QUEUED,
            )
        )
        await extraction.mark_succeeded(job, profile)
    current_ref = SemanticPolicyRef(policy_id="current-policy", policy_version="1")
    future_ref = SemanticPolicyRef(policy_id="future-policy", policy_version="2")
    policy_repository = InMemorySemanticPolicyRepository(
        [
            SemanticPolicy(
                policy_id="current-policy",
                version="1",
                status=SemanticPolicyStatus.ACTIVE,
                domain_pack_id="it_ai",
                domain_pack_version="1",
                domain_pack_checksum=IT_AI_PACK.checksum,
                description="current",
            ),
            SemanticPolicy(
                policy_id="future-policy",
                version="2",
                status=SemanticPolicyStatus.ACTIVE,
                domain_pack_id="it_ai",
                domain_pack_version="1",
                domain_pack_checksum=IT_AI_PACK.checksum,
                description="future",
            ),
        ]
    )
    current = active_role().model_copy(
        update={
            "id": "role-current",
            "semantic_policy": None,
            "semantic_policy_ref": current_ref,
        }
    )
    future = active_role().model_copy(
        update={
            "id": "role-future",
            "semantic_policy": None,
            "semantic_policy_ref": future_ref,
        }
    )
    service = CapabilityGapAnalysisService(
        extraction,
        InMemoryRoleProfileRepository([current, future]),
        InMemoryCapabilityGapPortfolioRepository(),
        domain_pack_registry=DomainPackRegistry((IT_AI_PACK,)),
        semantic_policy_resolver=SemanticPolicyResolver(
            policy_repository, (IT_AI_PACK,)
        ),
    )

    portfolio = await service.create(request(future="role-future"), learner())

    assert [(item.policy_id, item.policy_version) for item in portfolio.semantic_policies] == [
        ("current-policy", "1"),
        ("future-policy", "2"),
    ]


@pytest.mark.asyncio
async def test_future_provisional_target_is_preview_with_warning() -> None:
    service, _, _ = await service_with(roles_statuses=[RoleProfileStatus.ACTIVE])
    service._role_profiles._profiles.append(  # type: ignore[attr-defined]
        active_role().model_copy(
            update={
                "id": "role-future",
                "status": RoleProfileStatus.PROVISIONAL,
                "semantic_policy": TEST_SEMANTIC_POLICY,
            }
        )
    )

    portfolio = await service.create(request(future="role-future"), learner())

    assert portfolio.future_role is not None
    assert portfolio.future_role.usage_mode is TargetUsageMode.PREVIEW
    assert portfolio.future_role.warning_codes == ["future_target_profile_provisional"]


@pytest.mark.asyncio
async def test_future_draft_target_is_rejected_without_persisting_portfolio() -> None:
    service, _, portfolios = await service_with(roles_statuses=[RoleProfileStatus.ACTIVE])
    service._role_profiles._profiles.append(  # type: ignore[attr-defined]
        active_role().model_copy(update={"id": "role-future", "status": RoleProfileStatus.DRAFT})
    )

    with pytest.raises(FutureTargetNotUsableError):
        await service.create(request(future="role-future"), learner())

    assert await portfolios.get("capability-correlation-1") is None
    assert portfolios.audit_events[-1]["action"] == "CAPABILITY_GAP_REJECTED_FUTURE_TARGET"


@pytest.mark.asyncio
async def test_service_rejects_unaccepted_or_non_owner_cv_before_persisting() -> None:
    service, _, portfolios = await service_with(cv_state=ReviewState.PENDING_REVIEW)

    with pytest.raises(ExtractionProfileNotAcceptedError):
        await service.create(request(), learner())
    assert await portfolios.get("capability-correlation-1") is None

    owned_service, _, _ = await service_with()
    with pytest.raises(CapabilityAnalysisAccessDeniedError):
        await owned_service.create(request(), reviewer())


@pytest.mark.asyncio
async def test_service_read_allows_owner_only() -> None:
    service, _, _ = await service_with()
    created = await service.create(request(), learner())

    restored = await service.get(created.id, learner())

    assert restored == created
    with pytest.raises(CapabilityAnalysisAccessDeniedError):
        await service.get(
            created.id,
            ActorContext(
                actor_id=SME_ID,
                organization_id=ORG_PAI_ID,
                roles=frozenset({Role.LEARNER}),
            ),
        )


@pytest.mark.asyncio
async def test_service_read_allows_same_organization_reviewer_only() -> None:
    service, _, _ = await service_with()
    created = await service.create(request(), learner())
    other_organization_reviewer = ActorContext(
        actor_id=REVIEWER_ID,
        organization_id=uuid4(),
        roles=frozenset({Role.REVIEWER}),
    )

    assert await service.get(created.id, reviewer()) == created
    with pytest.raises(CapabilityAnalysisAccessDeniedError):
        await service.get(created.id, other_organization_reviewer)


@pytest.mark.asyncio
async def test_profile_metadata_policy_is_snapshotted_without_mutating_cv() -> None:
    service, extraction, _ = await service_with()
    before = await extraction.get_profile("cv-profile-1")
    assert before is not None
    before_payload = before.model_dump(mode="json")

    created = await service.create(request(), learner())

    after = await extraction.get_profile("cv-profile-1")
    assert len(created.semantic_policies) == 1
    current_policy = created.semantic_policies[0]
    assert current_policy.target_type is TargetType.CURRENT_ROLE
    assert current_policy.target_id == "role-current"
    assert current_policy.selection_source is SemanticPolicySelectionSource.PROFILE_METADATA
    assert current_policy.pack_refs == (
        DomainPackReference(pack_id="it_ai", version="1"),
    )
    assert after is not None
    assert after.model_dump(mode="json") == before_payload


@pytest.mark.asyncio
async def test_exact_legacy_mapping_is_snapshotted_and_wrong_version_is_not_used() -> None:
    mapping = RoleProfileSemanticPolicyMapping(
        role_profile_id="role-current",
        role_profile_version="1",
        core_version="semantic-core-v1",
        pack_refs=(DomainPackReference(pack_id="it_ai", version="1"),),
        selection_source=SemanticPolicySelectionSource.LEGACY_PROFILE_VERSION_MAPPING,
    )
    service, _, _ = await service_with(
        semantic_policy=None,
        semantic_policy_mappings=(mapping,),
    )

    created = await service.create(request(), learner())

    assert len(created.semantic_policies) == 1
    assert (
        created.semantic_policies[0].selection_source
        is SemanticPolicySelectionSource.LEGACY_PROFILE_VERSION_MAPPING
    )

    wrong_version = mapping.model_copy(update={"role_profile_version": "2"})
    missing_service, _, _ = await service_with(
        semantic_policy=None,
        semantic_policy_mappings=(wrong_version,),
    )
    with pytest.raises(SemanticPolicyNotConfiguredError) as raised:
        await missing_service.create(request(), learner())
    assert raised.value.code == "semantic_policy_not_configured"


@pytest.mark.asyncio
async def test_missing_semantic_policy_fails_closed_without_portfolio() -> None:
    service, _, portfolios = await service_with(semantic_policy=None)

    with pytest.raises(SemanticPolicyNotConfiguredError) as raised:
        await service.create(request(), learner())

    assert raised.value.code == "semantic_policy_not_configured"
    assert await portfolios.get("capability-correlation-1") is None


@pytest.mark.asyncio
async def test_service_applies_alias_only_from_exact_selected_pack() -> None:
    service, extraction, _ = await service_with()
    cv = await extraction.get_profile("cv-profile-1")
    assert cv is not None
    extraction._profiles["cv-profile-1"] = cv.model_copy(
        update={
            "candidate_profile": CandidateProfile(
                skills=[
                    SkillEntity(
                        entity="Apache Kafka",
                        evidence=[
                            EvidenceItem(
                                context=EvidenceContext.USED_IN_EMPLOYMENT,
                                usage="implemented",
                                source_excerpt="Used Apache Kafka at work.",
                                confidence=0.91,
                                source_locator=SourceLocator(
                                    document_id="cv-document-1",
                                    section="experience",
                                    start_offset=0,
                                    end_offset=26,
                                ),
                            )
                        ],
                    )
                ]
            )
        },
        deep=True,
    )
    role = service._role_profiles._profiles[0]  # type: ignore[attr-defined]
    service._role_profiles._profiles[0] = role.model_copy(  # type: ignore[attr-defined]
        update={
            "requirements": [
                role.requirements[0].model_copy(
                    update={"id": "kafka", "evidence_terms": ["Kafka"]}
                )
            ]
        },
        deep=True,
    )

    created = await service.create(request(), learner())

    assessment = created.current_role.assessments[0]
    assert assessment.evidence_status.value == "supported"
    assert assessment.retrieved_candidate_count == 1


@pytest.mark.asyncio
async def test_unavailable_pack_reference_fails_safely() -> None:
    unavailable = RoleProfileSemanticPolicy(
        core_version="semantic-core-v1",
        pack_refs=(DomainPackReference(pack_id="it_ai", version="99"),),
    )
    service, _, portfolios = await service_with(semantic_policy=unavailable)

    with pytest.raises(SemanticPolicyUnavailableError) as raised:
        await service.create(request(), learner())

    assert raised.value.code == "semantic_policy_unavailable"
    assert await portfolios.get("capability-correlation-1") is None


@pytest.mark.asyncio
async def test_same_inputs_and_policy_produce_deterministic_snapshot_structure() -> None:
    service, _, _ = await service_with()
    first = await service.create(request(), learner())
    second_request = request().model_copy(update={"correlation_id": "capability-correlation-2"})

    second = await service.create(second_request, learner())

    assert second.semantic_policies == first.semantic_policies
    assert second.current_role == first.current_role
    assert second.preview_readiness == first.preview_readiness
    assert second.verification_queue == first.verification_queue


@pytest.mark.asyncio
async def test_future_target_missing_policy_fails_closed_independently() -> None:
    service, _, portfolios = await service_with()
    service._role_profiles._profiles.append(  # type: ignore[attr-defined]
        active_role().model_copy(
            update={
                "id": "role-future",
                "status": RoleProfileStatus.PROVISIONAL,
                "semantic_policy": None,
            }
        )
    )

    with pytest.raises(SemanticPolicyNotConfiguredError):
        await service.create(request(future="role-future"), learner())

    assert await portfolios.get("capability-correlation-1") is None


@pytest.mark.asyncio
async def test_future_target_unavailable_pack_fails_closed_independently() -> None:
    unavailable = RoleProfileSemanticPolicy(
        core_version="semantic-core-v1",
        pack_refs=(DomainPackReference(pack_id="it_ai", version="99"),),
    )
    service, _, portfolios = await service_with()
    service._role_profiles._profiles.append(  # type: ignore[attr-defined]
        active_role().model_copy(
            update={
                "id": "role-future",
                "status": RoleProfileStatus.PROVISIONAL,
                "semantic_policy": unavailable,
            }
        )
    )

    with pytest.raises(SemanticPolicyUnavailableError):
        await service.create(request(future="role-future"), learner())

    assert await portfolios.get("capability-correlation-1") is None


@pytest.mark.asyncio
async def test_current_and_future_policy_provenance_is_keyed_by_target_track() -> None:
    service, _, _ = await service_with()
    service._role_profiles._profiles.append(  # type: ignore[attr-defined]
        active_role().model_copy(
            update={
                "id": "role-future",
                "version": "7",
                "status": RoleProfileStatus.PROVISIONAL,
                "semantic_policy": TEST_SEMANTIC_POLICY,
            }
        )
    )

    created = await service.create(request(future="role-future"), learner())

    assert [item.target_type for item in created.semantic_policies] == [
        TargetType.CURRENT_ROLE,
        TargetType.FUTURE_ROLE,
    ]
    assert [item.target_id for item in created.semantic_policies] == [
        "role-current",
        "role-future",
    ]
    assert [item.target_version for item in created.semantic_policies] == ["1", "7"]
