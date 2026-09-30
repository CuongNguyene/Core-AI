from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.authorization.fixtures import LEARNER_ID, ORG_PAI_ID, REVIEWER_ID
from app.capability_analysis.domain_packs.contracts import DomainPackReference
from app.capability_analysis.domain_packs.it_ai import IT_AI_PACK
from app.extraction.fixtures import FixtureDocumentSource
from app.extraction.repository import SqlAlchemyExtractionRepository
from app.extraction.schemas import (
    DocumentKind,
    EvidenceStatus,
    EvidenceType,
    ExtractedClaim,
    ExtractionJob,
    ExtractionProfile,
    JDExtractionOutput,
    JDRequirementExtractionOutputV2,
    JDRequirementExtractionV2,
    JDRequirementModality,
    JobStatus,
    ReviewState,
    SourceLocator,
)
from app.matching.repository import SqlAlchemyRoleProfileRepository
from app.matching.schemas import (
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileSemanticPolicy,
    RoleProfileStatus,
)
from app.role_profile_authoring.errors import (
    RoleProfileDraftSourceError,
    RoleProfileDraftStateError,
    RoleProfileDraftVersionConflictError,
)
from app.role_profile_authoring.repository import SqlAlchemyRoleProfileDraftRepository
from app.role_profile_authoring.schemas import RoleProfileDraftStatus
from app.semantic_policy.repository import InMemorySemanticPolicyRepository
from app.semantic_policy.schemas import SemanticPolicy, SemanticPolicyRef, SemanticPolicyStatus
from app.semantic_policy.service import SemanticPolicyResolver
from app.shared.database import Base

TEST_SEMANTIC_POLICY = RoleProfileSemanticPolicy(
    core_version="semantic-core-v1",
    pack_refs=(DomainPackReference(pack_id="it_ai", version="1"),),
)


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        del connection_record
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def jd_profile(
    profile_id: str = "jd-accepted", state: ReviewState = ReviewState.ACCEPTED
) -> ExtractionProfile:
    claim = ExtractedClaim(
        value="Python",
        evidence_type=EvidenceType.EXPLICIT_SKILL,
        confidence=0.9,
        evidence_status=EvidenceStatus.SUPPORTED,
        source_locator=SourceLocator(
            document_id="fixture-jd-basic",
            section="required_skills",
            start_offset=0,
            end_offset=6,
        ),
        source_excerpt="Python",
    )
    return ExtractionProfile(
        id=profile_id,
        job_id="job-" + profile_id,
        document_id="fixture-jd-basic",
        document_kind=DocumentKind.JD,
        owner_actor_id=LEARNER_ID,
        version=1,
        review_state=state,
        accepted_by=REVIEWER_ID if state is ReviewState.ACCEPTED else None,
        accepted_at=datetime.now(UTC) if state is ReviewState.ACCEPTED else None,
        output=JDExtractionOutput(required_skills=[claim], responsibilities=[], qualifications=[]),
        audit={
            "provider": "mock",
            "model": "mock-v1",
            "prompt_template_version": "1.0",
            "policy_version": "privacy-v1",
        },
    )


def queued_job(profile: ExtractionProfile) -> ExtractionJob:
    return ExtractionJob(
        id=profile.job_id,
        document_id=profile.document_id,
        document_kind=profile.document_kind,
        owner_actor_id=profile.owner_actor_id,
        correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        status=JobStatus.QUEUED,
    )


def first_required_skill() -> ExtractedClaim:
    output = jd_profile().output
    assert isinstance(output, JDExtractionOutput)
    return output.required_skills[0]


@pytest.fixture
async def repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[SqlAlchemyRoleProfileDraftRepository]:
    extraction = SqlAlchemyExtractionRepository(session_factory, FixtureDocumentSource.default())
    profile = jd_profile()
    await extraction.enqueue(queued_job(profile))
    await extraction.mark_succeeded(profile.job_id, profile)
    yield SqlAlchemyRoleProfileDraftRepository(
        session_factory,
        extraction,
        SqlAlchemyRoleProfileRepository(session_factory),
    )


