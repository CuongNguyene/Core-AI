from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.capability_analysis.domain_packs.contracts import DomainPackReference
from app.matching.models import RoleCompetencyProfileRecord
from app.matching.repository import (
    SqlAlchemyPreliminaryMatchRepository,
    SqlAlchemyRoleProfileRepository,
)
from app.matching.schemas import (
    RoleProfileSemanticPolicy,
    RoleProfileSemanticPolicyMapping,
    RoleProfileStatus,
    SemanticPolicySelectionSource,
)
from app.semantic_policy.schemas import SemanticPolicyRef
from app.shared.database import Base
from tests.test_matching_repository import active_role, match


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_role_profile_repository_persists_active_versioned_profile(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyRoleProfileRepository(session_factory)
    await repository.save(active_role())

    profile = await repository.get_active("role-ai-engineer")

    assert profile is not None
    assert profile.version == "1.0"
    assert profile.requirements[0].id == "critical-python"
    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(RoleCompetencyProfileRecord))
        ) == 1


@pytest.mark.asyncio
async def test_sql_role_profile_repository_preserves_prior_versions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyRoleProfileRepository(session_factory)
    await repository.save(
        active_role().model_copy(update={"version": "1.0", "status": RoleProfileStatus.RETIRED})
    )
    await repository.save(active_role().model_copy(update={"version": "2.0"}))

    profile = await repository.get_active("role-ai-engineer")

    assert profile is not None
    assert profile.version == "2.0"
    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(RoleCompetencyProfileRecord))
        ) == 2


@pytest.mark.asyncio
async def test_sql_role_profile_round_trips_immutable_semantic_policy_metadata(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyRoleProfileRepository(session_factory)
    policy = RoleProfileSemanticPolicy(
        core_version="semantic-core-v1",
        pack_refs=(DomainPackReference(pack_id="it_ai", version="1"),),
    )
    await repository.save(active_role().model_copy(update={"semantic_policy": policy}))

    restored = await repository.get_version("role-ai-engineer", "1.0")

    assert restored is not None
    assert restored.semantic_policy == policy
    assert restored.semantic_policy.pack_refs == (
        DomainPackReference(pack_id="it_ai", version="1"),
    )


@pytest.mark.asyncio
async def test_sql_role_profile_round_trips_exact_semantic_policy_reference(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyRoleProfileRepository(session_factory)
    reference = SemanticPolicyRef(policy_id="semantic-policy-it", policy_version="1")
    await repository.save(active_role().model_copy(update={"semantic_policy_ref": reference}))

    restored = await repository.get_version("role-ai-engineer", "1.0")

    assert restored is not None
    assert restored.semantic_policy_ref == reference


@pytest.mark.asyncio
async def test_sql_role_profile_binding_is_allowed_before_activation_and_immutable_after(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyRoleProfileRepository(session_factory)
    profile = active_role().model_copy(update={"status": RoleProfileStatus.PROVISIONAL})
    await repository.save(profile)
    reference = SemanticPolicyRef(policy_id="semantic-policy-it", policy_version="1")

    await repository.bind_semantic_policy(profile.id, profile.version, reference)
    restored = await repository.get_version(profile.id, profile.version)
    assert restored is not None
    assert restored.semantic_policy_ref == reference

    await repository.save(active_role().model_copy(update={"version": "2.0"}))
    with pytest.raises(ValueError, match="active"):
        await repository.bind_semantic_policy("role-ai-engineer", "2.0", reference)


@pytest.mark.asyncio
async def test_sql_legacy_semantic_policy_mapping_is_exact_and_immutable(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyRoleProfileRepository(session_factory)
    mapping = RoleProfileSemanticPolicyMapping(
        role_profile_id="role-ai-engineer",
        role_profile_version="1.0",
        core_version="semantic-core-v1",
        pack_refs=(DomainPackReference(pack_id="it_ai", version="1"),),
        selection_source=SemanticPolicySelectionSource.LEGACY_PROFILE_VERSION_MAPPING,
    )

    await repository.save_semantic_policy_mapping(mapping)

    assert (
        await repository.get_semantic_policy_mapping("role-ai-engineer", "1.0")
        == mapping
    )
    assert await repository.get_semantic_policy_mapping("role-ai-engineer", "2.0") is None
    with pytest.raises(ValueError, match="immutable"):
        await repository.save_semantic_policy_mapping(mapping)


@pytest.mark.asyncio
async def test_sql_match_repository_persists_result_allocation_and_safe_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyPreliminaryMatchRepository(session_factory)

    saved = await repository.create(match([]))
    restored = await repository.get(saved.id)

    assert restored is not None
    assert restored.cv_profile_version == 1
    assert restored.status.value == "completed"
