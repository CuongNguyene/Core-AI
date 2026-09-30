from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.capability_analysis.domain_packs.contracts import DomainPackReference
from app.capability_analysis.errors import AuditPersistenceError
from app.capability_analysis.models import (
    CapabilityGapAuditEventRecord,
    CapabilityGapPortfolioRecord,
    GapOverlapLinkRecord,
    TargetGapRecord,
)
from app.capability_analysis.repository import SqlAlchemyCapabilityGapPortfolioRepository
from app.capability_analysis.schemas import (
    AssessmentEvidenceStatus,
    PreviewReadiness,
    TargetSemanticPolicySnapshot,
    TargetType,
    TargetUsageMode,
    VerificationQueueItem,
    VerificationQueueStatus,
)
from app.documents.models import DocumentRecord  # noqa: F401
from app.matching.schemas import SemanticPolicySelectionSource
from app.shared.database import Base
from tests.test_capability_analysis_repository import portfolio


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_portfolio_round_trips_immutable_target_rows_and_safe_audit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyCapabilityGapPortfolioRepository(session_factory)
    saved = await repository.create(portfolio())

    restored = await repository.get(saved.id)

    assert restored == saved
    assert restored.cv_profile_version == 3
    assert restored.current_target_version == "2.1"
    assert restored.future_target_version == "1.4"
    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(CapabilityGapPortfolioRecord))
            == 1
        )
        assert await session.scalar(select(func.count()).select_from(TargetGapRecord)) == 2
        assert await session.scalar(select(func.count()).select_from(GapOverlapLinkRecord)) == 1
        audit = await session.scalar(select(CapabilityGapAuditEventRecord))
        assert audit is not None
        assert "matched_evidence_refs" not in audit.audit_metadata
        assert "source_excerpt" not in audit.audit_metadata


@pytest.mark.asyncio
async def test_sql_portfolio_create_rolls_back_when_audit_write_fails(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyCapabilityGapPortfolioRepository(session_factory, fail_audit=True)

    with pytest.raises(AuditPersistenceError):
        await repository.create(portfolio())

    assert await repository.get("portfolio-1") is None
    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(CapabilityGapPortfolioRecord))
            == 0
        )


