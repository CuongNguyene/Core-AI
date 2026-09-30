from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.capability_analysis.domain_packs.contracts import (
    DomainSemanticHints,
)
from app.capability_analysis.domain_packs.registry import DomainPackRegistry
from app.semantic_policy.errors import SemanticPolicyError, SemanticPolicyNotFoundError
from app.semantic_policy.models import SemanticPolicyAuditEventRecord
from app.semantic_policy.repository import (
    InMemorySemanticPolicyRepository,
    SqlAlchemySemanticPolicyRepository,
)
from app.semantic_policy.schemas import (
    SemanticPolicy,
    SemanticPolicyRef,
    SemanticPolicyStatus,
)
from app.semantic_policy.service import SemanticPolicyResolver, SemanticPolicyService
from app.shared.database import Base


@dataclass(frozen=True)
class _Pack:
    pack_id: str = "fixture"
    version: str = "1"
    supported_domain: str = "fixture"
    status: str = "active"
    checksum: str = "sha256:fixture-v1"
    schema_version: str = "1"

    def normalize_term(self, value: str) -> str:
        return value

    def expand_aliases(self, text: str) -> tuple[str, ...]:
        return (text,)

    def map_requirement_phrase(self, phrase: str) -> DomainSemanticHints:
        return DomainSemanticHints(concepts=(phrase,))

    def map_evidence_phrase(self, phrase: str) -> DomainSemanticHints:
        return DomainSemanticHints(concepts=(phrase,))


def _policy(*, status: SemanticPolicyStatus = SemanticPolicyStatus.DRAFT) -> SemanticPolicy:
    return SemanticPolicy(
        policy_id="fixture-policy",
        version="1",
        status=status,
        domain_pack_id="fixture",
        domain_pack_version="1",
        domain_pack_checksum="sha256:fixture-v1",
        description="fixture semantic policy",
    )


@pytest.mark.asyncio
async def test_policy_lifecycle_is_explicit_and_active_versions_are_immutable() -> None:
    repository = InMemorySemanticPolicyRepository()
    service = SemanticPolicyService(repository, DomainPackRegistry((_Pack(),)))

    draft = await service.create(_policy())
    assert draft.status is SemanticPolicyStatus.DRAFT
    with pytest.raises(SemanticPolicyError, match="not active"):
        await SemanticPolicyResolver(repository, (_Pack(),)).resolve(
            SemanticPolicyRef(policy_id=draft.policy_id, policy_version=draft.version),
            target_id="role-1",
            target_type="current_role",
        )

    active = await service.activate(draft.policy_id, draft.version)
    assert active.status is SemanticPolicyStatus.ACTIVE
    assert active.activated_at is not None
    with pytest.raises(ValueError, match="immutable"):
        await repository.save(active.model_copy(update={"domain_pack_checksum": "changed"}))

    deprecated = await service.deprecate(active.policy_id, active.version)
    assert deprecated.status is SemanticPolicyStatus.DEPRECATED
    assert deprecated.deprecated_at is not None
    with pytest.raises(SemanticPolicyError, match="not active"):
        await SemanticPolicyResolver(repository, (_Pack(),)).resolve(
            SemanticPolicyRef(policy_id=active.policy_id, policy_version=active.version),
            target_id="role-1",
            target_type="current_role",
        )

    historical = await SemanticPolicyResolver(repository, (_Pack(),)).resolve(
        SemanticPolicyRef(policy_id=active.policy_id, policy_version=active.version),
        target_id="role-1",
        target_type="current_role",
        historical_replay=True,
    )
    assert historical.policy_version == "1"
    assert historical.domain_pack_checksum == "sha256:fixture-v1"


@pytest.mark.asyncio
async def test_resolver_requires_exact_policy_and_pack_versions() -> None:
    repository = InMemorySemanticPolicyRepository(
        [_policy(status=SemanticPolicyStatus.ACTIVE)]
    )
    resolver = SemanticPolicyResolver(repository, (_Pack(),))

    resolved = await resolver.resolve(
        SemanticPolicyRef(policy_id="fixture-policy", policy_version="1"),
        target_id="role-1",
        target_type="current_role",
    )
    assert resolved.policy_id == "fixture-policy"
    assert resolved.domain_pack_id == "fixture"
    assert resolved.domain_pack_version == "1"
    assert resolved.resolution_status == "resolved"

    with pytest.raises(SemanticPolicyError, match="not found"):
        await resolver.resolve(
            SemanticPolicyRef(policy_id="fixture-policy", policy_version="2"),
            target_id="role-1",
            target_type="current_role",
        )


