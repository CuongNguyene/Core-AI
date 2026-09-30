from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.authorization.schemas import ActorContext, Role
from app.candidate.repository import CandidateRepository
from app.integration.models import CandidateIdentityLinkRecord
from app.shared.config import Settings


class IdentityBridgeError(Exception):
    def __init__(self, code: str, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class LmsIdentityContext:
    user_id: str
    organization_id: UUID
    status: str


@dataclass(frozen=True)
class CandidateIdentityLink:
    id: UUID
    candidate_id: UUID
    source_system: str
    source_subject_ref: str
    organization_scope: UUID
    status: str
    created_at: datetime
    created_by: UUID
    updated_at: datetime


class LmsIdentityResolver(Protocol):
    async def resolve(self, user_id: str) -> LmsIdentityContext | None: ...


class HttpLmsIdentityResolver:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.lms_identity_context_url.rstrip("/")
        self._token = settings.lms_identity_context_token.get_secret_value()

    async def resolve(self, user_id: str) -> LmsIdentityContext | None:
        if not self._token:
            raise IdentityBridgeError("lms_identity_context_unavailable", 503)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._base_url}/{user_id}/identity-context",
                    headers={"Authorization": f"Bearer {self._token}"},
                )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
            return LmsIdentityContext(
                user_id=str(payload["userId"]),
                organization_id=UUID(str(payload["organizationId"])),
                status=str(payload["status"]),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise IdentityBridgeError("lms_identity_context_unavailable", 503) from exc


class CandidateIdentityLinkRepository(Protocol):
    async def get_active_for_candidate(self, candidate_id: UUID) -> CandidateIdentityLink | None: ...

    async def get_active_for_subject(
        self, source_system: str, source_subject_ref: str, organization_scope: UUID
    ) -> CandidateIdentityLink | None: ...

    async def create(self, link: CandidateIdentityLink) -> CandidateIdentityLink: ...


class InMemoryCandidateIdentityLinkRepository:
    def __init__(self) -> None:
        self.links: dict[UUID, CandidateIdentityLink] = {}

    async def get_active_for_candidate(self, candidate_id: UUID) -> CandidateIdentityLink | None:
        return next(
            (item for item in self.links.values() if item.candidate_id == candidate_id and item.status == "ACTIVE"),
            None,
        )

    async def get_active_for_subject(
        self, source_system: str, source_subject_ref: str, organization_scope: UUID
    ) -> CandidateIdentityLink | None:
        return next(
            (
                item
                for item in self.links.values()
                if item.status == "ACTIVE"
                and item.source_system == source_system
                and item.source_subject_ref == source_subject_ref
                and item.organization_scope == organization_scope
            ),
            None,
        )

    async def create(self, link: CandidateIdentityLink) -> CandidateIdentityLink:
        self.links[link.id] = link
        return link

    async def list_active(self) -> list[CandidateIdentityLink]:
        return [item for item in self.links.values() if item.status == "ACTIVE"]


class SqlAlchemyCandidateIdentityLinkRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_active_for_candidate(self, candidate_id: UUID) -> CandidateIdentityLink | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CandidateIdentityLinkRecord).where(
                    CandidateIdentityLinkRecord.candidate_id == candidate_id,
                    CandidateIdentityLinkRecord.source_system == "lms",
                    CandidateIdentityLinkRecord.status == "ACTIVE",
                )
            )
            return _link(record) if record is not None else None

    async def get_active_for_subject(
        self, source_system: str, source_subject_ref: str, organization_scope: UUID
    ) -> CandidateIdentityLink | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CandidateIdentityLinkRecord).where(
                    CandidateIdentityLinkRecord.source_system == source_system,
                    CandidateIdentityLinkRecord.source_subject_ref == source_subject_ref,
                    CandidateIdentityLinkRecord.organization_scope == organization_scope,
                    CandidateIdentityLinkRecord.status == "ACTIVE",
                )
            )
            return _link(record) if record is not None else None

    async def create(self, link: CandidateIdentityLink) -> CandidateIdentityLink:
        async with self._session_factory() as session, session.begin():
            session.add(
                CandidateIdentityLinkRecord(
                    id=link.id,
                    candidate_id=link.candidate_id,
                    source_system=link.source_system,
                    source_subject_ref=link.source_subject_ref,
                    organization_scope=link.organization_scope,
                    status=link.status,
                    created_at=link.created_at,
                    created_by=link.created_by,
                    updated_at=link.updated_at,
                )
            )
            try:
                await session.flush()
            except IntegrityError as exc:
                raise IdentityBridgeError("identity_link_conflict") from exc
        return link