@pytest.mark.asyncio
async def test_sql_portfolio_restores_current_preview_warning(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    preview = portfolio().model_copy(deep=True)
    preview.current_role.usage_mode = TargetUsageMode.PREVIEW
    preview.current_role.warning_codes = ["current_target_profile_provisional"]
    preview.future_role = None
    preview.future_target_version = None
    preview.overlap_links = []

    repository = SqlAlchemyCapabilityGapPortfolioRepository(session_factory)
    saved = await repository.create(preview)

    restored = await repository.get(saved.id)

    assert restored is not None
    assert restored.current_role.warning_codes == ["current_target_profile_provisional"]


@pytest.mark.asyncio
async def test_sql_portfolio_round_trips_versioned_preview_snapshot(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    preview = portfolio().model_copy(deep=True)
    preview.current_role.usage_mode = TargetUsageMode.PREVIEW
    preview.current_role.warning_codes = ["current_target_profile_provisional"]
    preview.future_role = None
    preview.future_target_version = None
    preview.overlap_links = []
    preview.snapshot_schema_version = "capability-gap-preview-v1"
    preview.preview_readiness = PreviewReadiness()
    preview.verification_queue = [
        VerificationQueueItem(
            requirement_id="python",
            target_type=TargetType.CURRENT_ROLE,
            evidence_status=AssessmentEvidenceStatus.REQUIRES_VERIFICATION,
            status=VerificationQueueStatus.RECOMMENDED,
            evidence_refs=("evidence-python",),
        )
    ]

    repository = SqlAlchemyCapabilityGapPortfolioRepository(session_factory)
    saved = await repository.create(preview)
    restored = await repository.get(saved.id)

    assert restored is not None
    assert restored.snapshot_schema_version == "capability-gap-preview-v1"
    assert restored.preview_readiness == PreviewReadiness()
    assert restored.verification_queue == preview.verification_queue


@pytest.mark.asyncio
async def test_sql_portfolio_round_trips_semantic_policy_provenance(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    snapshot = TargetSemanticPolicySnapshot(
        target_id="role-current",
        target_version="2.1",
        target_type=TargetType.CURRENT_ROLE,
        core_version="semantic-core-v1",
        pack_refs=(DomainPackReference(pack_id="it_ai", version="1"),),
        selection_source=SemanticPolicySelectionSource.PROFILE_METADATA,
    )
    future_snapshot = snapshot.model_copy(
        update={
            "target_id": "role-future",
            "target_version": "1.4",
            "target_type": TargetType.FUTURE_ROLE,
        }
    )
    expected = portfolio().model_copy(
        update={"semantic_policies": (snapshot, future_snapshot)}, deep=True
    )
    repository = SqlAlchemyCapabilityGapPortfolioRepository(session_factory)

    await repository.create(expected)
    restored = await repository.get(expected.id)

    assert restored is not None
    assert restored.semantic_policies == (snapshot, future_snapshot)


@pytest.mark.asyncio
async def test_sql_portfolio_rejects_corrupt_semantic_policy_track_on_restore(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    current_only = portfolio().model_copy(
        update={
            "future_target_version": None,
            "future_role": None,
            "overlap_links": [],
            "semantic_policies": (
                TargetSemanticPolicySnapshot(
                    target_id="role-current",
                    target_version="2.1",
                    target_type=TargetType.CURRENT_ROLE,
                    core_version="semantic-core-v1",
                    pack_refs=(DomainPackReference(pack_id="it_ai", version="1"),),
                    selection_source=SemanticPolicySelectionSource.PROFILE_METADATA,
                ),
            ),
        },
        deep=True,
    )
    repository = SqlAlchemyCapabilityGapPortfolioRepository(session_factory)
    await repository.create(current_only)
    async with session_factory() as session, session.begin():
        record = await session.get(CapabilityGapPortfolioRecord, current_only.id)
        assert record is not None
        corrupt = record.semantic_policy
        assert corrupt is not None
        targets = cast(list[dict[str, object]], corrupt["targets"])
        record.semantic_policy = {
            "targets": [{**targets[0], "target_version": "wrong"}]
        }

    with pytest.raises(ValidationError):
        await repository.get(current_only.id)


def test_historical_portfolio_without_semantic_policy_deserializes_with_none() -> None:
    payload = portfolio().model_dump(mode="json")
    payload.pop("semantic_policies", None)

    restored = type(portfolio()).model_validate(payload, strict=False)

    assert restored.semantic_policies == ()


@pytest.mark.asyncio
async def test_sql_portfolio_allows_rerun_with_same_logical_gap_ids(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyCapabilityGapPortfolioRepository(session_factory)
    first = portfolio()
    second = portfolio().model_copy(
        update={"id": "portfolio-2", "correlation_id": "capability-correlation-2"},
        deep=True,
    )

    await repository.create(first)
    saved = await repository.create(second)

    assert saved.current_role.gaps[0].id == first.current_role.gaps[0].id
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(TargetGapRecord)) == 4


@pytest.mark.asyncio
async def test_sql_portfolio_lists_all_candidate_analyses_in_newest_first_order(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlAlchemyCapabilityGapPortfolioRepository(session_factory)
    candidate_id = UUID("8b4366e1-3f14-4b59-be5c-8690139592bf")
    first = portfolio().model_copy(
        update={"id": "portfolio-candidate-1", "candidate_id": candidate_id},
        deep=True,
    )
    second = portfolio().model_copy(
        update={
            "id": "portfolio-candidate-2",
            "candidate_id": candidate_id,
            "analysis_version": 2,
        },
        deep=True,
    )

    await repository.create(first)
    await repository.create(second)

    listed = await repository.list_for_candidate(
        candidate_id,
        actor_id=first.owner_actor_id,
        organization_id=first.organization_id,
    )

    assert [item.id for item in listed] == [second.id, first.id]
