import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.documents.schemas import DocumentKind, DocumentStatus, StoredDocument
from app.role_registry.repository import InMemoryRoleRegistryRepository
from app.role_registry.schemas import CreateRoleRequest, RoleStatus
from app.role_registry.service import RoleRegistryService


ORG = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ORG = UUID("00000000-0000-0000-0000-000000000002")
ACTOR = UUID("11111111-1111-4111-8111-111111111111")


def document(*, organization_id: UUID = ORG) -> StoredDocument:
    return StoredDocument(
        id=uuid4(),
        owner_actor_id=ACTOR,
        organization_id=organization_id,
        kind=DocumentKind.JD,
        content_type="application/pdf",
        byte_size=10,
        sha256="a" * 64,
        object_key=f"jd/{uuid4()}.pdf",
        status=DocumentStatus.CLEAN,
        retention_until=datetime.now(UTC) + timedelta(days=1),
    )


def test_role_code_is_stable_when_second_jd_version_is_added() -> None:
    asyncio.run(_test_role_code_is_stable_when_second_jd_version_is_added())


async def _test_role_code_is_stable_when_second_jd_version_is_added() -> None:
    repository = InMemoryRoleRegistryRepository()
    service = RoleRegistryService(repository)
    role = await service.create_role(ORG, ACTOR, CreateRoleRequest(title="Product Manager"))

    first = await service.attach_document_as_jd_version(role.id, document())
    second = await service.attach_document_as_jd_version(role.id, document())

    assert role.role_code == "ROLE-000001"
    assert first.version == 1
    assert second.version == 2
    assert first.role_jd_id == second.role_jd_id
    assert len(await service.list_jd_versions(role.id, ORG)) == 2


def test_cross_organization_document_cannot_be_attached() -> None:
    asyncio.run(_test_cross_organization_document_cannot_be_attached())


async def _test_cross_organization_document_cannot_be_attached() -> None:
    repository = InMemoryRoleRegistryRepository()
    service = RoleRegistryService(repository)
    role = await service.create_role(ORG, ACTOR, CreateRoleRequest(title="Engineer"))

    with pytest.raises(PermissionError, match="organization"):
        await service.attach_document_as_jd_version(role.id, document(organization_id=OTHER_ORG))


def test_same_document_cannot_become_two_jd_versions() -> None:
    asyncio.run(_test_same_document_cannot_become_two_jd_versions())


async def _test_same_document_cannot_become_two_jd_versions() -> None:
    repository = InMemoryRoleRegistryRepository()
    service = RoleRegistryService(repository)
    role_a = await service.create_role(ORG, ACTOR, CreateRoleRequest(title="Engineer"))
    role_b = await service.create_role(ORG, ACTOR, CreateRoleRequest(title="Platform Engineer"))
    source = document()
    await service.attach_document_as_jd_version(role_a.id, source)

    with pytest.raises(ValueError, match="already attached"):
        await service.attach_document_as_jd_version(role_b.id, source)


def test_jd_version_starts_existing_extraction_with_bounded_correlation_id() -> None:
    asyncio.run(_test_jd_version_starts_existing_extraction_with_bounded_correlation_id())


async def _test_jd_version_starts_existing_extraction_with_bounded_correlation_id() -> None:
    class ExtractionRecorder:
        def __init__(self) -> None:
            self.jobs = []

        async def get_latest_job_for_document(self, document_id, document_kind):
            return None

        async def enqueue(self, job) -> None:
            self.jobs.append(job)

    repository = InMemoryRoleRegistryRepository()
    extraction = ExtractionRecorder()
    service = RoleRegistryService(repository, extraction=extraction)  # type: ignore[arg-type]
    role = await service.create_role(ORG, ACTOR, CreateRoleRequest(title="Engineer"))
    version = await service.attach_document_as_jd_version(role.id, document())

    assert len(extraction.jobs) == 1
    assert extraction.jobs[0].correlation_id == str(version.id)
    assert len(extraction.jobs[0].correlation_id) <= 36


def test_search_is_organization_scoped_and_does_not_merge_same_titles() -> None:
    asyncio.run(_test_search_is_organization_scoped_and_does_not_merge_same_titles())


async def _test_search_is_organization_scoped_and_does_not_merge_same_titles() -> None:
    repository = InMemoryRoleRegistryRepository()
    service = RoleRegistryService(repository)
    await service.create_role(ORG, ACTOR, CreateRoleRequest(title="Analyst"))
    await service.create_role(ORG, ACTOR, CreateRoleRequest(title="Analyst"))
    await service.create_role(OTHER_ORG, ACTOR, CreateRoleRequest(title="Analyst"))

    results = await service.search_roles(ORG, "Analyst")

    assert len(results) == 2
    assert {item.title for item in results} == {"Analyst"}
    assert all(item.status is RoleStatus.ACTIVE for item in results)