@pytest.mark.asyncio
async def test_resolver_rejects_checksum_or_pack_status_mismatch() -> None:
    policy = _policy(status=SemanticPolicyStatus.ACTIVE)
    repository = InMemorySemanticPolicyRepository(
        [policy.model_copy(update={"domain_pack_checksum": "sha256:wrong"})]
    )
    with pytest.raises(SemanticPolicyError, match="incompatible"):
        await SemanticPolicyResolver(repository, (_Pack(),)).resolve(
            SemanticPolicyRef(policy_id=policy.policy_id, policy_version=policy.version),
            target_id="role-1",
            target_type="current_role",
        )


@pytest.mark.asyncio
async def test_resolver_uses_stable_safe_codes_for_missing_dependencies() -> None:
    repository = InMemorySemanticPolicyRepository()
    resolver = SemanticPolicyResolver(repository, (_Pack(),))
    with pytest.raises(SemanticPolicyNotFoundError) as error:
        await resolver.resolve(
            SemanticPolicyRef(policy_id="missing", policy_version="1"),
            target_id="role-1",
            target_type="current_role",
        )
    assert error.value.code == "semantic_policy_not_found"


@pytest.mark.asyncio
async def test_resolver_rejects_missing_pack_without_fallback() -> None:
    policy = _policy(status=SemanticPolicyStatus.ACTIVE).model_copy(
        update={"domain_pack_id": "missing"}
    )
    resolver = SemanticPolicyResolver(
        InMemorySemanticPolicyRepository([policy]),
        (_Pack(),),
    )
    with pytest.raises(SemanticPolicyError) as error:
        await resolver.resolve(
            SemanticPolicyRef(policy_id=policy.policy_id, policy_version=policy.version),
            target_id="role-1",
            target_type="current_role",
        )
    assert error.value.code in {"domain_pack_not_found", "domain_pack_version_not_found"}


@pytest.mark.asyncio
async def test_activation_rejects_policy_with_unavailable_pack() -> None:
    repository = InMemorySemanticPolicyRepository()
    service = SemanticPolicyService(repository, DomainPackRegistry((_Pack(),)))
    await service.create(_policy())
    await repository.save(
        _policy(status=SemanticPolicyStatus.DRAFT).model_copy(
            update={"policy_id": "bad-policy", "domain_pack_id": "missing"}
        )
    )
    with pytest.raises(SemanticPolicyError):
        await service.activate("bad-policy", "1")



def test_semantic_policy_ref_is_exact_and_immutable() -> None:
    reference = SemanticPolicyRef(policy_id="policy", policy_version="7")
    with pytest.raises(ValueError):
        reference.policy_version = "8"  # type: ignore[misc]


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_repository_round_trips_and_transitions_exact_policy_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemySemanticPolicyRepository(session_factory)
    saved = await repository.save(_policy())
    assert saved == _policy()
    assert await repository.get("fixture-policy", "1") == _policy()
    active = await repository.transition("fixture-policy", "1", SemanticPolicyStatus.ACTIVE)
    assert active.status is SemanticPolicyStatus.ACTIVE
    with pytest.raises(ValueError, match="immutable"):
        await repository.save(active)


@pytest.mark.asyncio
async def test_sql_repository_persists_safe_lifecycle_audit_event(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemySemanticPolicyRepository(session_factory)
    await repository.save(_policy())
    await repository.append_audit(
        action="semantic_policy_activated",
        policy_id="fixture-policy",
        policy_version="1",
        actor_id="actor-1",
    )
    async with session_factory() as session:
        event = await session.scalar(select(SemanticPolicyAuditEventRecord))
    assert event is not None
    assert event.action == "semantic_policy_activated"
    assert event.audit_metadata == {
        "policy_id": "fixture-policy",
        "policy_version": "1",
        "actor_id": "actor-1",
    }
