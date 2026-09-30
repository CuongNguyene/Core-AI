from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.authorization.fixtures import LEARNER_ID
from app.capability_analysis.models import CapabilityGapPortfolioRecord
from app.documents.models import DocumentRecord
from app.extraction.models import ExtractionJobRecord, ExtractionProfileRecord
from app.shared.database import Base
from scripts.run_real_cv_capability_integration import (
    IntegrationPreflightError,
    assert_portfolio_contract,
    cleanup_live_data,
    safe_result,
    validate_real_cv_input,
)


class FakeBlobStore:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete(self, object_key: str) -> None:
        self.deleted.append(object_key)


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def test_preflight_rejects_hash_mismatch_before_upload(tmp_path: Path) -> None:
    cv_path = tmp_path / "candidate.pdf"
    cv_path.write_bytes(b"private CV bytes")

    with pytest.raises(IntegrationPreflightError, match="sha256"):
        validate_real_cv_input(cv_path, expected_sha256="0" * 64)


def test_safe_result_never_contains_document_content() -> None:
    result = safe_result(document_id="doc-1", portfolio_id="portfolio-1")

    assert result == {
        "document_id": "doc-1",
        "portfolio_id": "portfolio-1",
    }
    assert "content" not in result
    assert "excerpt" not in result


def test_portfolio_contract_requires_current_role_gap_and_redacts_source_fields() -> None:
    payload = {
        "id": "portfolio-1",
        "cv_profile_id": "profile-1",
        "cv_profile_version": 1,
        "current_target_version": "1.0",
        "future_target_version": None,
        "owner_actor_id": "00000000-0000-0000-0000-000000000005",
        "organization_id": "00000000-0000-0000-0000-000000000001",
        "correlation_id": "run-1",
        "current_role": {
            "target_id": "seed-real-cv-capability-target",
            "target_type": "current_role",
            "usage_mode": "official",
            "assessments": [{"target_type": "current_role", "requirement_id": "seed-python"}],
            "gaps": [
                {
                    "target_type": "current_role",
                    "requirement_id": "seed-integration-unavailable-signal",
                    "missing_signals": ["seed-integration-unavailable-signal"],
                }
            ],
        },
    }

    assert_portfolio_contract(payload)

    payload["current_role"]["gaps"][0]["source_excerpt"] = "private CV text"
    with pytest.raises(AssertionError, match="redacted"):
        assert_portfolio_contract(payload)


@pytest.mark.asyncio
async def test_cleanup_deletes_only_run_scoped_identifiers(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    document_id = uuid4()
    unrelated_document_id = uuid4()
    async with session_factory() as session, session.begin():
        session.add_all(
            [
                DocumentRecord(
                    id=document_id,
                    owner_actor_id=LEARNER_ID,
                    organization_id=UUID("00000000-0000-0000-0000-000000000001"),
                    document_kind="cv",
                    content_type="application/pdf",
                    byte_size=1,
                    sha256="0" * 64,
                    object_key="documents/run/object",
                    status="clean",
                    retention_until=datetime(2026, 9, 6, tzinfo=UTC),
                ),
                DocumentRecord(
                    id=unrelated_document_id,
                    owner_actor_id=LEARNER_ID,
                    organization_id=UUID("00000000-0000-0000-0000-000000000001"),
                    document_kind="cv",
                    content_type="application/pdf",
                    byte_size=1,
                    sha256="1" * 64,
                    object_key="documents/unrelated/object",
                    status="clean",
                    retention_until=datetime(2026, 9, 6, tzinfo=UTC),
                ),
            ]
        )
        session.add(
            ExtractionJobRecord(
                id="job-run",
                document_id=str(document_id),
                document_kind="cv",
                owner_actor_id=LEARNER_ID,
                correlation_id="job-run",
                status="succeeded",
                profile_id="profile-run",
            )
        )
        session.add(
            ExtractionProfileRecord(
                id="profile-run",
                job_id="job-run",
                document_id=str(document_id),
                document_kind="cv",
                owner_actor_id=LEARNER_ID,
                version=1,
                review_state="accepted",
                normalized_output={},
                audit_metadata={},
            )
        )
        session.add(
            CapabilityGapPortfolioRecord(
                id="portfolio-run",
                cv_profile_id="profile-run",
                cv_profile_version=1,
                current_target_id="target",
                current_target_version="1.0",
                current_usage_mode="official",
                owner_actor_id=str(LEARNER_ID),
                organization_id="00000000-0000-0000-0000-000000000001",
                correlation_id="portfolio-run",
            )
        )
        session.add(
            CapabilityGapPortfolioRecord(
                id="portfolio-unrelated",
                cv_profile_id="profile-other",
                cv_profile_version=1,
                current_target_id="target",
                current_target_version="1.0",
                current_usage_mode="official",
                owner_actor_id=str(LEARNER_ID),
                organization_id="00000000-0000-0000-0000-000000000001",
                correlation_id="portfolio-unrelated",
            )
        )

    blob_store = FakeBlobStore()
    result = await cleanup_live_data(
        session_factory,
        blob_store,
        {
            "document_id": str(document_id),
            "job_id": "job-run",
            "profile_id": "profile-run",
            "portfolio_id": "portfolio-run",
        },
        enabled=True,
    )

    assert result["cleanup_completed"] is True
    assert blob_store.deleted == ["documents/run/object"]
    async with session_factory() as session:
        assert await session.get(DocumentRecord, document_id) is None
        assert await session.get(CapabilityGapPortfolioRecord, "portfolio-run") is None
        assert await session.get(DocumentRecord, unrelated_document_id) is not None
        assert (
            await session.scalar(
                select(CapabilityGapPortfolioRecord.id).where(
                    CapabilityGapPortfolioRecord.id == "portfolio-unrelated"
                )
            )
            == "portfolio-unrelated"
        )
