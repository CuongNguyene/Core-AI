from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.authorization.schemas import ActorContext, Role
from app.candidate.repository import InMemoryCandidateRepository
from app.candidate.schemas import Candidate
from app.integration.actor_context import get_signed_actor_context
from app.integration.auth import verify_integration_api_key
from app.integration.identity_bridge import (
    CandidateIdentityBridgeService,
    IdentityBridgeError,
    InMemoryCandidateIdentityLinkRepository,
    LmsIdentityContext,
)
from app.integration.identity_bridge_api import router as identity_bridge_router

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ORG_ID = UUID("00000000-0000-0000-0000-000000000002")
ACTOR_ID = UUID("00000000-0000-0000-0000-000000000002")
USER_A = "55555555-5555-4555-8555-555555555555"
USER_B = "66666666-6666-4666-8666-666666666666"


class FakeLmsIdentityResolver:
    def __init__(self) -> None:
        self.contexts: dict[str, LmsIdentityContext] = {}

    async def resolve(self, user_id: str) -> LmsIdentityContext | None:
        return self.contexts.get(user_id)


def actor(organization_id: UUID = ORG_ID) -> ActorContext:
    return ActorContext(
        actor_id=ACTOR_ID,
        organization_id=organization_id,
        roles=frozenset({Role.ADMIN}),
    )


async def make_service() -> tuple[CandidateIdentityBridgeService, FakeLmsIdentityResolver, InMemoryCandidateIdentityLinkRepository]:
    candidates = InMemoryCandidateRepository()
    resolver = FakeLmsIdentityResolver()
    links = InMemoryCandidateIdentityLinkRepository()
    service = CandidateIdentityBridgeService(candidates, resolver, links)
    return service, resolver, links


async def add_candidate(repository: InMemoryCandidateRepository, organization_id: UUID = ORG_ID) -> UUID:
    candidate_id = uuid4()
    now = datetime.now(UTC)
    await repository.create(
        Candidate(
            candidate_id=candidate_id,
            organization_id=organization_id,
            created_by_actor_id=ACTOR_ID,
            created_at=now,
            updated_at=now,
        )
    )
    return candidate_id


def lms_context(user_id: str, organization_id: UUID = ORG_ID, status: str = "ACTIVE") -> LmsIdentityContext:
    return LmsIdentityContext(user_id=user_id, organization_id=organization_id, status=status)


@pytest.mark.asyncio
async def test_same_org_link_persists_and_resolves_exact_user() -> None:
    service, resolver, links = await make_service()
    candidate_id = await add_candidate(service._candidates)  # noqa: SLF001 - fixture setup
    resolver.contexts[USER_A] = lms_context(USER_A)

    link = await service.link(candidate_id, USER_A, actor())

    assert link.candidate_id == candidate_id
    assert link.source_subject_ref == USER_A
    assert link.organization_scope == ORG_ID
    assert link.status == "ACTIVE"
    assert await service.resolve_lms_user_for_candidate(candidate_id, actor()) == USER_A
    assert len(await links.list_active()) == 1


@pytest.mark.asyncio
async def test_exact_retry_is_idempotent_without_duplicate_link() -> None:
    service, resolver, links = await make_service()
    candidate_id = await add_candidate(service._candidates)  # noqa: SLF001 - fixture setup
    resolver.contexts[USER_A] = lms_context(USER_A)

    first = await service.link(candidate_id, USER_A, actor())
    second = await service.link(candidate_id, USER_A, actor())

    assert second.id == first.id
    assert len(await links.list_active()) == 1


@pytest.mark.asyncio
async def test_candidate_and_user_conflicts_fail_closed() -> None:
    service, resolver, _ = await make_service()
    candidate_a = await add_candidate(service._candidates)  # noqa: SLF001 - fixture setup
    candidate_b = await add_candidate(service._candidates)  # noqa: SLF001 - fixture setup
    resolver.contexts[USER_A] = lms_context(USER_A)
    resolver.contexts[USER_B] = lms_context(USER_B)
    await service.link(candidate_a, USER_A, actor())

    with pytest.raises(IdentityBridgeError, match="candidate_already_linked"):
        await service.link(candidate_a, USER_B, actor())
    with pytest.raises(IdentityBridgeError, match="user_already_linked"):
        await service.link(candidate_b, USER_A, actor())


@pytest.mark.asyncio
async def test_cross_org_unknown_and_inactive_users_are_rejected() -> None:
    service, resolver, links = await make_service()
    candidate_id = await add_candidate(service._candidates)
    resolver.contexts[USER_A] = lms_context(USER_A, OTHER_ORG_ID)
    resolver.contexts[USER_B] = lms_context(USER_B, ORG_ID, "DISABLED")

    with pytest.raises(IdentityBridgeError, match="organization_mismatch"):
        await service.link(candidate_id, USER_A, actor())
    with pytest.raises(IdentityBridgeError, match="lms_user_ineligible"):
        await service.link(candidate_id, USER_B, actor())
    assert await links.list_active() == []


@pytest.mark.asyncio
async def test_unlinked_candidate_is_explicit_and_no_identity_fallback_occurs() -> None:
    service, _, _ = await make_service()
    candidate_id = await add_candidate(service._candidates)

    with pytest.raises(IdentityBridgeError, match="candidate_not_linked"):
        await service.resolve_lms_user_for_candidate(candidate_id, actor())


@pytest.mark.asyncio
async def test_department_mobility_does_not_change_candidate_link() -> None:
    service, resolver, links = await make_service()
    candidate_id = await add_candidate(service._candidates)
    resolver.contexts[USER_A] = lms_context(USER_A)
    link = await service.link(candidate_id, USER_A, actor())
    resolver.contexts[USER_A] = lms_context(USER_A)

    assert await service.resolve_lms_user_for_candidate(candidate_id, actor()) == USER_A
    assert (await links.list_active())[0].id == link.id


@pytest.mark.asyncio
async def test_successful_link_records_bounded_audit_only() -> None:
    service, resolver, _ = await make_service()
    candidate_id = await add_candidate(service._candidates)
    resolver.contexts[USER_A] = lms_context(USER_A)

    await service.link(candidate_id, USER_A, actor())

    assert service.audit_events == [
        {
            "action": "CANDIDATE_LMS_USER_LINKED",
            "candidate_id": str(candidate_id),
            "source_system": "lms",
            "source_subject_ref": USER_A,
            "organization_scope": str(ORG_ID),
            "actor_id": str(ACTOR_ID),
        }
    ]


@pytest.mark.asyncio
async def test_integration_api_creates_and_reads_link_without_profile_ownership() -> None:
    service, resolver, _ = await make_service()
    candidate_id = await add_candidate(service._candidates)  # noqa: SLF001 - fixture setup
    resolver.contexts[USER_A] = lms_context(USER_A)
    app = FastAPI()
    app.include_router(identity_bridge_router)
    app.state.candidate_identity_bridge_service = service
    app.dependency_overrides[verify_integration_api_key] = lambda: None
    app.dependency_overrides[get_signed_actor_context] = lambda: actor()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        created = await client.post(
            f"/api/v1/integration/candidates/{candidate_id}/lms-user-link",
            json={"schema_version": "v1", "data": {"lms_user_id": USER_A}},
        )
        read = await client.get(f"/api/v1/integration/candidates/{candidate_id}/lms-user-link")

    assert created.status_code == 200
    assert read.status_code == 200
    assert read.json()["data"]["source_subject_ref"] == USER_A