@pytest.mark.asyncio
async def test_repository_creates_draft_from_accepted_jd_and_materializes_active(
    repository: SqlAlchemyRoleProfileDraftRepository,
) -> None:
    draft = await repository.create_from_jd("jd-accepted", REVIEWER_ID, ORG_PAI_ID, "draft-run-1")
    assert draft.status is RoleProfileDraftStatus.DRAFT
    assert await repository._role_profiles.get_preferred_target(draft.id) is None
    authored = await repository.author(
        draft.id,
        expected_version=draft.version,
        actor_id=REVIEWER_ID,
        title="Python Engineer",
        requirements=[
            draft.requirements[0].model_copy(
                update={
                    "classification": RequirementClassification.ROLE_CRITICAL,
                    "modality": "must",
                    "logical_group": "core-skills",
                    "target_level": "intermediate",
                    "observable_behaviors": ["Writes production Python."],
                    "evidence_constraints": ["Require source-backed evidence."],
                }
            )
        ],
    )
    validated = await repository.validate(
        authored.id, expected_version=authored.version, actor_id=REVIEWER_ID
    )
    approved = await repository.approve(
        validated.id,
        expected_version=validated.version,
        actor_id=REVIEWER_ID,
        requested_status=RoleProfileStatus.ACTIVE,
        semantic_policy=TEST_SEMANTIC_POLICY,
    )

    assert approved.status.value == "approved"
    assert approved.approved_role_profile_id is not None
    assert approved.approved_role_profile_id.startswith("role-profile-")
    assert approved.approved_role_profile_id != draft.id
    assert approved.version == validated.version
    assert draft.source_schema == "legacy_v1"
    assert draft.source_version == "1.1"
    assert "legacy_missing_modality" in {item.code for item in draft.authoring_findings}
    profile = await repository._role_profiles.get_active(approved.approved_role_profile_id)
    assert profile is not None
    assert profile.status is RoleProfileStatus.ACTIVE
    assert profile.semantic_policy == TEST_SEMANTIC_POLICY
    assert approved.approved_role_profile_version == profile.version


@pytest.mark.asyncio
async def test_accepted_v2_jd_materializes_mixed_semantics_as_provisional_role_profile(
    repository: SqlAlchemyRoleProfileDraftRepository,
) -> None:
    source = jd_profile("jd-v2-mixed").model_copy(
        update={
            "output": JDRequirementExtractionOutputV2(
                requirements=[
                    JDRequirementExtractionV2(
                        requirement_id="pmp",
                        statement="PMP certification preferred",
                        criterion_dimension="credential",
                        modality=JDRequirementModality.PREFERRED,
                        confidence=0.95,
                        evidence_status=EvidenceStatus.SUPPORTED,
                        source_locator=SourceLocator(
                            document_id="fixture-jd-basic",
                            section="preferred",
                            start_offset=0,
                            end_offset=26,
                        ),
                        source_excerpt="PMP certification preferred",
                    ),
                    JDRequirementExtractionV2(
                        requirement_id="monthly-reports",
                        statement="Prepare monthly financial reports",
                        criterion_dimension=None,
                        modality=JDRequirementModality.RESPONSIBILITY,
                        confidence=0.95,
                        evidence_status=EvidenceStatus.SUPPORTED,
                        source_locator=SourceLocator(
                            document_id="fixture-jd-basic",
                            section="responsibilities",
                            start_offset=27,
                            end_offset=61,
                        ),
                        source_excerpt="Prepare monthly financial reports",
                    ),
                ]
            )
        }
    )
    await repository._extraction.enqueue(queued_job(source))
    await repository._extraction.mark_succeeded(source.job_id, source)

    draft = await repository.create_from_jd(
        source.id, REVIEWER_ID, ORG_PAI_ID, "v2-mixed-provisional"
    )
    assert [item.criterion_dimension.value if item.criterion_dimension else None for item in draft.requirements] == [
        "credential",
        None,
    ]
    assert draft.requirements[1].modality == "responsibility"

    validated = await repository.validate(
        draft.id,
        expected_version=draft.version,
        actor_id=REVIEWER_ID,
    )
    approved = await repository.approve(
        validated.id,
        expected_version=validated.version,
        actor_id=REVIEWER_ID,
        requested_status=RoleProfileStatus.PROVISIONAL,
        semantic_policy=TEST_SEMANTIC_POLICY,
    )

    assert approved.approved_role_profile_id is not None
    profile = await repository._role_profiles.get_preferred_target(
        approved.approved_role_profile_id
    )
    assert approved.status is RoleProfileDraftStatus.APPROVED
    assert profile is not None
    assert profile.status is RoleProfileStatus.PROVISIONAL
    assert [item.criterion_dimension.value if item.criterion_dimension else None for item in profile.requirements] == [
        "credential",
        None,
    ]
    assert profile.requirements[1].modality == "responsibility"