def _link(record: CandidateIdentityLinkRecord) -> CandidateIdentityLink:
    return CandidateIdentityLink(
        id=record.id,
        candidate_id=record.candidate_id,
        source_system=record.source_system,
        source_subject_ref=record.source_subject_ref,
        organization_scope=record.organization_scope,
        status=record.status,
        created_at=record.created_at,
        created_by=record.created_by,
        updated_at=record.updated_at,
    )


class CandidateIdentityBridgeService:
    def __init__(
        self,
        candidates: CandidateRepository,
        lms_identity: LmsIdentityResolver,
        links: CandidateIdentityLinkRepository,
    ) -> None:
        self._candidates = candidates
        self._lms_identity = lms_identity
        self._links = links
        self.audit_events: list[dict[str, str]] = []

    async def link(
        self, candidate_id: UUID, lms_user_id: str, actor: ActorContext
    ) -> CandidateIdentityLink:
        if not self._can_manage(actor):
            raise IdentityBridgeError("identity_link_forbidden", 403)
        candidate = await self._candidates.get(candidate_id)
        if candidate is None:
            raise IdentityBridgeError("candidate_not_found", 404)
        if candidate.organization_id != actor.organization_id:
            raise IdentityBridgeError("organization_mismatch", 403)
        if candidate.status.value != "active":
            raise IdentityBridgeError("candidate_ineligible", 409)

        existing_candidate = await self._links.get_active_for_candidate(candidate_id)
        if existing_candidate is not None:
            if existing_candidate.source_subject_ref == lms_user_id:
                return existing_candidate
            raise IdentityBridgeError("candidate_already_linked")

        identity = await self._lms_identity.resolve(lms_user_id)
        if identity is None:
            raise IdentityBridgeError("lms_user_not_found", 404)
        if identity.status.casefold() != "active":
            raise IdentityBridgeError("lms_user_ineligible")
        if identity.organization_id != candidate.organization_id:
            raise IdentityBridgeError("organization_mismatch", 403)

        existing_subject = await self._links.get_active_for_subject(
            "lms", identity.user_id, identity.organization_id
        )
        if existing_subject is not None:
            raise IdentityBridgeError("user_already_linked")

        now = datetime.now(UTC)
        link = CandidateIdentityLink(
            id=uuid4(),
            candidate_id=candidate_id,
            source_system="lms",
            source_subject_ref=identity.user_id,
            organization_scope=identity.organization_id,
            status="ACTIVE",
            created_at=now,
            created_by=actor.actor_id,
            updated_at=now,
        )
        stored = await self._links.create(link)
        self.audit_events.append(
            {
                "action": "CANDIDATE_LMS_USER_LINKED",
                "candidate_id": str(candidate_id),
                "source_system": stored.source_system,
                "source_subject_ref": stored.source_subject_ref,
                "organization_scope": str(stored.organization_scope),
                "actor_id": str(actor.actor_id),
            }
        )
        return stored

    async def resolve_lms_user_for_candidate(
        self, candidate_id: UUID, actor: ActorContext
    ) -> str:
        if not self._can_manage(actor):
            raise IdentityBridgeError("identity_link_forbidden", 403)
        candidate = await self._candidates.get(candidate_id)
        if candidate is None:
            raise IdentityBridgeError("candidate_not_found", 404)
        if candidate.organization_id != actor.organization_id:
            raise IdentityBridgeError("organization_mismatch", 403)
        link = await self._links.get_active_for_candidate(candidate_id)
        if link is None:
            raise IdentityBridgeError("candidate_not_linked", 409)
        identity = await self._lms_identity.resolve(link.source_subject_ref)
        if identity is None or identity.status.casefold() != "active":
            raise IdentityBridgeError("lms_user_ineligible", 409)
        if identity.organization_id != link.organization_scope:
            raise IdentityBridgeError("organization_mismatch", 403)
        return identity.user_id

    async def get_link(self, candidate_id: UUID, actor: ActorContext) -> CandidateIdentityLink:
        await self.resolve_lms_user_for_candidate(candidate_id, actor)
        link = await self._links.get_active_for_candidate(candidate_id)
        if link is None:
            raise IdentityBridgeError("candidate_not_linked", 409)
        return link

    @staticmethod
    def _can_manage(actor: ActorContext) -> bool:
        return bool(actor.roles & {Role.ADMIN, Role.SME, Role.REVIEWER})