@pytest.mark.asyncio
async def test_legacy_role_draft_profile_identity_remains_resolvable(
    repository: SqlAlchemyRoleProfileDraftRepository,
) -> None:
    draft = await repository.create_from_jd("jd-accepted", REVIEWER_ID, ORG_PAI_ID, "legacy-id")
    legacy_profile = RoleCompetencyProfile(
        id=draft.id,
        version="1",
        status=RoleProfileStatus.PROVISIONAL,
        source_jd_profile_id=draft.source_jd_profile_id,
        source_jd_profile_version=draft.source_jd_profile_version,
        rule_set_version="legacy",
        policy_version="legacy",
        requirements=draft.requirements,
    )
    await repository._role_profiles.save(legacy_profile)

    resolved = await repository._role_profiles.get_preferred_target(draft.id)

    assert resolved is not None
    assert resolved.id == draft.id


@pytest.mark.asyncio
async def test_approval_persists_explicit_active_semantic_policy_reference(
    repository: SqlAlchemyRoleProfileDraftRepository,
) -> None:
    policy_repository = InMemorySemanticPolicyRepository(
        [
            SemanticPolicy(
                policy_id="semantic-policy-it",
                version="1",
                status=SemanticPolicyStatus.ACTIVE,
                domain_pack_id="it_ai",
                domain_pack_version="1",
                domain_pack_checksum=IT_AI_PACK.checksum,
                description="IT policy",
            )
        ]
    )
    repository._semantic_policy_resolver = SemanticPolicyResolver(
        policy_repository, (IT_AI_PACK,)
    )
    draft = await repository.create_from_jd("jd-accepted", REVIEWER_ID, ORG_PAI_ID, "governed")
    authored = await repository.author(
        draft.id,
        expected_version=draft.version,
        actor_id=REVIEWER_ID,
        title="Python Engineer",
        requirements=draft.requirements,
    )
    validated = await repository.validate(
        authored.id, expected_version=authored.version, actor_id=REVIEWER_ID
    )
    reference = SemanticPolicyRef(policy_id="semantic-policy-it", policy_version="1")
    approved = await repository.approve(
        validated.id,
        expected_version=validated.version,
        actor_id=REVIEWER_ID,
        requested_status=RoleProfileStatus.PROVISIONAL,
        semantic_policy=TEST_SEMANTIC_POLICY,
        semantic_policy_ref=reference,
    )

    profile = await repository._role_profiles.get_version(
        approved.approved_role_profile_id, str(validated.version)
    )
    assert profile is not None
    assert profile.semantic_policy_ref == reference


@pytest.mark.asyncio
async def test_legacy_draft_aggregates_detail_findings_without_false_provenance_block(
    repository: SqlAlchemyRoleProfileDraftRepository,
) -> None:
    draft = await repository.create_from_jd("jd-accepted", REVIEWER_ID, ORG_PAI_ID, "legacy-summary")

    modality = [
        item for item in draft.quality_gate.summary_findings if item.code == "legacy_missing_modality"
    ]
    assert len(modality) == 1
    assert modality[0].affected_requirement_count == 1
    assert "legacy_missing_provenance" not in {
        item.code for item in draft.quality_gate.summary_findings
    }
    assert draft.approval_eligibility.can_create_draft is True
    assert draft.approval_eligibility.can_approve_provisional is True
    assert draft.approval_eligibility.can_approve_active is False
    assert all(item.requirement_id == draft.requirements[0].id for item in draft.authoring_findings)
    assert draft.requirements[0].source_locator is not None
    assert draft.requirements[0].source_requirement_ref == "legacy.skill.1"


@pytest.mark.asyncio
async def test_repository_rejects_stale_authoring_and_pending_source(
    repository: SqlAlchemyRoleProfileDraftRepository,
) -> None:
    draft = await repository.create_from_jd("jd-accepted", REVIEWER_ID, ORG_PAI_ID, "run-2")
    with pytest.raises(RoleProfileDraftVersionConflictError):
        await repository.author(
            draft.id,
            expected_version=99,
            actor_id=REVIEWER_ID,
            title="Stale",
            requirements=draft.requirements,
        )

    with pytest.raises(RoleProfileDraftSourceError):
        await repository.create_from_jd("jd-pending", REVIEWER_ID, ORG_PAI_ID, "run-3")


@pytest.mark.asyncio
async def test_failed_quality_gate_can_only_approve_provisional(
    repository: SqlAlchemyRoleProfileDraftRepository,
) -> None:
    draft = await repository.create_from_jd("jd-accepted", REVIEWER_ID, ORG_PAI_ID, "run-4")
    authored = await repository.author(
        draft.id,
        expected_version=draft.version,
        actor_id=REVIEWER_ID,
        title="Incomplete role",
        requirements=[draft.requirements[0], draft.requirements[0]],
    )
    validated = await repository.validate(
        authored.id, expected_version=authored.version, actor_id=REVIEWER_ID
    )
    with pytest.raises(RoleProfileDraftStateError, match="passing quality gate"):
        await repository.approve(
            validated.id,
            expected_version=validated.version,
            actor_id=REVIEWER_ID,
            requested_status=RoleProfileStatus.ACTIVE,
            semantic_policy=TEST_SEMANTIC_POLICY,
        )
    approved = await repository.approve(
        validated.id,
        expected_version=validated.version,
        actor_id=REVIEWER_ID,
        requested_status=RoleProfileStatus.PROVISIONAL,
        semantic_policy=TEST_SEMANTIC_POLICY,
    )
    assert approved.status.value == "approved"
    profile = await repository._role_profiles.get_preferred_target(
        approved.approved_role_profile_id
    )
    assert profile is not None
    assert profile.status is RoleProfileStatus.PROVISIONAL


@pytest.mark.asyncio
async def test_null_legacy_placeholders_are_ignored_without_blocking_approval(
    repository: SqlAlchemyRoleProfileDraftRepository,
) -> None:
    lossy_claim = ExtractedClaim(
        value=None,
        evidence_type=EvidenceType.UNKNOWN,
        confidence=0.2,
        evidence_status=EvidenceStatus.INSUFFICIENT,
    )
    source = jd_profile("jd-lossy").model_copy(
        update={
            "output": JDExtractionOutput(
                required_skills=[
                    first_required_skill(),
                    lossy_claim,
                ],
                responsibilities=[],
                qualifications=[],
            )
        }
    )
    await repository._extraction.enqueue(queued_job(source))
    await repository._extraction.mark_succeeded(source.job_id, source)

    draft = await repository.create_from_jd("jd-lossy", REVIEWER_ID, ORG_PAI_ID, "run-lossy")
    authored = await repository.author(
        draft.id,
        expected_version=draft.version,
        actor_id=REVIEWER_ID,
        title="Python Engineer",
        requirements=draft.requirements,
    )
    validated = await repository.validate(
        authored.id, expected_version=authored.version, actor_id=REVIEWER_ID
    )

    assert len(draft.requirements) == 1
    assert validated.quality_gate.has_blocking is False
    assert validated.approval_eligibility.can_approve_provisional is True
