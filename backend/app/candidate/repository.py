from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.candidate.models import (
    CandidateClaimRecord,
    CandidateCVRecord,
    CandidateCVVersionRecord,
    CandidateDocumentRecord,
    CandidateEvidenceRecord,
    CandidateProfileRecord,
    CandidateRecord,
    CandidateReviewActionRecordModel,
)
from app.candidate.schemas import (
    Candidate,
    CandidateClaim,
    CandidateCVVersion,
    CandidateDocument,
    CandidateEvidence,
    CandidateProfileLink,
    CandidateReviewActionRecord,
    CandidateReviewState,
)


class CandidateRepository(Protocol):
    async def create(self, candidate: Candidate) -> Candidate: ...

    async def get(self, candidate_id: UUID) -> Candidate | None: ...

    async def list_candidates(
        self, organization_id: UUID, *, status: str | None = None, sort: str = "updated_at_desc", query: str | None = None
    ) -> tuple[Candidate, ...]: ...

    async def list_cv_versions(self, candidate_id: UUID) -> tuple[CandidateCVVersion, ...]: ...

    async def create_cv_version(self, version: CandidateCVVersion) -> CandidateCVVersion: ...

    async def get_review_action(
        self, candidate_id: UUID, idempotency_key: str
    ) -> CandidateReviewActionRecord | None: ...

    async def save_review_action(self, action: CandidateReviewActionRecord) -> None: ...

    async def update(self, candidate: Candidate) -> Candidate: ...

    async def attach_document(self, document: CandidateDocument) -> CandidateDocument: ...

    async def list_documents(self, candidate_id: UUID) -> tuple[CandidateDocument, ...]: ...

    async def list_candidate_ids_for_document(self, document_id: UUID) -> tuple[UUID, ...]: ...

    async def get_candidate_document_reference(
        self, candidate_id: UUID, document_id: UUID
    ) -> UUID | None: ...

    async def link_profile(self, profile: CandidateProfileLink) -> CandidateProfileLink: ...

    async def set_current_profile(self, candidate_id: UUID, profile_id: str) -> Candidate: ...

    async def promote_current_profile(
        self, candidate_id: UUID, profile_id: str, governance_version: int
    ) -> Candidate: ...

    async def update_profile_link(self, profile: CandidateProfileLink) -> CandidateProfileLink: ...

    async def get_profile_link(
        self, candidate_id: UUID, profile_id: str
    ) -> CandidateProfileLink | None: ...

    async def list_profiles(self, candidate_id: UUID) -> tuple[CandidateProfileLink, ...]: ...

    async def list_claims(self, candidate_id: UUID) -> tuple[CandidateClaim, ...]: ...

    async def get_claim(self, candidate_id: UUID, claim_id: UUID) -> CandidateClaim | None: ...

    async def create_claims(
        self, candidate_id: UUID, claims: Sequence[CandidateClaim], evidence: Sequence[CandidateEvidence]
    ) -> tuple[CandidateClaim, ...]: ...

    async def list_evidence(self, candidate_id: UUID, claim_id: UUID) -> tuple[CandidateEvidence, ...]: ...


class InMemoryCandidateRepository:
    def __init__(self) -> None:
        self._candidates: dict[UUID, Candidate] = {}
        self._documents: dict[UUID, CandidateDocument] = {}
        self._profiles: dict[UUID, CandidateProfileLink] = {}
        self._claims: dict[UUID, CandidateClaim] = {}
        self._evidence: dict[UUID, CandidateEvidence] = {}
        self._review_actions: dict[tuple[UUID, str], CandidateReviewActionRecord] = {}
        self._cvs: dict[UUID, UUID] = {}
        self._cv_versions: dict[UUID, CandidateCVVersion] = {}

    async def create(self, candidate: Candidate) -> Candidate:
        if candidate.candidate_id in self._candidates:
            raise ValueError("candidate_exists")
        self._candidates[candidate.candidate_id] = candidate.model_copy(deep=True)
        return candidate.model_copy(deep=True)

    async def get(self, candidate_id: UUID) -> Candidate | None:
        candidate = self._candidates.get(candidate_id)
        return candidate.model_copy(deep=True) if candidate else None

    async def list_candidates(
        self, organization_id: UUID, *, status: str | None = None, sort: str = "updated_at_desc", query: str | None = None
    ) -> tuple[Candidate, ...]:
        candidates = [
            candidate.model_copy(deep=True)
            for candidate in self._candidates.values()
            if candidate.organization_id == organization_id
            and (status is None or candidate.status.value == status)
            and (not query or _candidate_matches(candidate, query))
        ]
        reverse = sort.endswith("_desc")
        candidates.sort(key=lambda item: (item.updated_at, item.candidate_id.hex), reverse=reverse)
        return tuple(candidates)

    async def list_cv_versions(self, candidate_id: UUID) -> tuple[CandidateCVVersion, ...]:
        return tuple(sorted(
            (item.model_copy(deep=True) for item in self._cv_versions.values() if item.candidate_id == candidate_id),
            key=lambda item: (item.version, item.created_at), reverse=True
        ))

    async def create_cv_version(self, version: CandidateCVVersion) -> CandidateCVVersion:
        if version.candidate_id not in self._candidates:
            raise KeyError(version.candidate_id)
        if version.document_id in {item.document_id for item in self._cv_versions.values()}:
            raise ValueError("candidate_cv_document_exists")
        cv_id = self._cvs.get(version.candidate_id)
        if cv_id is None:
            cv_id = version.candidate_cv_id
            self._cvs[version.candidate_id] = cv_id
        elif cv_id != version.candidate_cv_id:
            raise ValueError("candidate_cv_mismatch")
        if any(item.candidate_id == version.candidate_id and item.version == version.version for item in self._cv_versions.values()):
            raise ValueError("candidate_cv_version_exists")
        self._cv_versions[version.cv_version_id] = version.model_copy(deep=True)
        return version.model_copy(deep=True)

    async def get_review_action(
        self, candidate_id: UUID, idempotency_key: str
    ) -> CandidateReviewActionRecord | None:
        item = self._review_actions.get((candidate_id, idempotency_key))
        return item.model_copy(deep=True) if item else None

    async def save_review_action(self, action: CandidateReviewActionRecord) -> None:
        key = (action.candidate_id, action.idempotency_key)
        if key in self._review_actions:
            raise ValueError("candidate_review_idempotency_exists")
        self._review_actions[key] = action.model_copy(deep=True)

    async def update(self, candidate: Candidate) -> Candidate:
        if candidate.candidate_id not in self._candidates:
            raise KeyError(candidate.candidate_id)
        self._candidates[candidate.candidate_id] = candidate.model_copy(deep=True)
        return candidate.model_copy(deep=True)

    async def attach_document(self, document: CandidateDocument) -> CandidateDocument:
        if document.candidate_id not in self._candidates:
            raise KeyError(document.candidate_id)
        if any(
            item.candidate_id == document.candidate_id and item.document_id == document.document_id
            for item in self._documents.values()
        ):
            raise ValueError("candidate_document_exists")
        if document.is_primary:
            for key, item in tuple(self._documents.items()):
                if item.candidate_id == document.candidate_id and item.is_primary:
                    self._documents[key] = item.model_copy(update={"is_primary": False})
        self._documents[document.candidate_document_id] = document.model_copy(deep=True)
        return document.model_copy(deep=True)

    async def list_documents(self, candidate_id: UUID) -> tuple[CandidateDocument, ...]:
        return tuple(
            item.model_copy(deep=True)
            for item in self._documents.values()
            if item.candidate_id == candidate_id
        )

    async def list_candidate_ids_for_document(self, document_id: UUID) -> tuple[UUID, ...]:
        return tuple(
            item.candidate_id for item in self._documents.values() if item.document_id == document_id
        )

    async def get_candidate_document_reference(
        self, candidate_id: UUID, document_id: UUID
    ) -> UUID | None:
        return next(
            (
                item.candidate_document_id
                for item in self._documents.values()
                if item.candidate_id == candidate_id and item.document_id == document_id
            ),
            None,
        )

    async def link_profile(self, profile: CandidateProfileLink) -> CandidateProfileLink:
        if profile.candidate_id not in self._candidates:
            raise KeyError(profile.candidate_id)
        if await self.get_profile_link(profile.candidate_id, profile.profile_id):
            raise ValueError("candidate_profile_exists")
        if not any(
            item.candidate_id == profile.candidate_id and item.document_id == profile.document_id
            for item in self._documents.values()
        ):
            raise ValueError("candidate_document_required")
        if profile.governance_version is None:
            versions = [
                item.governance_version
                for item in self._profiles.values()
                if item.candidate_id == profile.candidate_id and item.governance_version is not None
            ]
            profile = profile.model_copy(update={"governance_version": max(versions, default=0) + 1})
        elif any(
            item.candidate_id == profile.candidate_id
            and item.governance_version == profile.governance_version
            for item in self._profiles.values()
        ):
            raise ValueError("candidate_governance_version_exists")
        self._profiles[profile.candidate_profile_id] = profile.model_copy(deep=True)
        return profile.model_copy(deep=True)

    async def set_current_profile(self, candidate_id: UUID, profile_id: str) -> Candidate:
        candidate = self._candidates.get(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        profile = await self.get_profile_link(candidate_id, profile_id)
        if profile is None:
            raise ValueError("candidate_profile_not_found")
        if profile.review_state is not CandidateReviewState.ACCEPTED:
            raise ValueError("candidate_current_profile_not_accepted")
        updated = candidate.model_copy(
            update={
                "current_profile_id": profile.profile_id,
                "current_profile_version": profile.profile_version,
                "review_state": CandidateReviewState.ACCEPTED,
                "updated_at": datetime.now(UTC),
            }
        )
        self._candidates[candidate_id] = updated
        return updated.model_copy(deep=True)

    async def promote_current_profile(
        self, candidate_id: UUID, profile_id: str, governance_version: int
    ) -> Candidate:
        candidate = self._candidates.get(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        target = await self.get_profile_link(candidate_id, profile_id)
        if target is None:
            raise ValueError("candidate_profile_not_found")
        if target.governance_version != governance_version:
            raise ValueError("candidate_profile_governance_conflict")
        if target.review_state is not CandidateReviewState.ACCEPTED:
            raise ValueError("candidate_current_profile_not_accepted")
        current = (
            await self.get_profile_link(candidate_id, candidate.current_profile_id)
            if candidate.current_profile_id is not None
            else None
        )
        if current is not None and (current.governance_version or 0) >= governance_version:
            return candidate.model_copy(deep=True)
        updated = candidate.model_copy(
            update={
                "current_profile_id": target.profile_id,
                "current_profile_version": target.profile_version,
                "review_state": CandidateReviewState.ACCEPTED,
                "updated_at": datetime.now(UTC),
            }
        )
        self._candidates[candidate_id] = updated
        return updated.model_copy(deep=True)

    async def update_profile_link(self, profile: CandidateProfileLink) -> CandidateProfileLink:
        if profile.candidate_profile_id not in self._profiles:
            raise KeyError(profile.candidate_profile_id)
        self._profiles[profile.candidate_profile_id] = profile.model_copy(deep=True)
        return profile.model_copy(deep=True)

    async def get_profile_link(self, candidate_id: UUID, profile_id: str) -> CandidateProfileLink | None:
        return next(
            (
                item.model_copy(deep=True)
                for item in self._profiles.values()
                if item.candidate_id == candidate_id and item.profile_id == profile_id
            ),
            None,
        )

    async def list_profiles(self, candidate_id: UUID) -> tuple[CandidateProfileLink, ...]:
        return tuple(
            item.model_copy(deep=True)
            for item in self._profiles.values()
            if item.candidate_id == candidate_id
        )

    async def list_claims(self, candidate_id: UUID) -> tuple[CandidateClaim, ...]:
        return tuple(
            item.model_copy(deep=True)
            for item in self._claims.values()
            if item.candidate_id == candidate_id
        )

    async def get_claim(self, candidate_id: UUID, claim_id: UUID) -> CandidateClaim | None:
        item = self._claims.get(claim_id)
        return item.model_copy(deep=True) if item and item.candidate_id == candidate_id else None

    async def create_claims(
        self, candidate_id: UUID, claims: Sequence[CandidateClaim], evidence: Sequence[CandidateEvidence]
    ) -> tuple[CandidateClaim, ...]:
        if candidate_id not in self._candidates:
            raise KeyError(candidate_id)
        existing_keys = {
            (item.profile_id, item.bucket, item.claim_index)
            for item in self._claims.values()
            if item.candidate_id == candidate_id
        }
        if any((item.profile_id, item.bucket, item.claim_index) in existing_keys for item in claims):
            raise ValueError("candidate_claim_exists")
        evidence_by_claim: dict[UUID, list[UUID]] = {}
        for evidence_item in evidence:
            if evidence_item.candidate_id != candidate_id or evidence_item.claim_id not in {claim.claim_id for claim in claims}:
                raise ValueError("candidate_evidence_invalid")
            self._evidence[evidence_item.evidence_id] = evidence_item.model_copy(deep=True)
            evidence_by_claim.setdefault(evidence_item.claim_id, []).append(evidence_item.evidence_id)
        stored: list[CandidateClaim] = []
        for claim_item in claims:
            evidence_ids = evidence_by_claim.get(claim_item.claim_id, [])
            updated = claim_item.model_copy(
                update={"evidence_ids": evidence_ids, "evidence_available": bool(evidence_ids)}
            )
            self._claims[claim_item.claim_id] = updated.model_copy(deep=True)
            stored.append(updated)
        return tuple(item.model_copy(deep=True) for item in stored)

    async def list_evidence(self, candidate_id: UUID, claim_id: UUID) -> tuple[CandidateEvidence, ...]:
        return tuple(
            item.model_copy(deep=True)
            for item in self._evidence.values()
            if item.candidate_id == candidate_id and item.claim_id == claim_id
        )


class SqlAlchemyCandidateRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, candidate: Candidate) -> Candidate:
        async with self._session_factory() as session, session.begin():
            session.add(_candidate_record(candidate))
        return candidate.model_copy(deep=True)

    async def get(self, candidate_id: UUID) -> Candidate | None:
        async with self._session_factory() as session:
            record = await session.get(CandidateRecord, candidate_id)
            return _candidate(record) if record else None

    async def list_candidates(
        self, organization_id: UUID, *, status: str | None = None, sort: str = "updated_at_desc", query: str | None = None
    ) -> tuple[Candidate, ...]:
        async with self._session_factory() as session:
            order_column = CandidateRecord.updated_at
            descending = sort.endswith("_desc")
            if sort.startswith("created_at"):
                order_column = CandidateRecord.created_at
            ordering = order_column.desc() if descending else order_column.asc()
            filters = [CandidateRecord.organization_id == organization_id]
            if status is not None:
                filters.append(CandidateRecord.status == status)
            if query:
                pattern = f"%{query}%"
                filters.append(
                    (CandidateRecord.candidate_code.ilike(pattern))
                    | (CandidateRecord.display_name.ilike(pattern))
                    | (CandidateRecord.primary_email.ilike(pattern))
                    | (CandidateRecord.primary_phone.ilike(pattern))
                )
            records = (
                await session.scalars(
                    select(CandidateRecord)
                    .where(*filters)
                    .order_by(ordering, CandidateRecord.id.desc() if descending else CandidateRecord.id.asc())
                )
            ).all()
            return tuple(_candidate(record) for record in records)

    async def list_cv_versions(self, candidate_id: UUID) -> tuple[CandidateCVVersion, ...]:
        async with self._session_factory() as session:
            rows = (await session.scalars(
                select(CandidateCVVersionRecord)
                .join(CandidateCVRecord, CandidateCVRecord.id == CandidateCVVersionRecord.candidate_cv_id)
                .where(CandidateCVRecord.candidate_id == candidate_id)
                .order_by(CandidateCVVersionRecord.version.desc())
            )).all()
            return tuple(_cv_version(row, candidate_id) for row in rows)

    async def create_cv_version(self, version: CandidateCVVersion) -> CandidateCVVersion:
        async with self._session_factory() as session, session.begin():
            if await session.get(CandidateRecord, version.candidate_id) is None:
                raise KeyError(version.candidate_id)
            cv = await session.scalar(
                select(CandidateCVRecord).where(CandidateCVRecord.candidate_id == version.candidate_id).with_for_update()
            )
            if cv is None:
                cv = CandidateCVRecord(id=version.candidate_cv_id, candidate_id=version.candidate_id)
                session.add(cv)
                await session.flush()
            elif cv.id != version.candidate_cv_id:
                raise ValueError("candidate_cv_mismatch")
            latest = await session.scalar(
                select(CandidateCVVersionRecord.version)
                .where(CandidateCVVersionRecord.candidate_cv_id == cv.id)
                .order_by(CandidateCVVersionRecord.version.desc())
            )
            if latest is not None and version.version != latest + 1:
                raise ValueError("candidate_cv_version_conflict")
            session.add(CandidateCVVersionRecord(
                id=version.cv_version_id,
                candidate_cv_id=cv.id,
                version=version.version,
                document_id=version.document_id,
                created_by_actor_id=version.created_by_actor_id,
                created_at=version.created_at,
            ))
        return version.model_copy(deep=True)

    async def get_review_action(
        self, candidate_id: UUID, idempotency_key: str
    ) -> CandidateReviewActionRecord | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CandidateReviewActionRecordModel).where(
                    CandidateReviewActionRecordModel.candidate_id == candidate_id,
                    CandidateReviewActionRecordModel.idempotency_key == idempotency_key,
                )
            )
            return _review_action(record) if record else None

    async def save_review_action(self, action: CandidateReviewActionRecord) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                CandidateReviewActionRecordModel(
                    candidate_id=action.candidate_id,
                    idempotency_key=action.idempotency_key,
                    action=action.action,
                    version=action.version,
                )
            )

    async def update(self, candidate: Candidate) -> Candidate:
        async with self._session_factory() as session, session.begin():
            record = await session.get(CandidateRecord, candidate.candidate_id, with_for_update=True)
            if record is None:
                raise KeyError(candidate.candidate_id)
            record.organization_id = candidate.organization_id
            record.candidate_code = candidate.candidate_code or f"CAN-{candidate.candidate_id.hex[:12].upper()}"
            record.display_name = candidate.display_name
            record.primary_email = candidate.primary_email
            record.primary_phone = candidate.primary_phone
            record.created_by_actor_id = candidate.created_by_actor_id
            record.status = candidate.status.value
            record.review_state = candidate.review_state.value
            record.current_profile_id = candidate.current_profile_id
            record.current_profile_version = candidate.current_profile_version
            record.updated_at = datetime.now(UTC)
            await session.flush()
            return _candidate(record)

    async def attach_document(self, document: CandidateDocument) -> CandidateDocument:
        async with self._session_factory() as session, session.begin():
            if await session.get(CandidateRecord, document.candidate_id) is None:
                raise KeyError(document.candidate_id)
            existing = await session.scalar(
                select(CandidateDocumentRecord).where(
                    CandidateDocumentRecord.candidate_id == document.candidate_id,
                    CandidateDocumentRecord.document_id == document.document_id,
                )
            )
            if existing is not None:
                raise ValueError("candidate_document_exists")
            if document.is_primary:
                records = (
                    await session.scalars(
                        select(CandidateDocumentRecord).where(
                            CandidateDocumentRecord.candidate_id == document.candidate_id
                        )
                    )
                ).all()
                for record in records:
                    record.is_primary = False
            session.add(_document_record(document))
        return document.model_copy(deep=True)

    async def list_documents(self, candidate_id: UUID) -> tuple[CandidateDocument, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(CandidateDocumentRecord)
                    .where(CandidateDocumentRecord.candidate_id == candidate_id)
                    .order_by(CandidateDocumentRecord.attached_at, CandidateDocumentRecord.id)
                )
            ).all()
            return tuple(_document(record) for record in records)

    async def list_candidate_ids_for_document(self, document_id: UUID) -> tuple[UUID, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(CandidateDocumentRecord.candidate_id).where(
                        CandidateDocumentRecord.document_id == document_id
                    )
                )
            ).all()
            return tuple(records)

    async def get_candidate_document_reference(
        self, candidate_id: UUID, document_id: UUID
    ) -> UUID | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CandidateDocumentRecord).where(
                    CandidateDocumentRecord.candidate_id == candidate_id,
                    CandidateDocumentRecord.document_id == document_id,
                )
            )
            return record.id if record else None

    async def link_profile(self, profile: CandidateProfileLink) -> CandidateProfileLink:
        async with self._session_factory() as session, session.begin():
            candidate = await session.get(CandidateRecord, profile.candidate_id, with_for_update=True)
            if candidate is None:
                raise KeyError(profile.candidate_id)
            existing = await session.scalar(
                select(CandidateProfileRecord).where(
                    CandidateProfileRecord.candidate_id == profile.candidate_id,
                    CandidateProfileRecord.profile_id == profile.profile_id,
                )
            )
            if existing is not None:
                raise ValueError("candidate_profile_exists")
            document = await session.scalar(
                select(CandidateDocumentRecord).where(
                    CandidateDocumentRecord.candidate_id == profile.candidate_id,
                    CandidateDocumentRecord.document_id == profile.document_id,
                )
            )
            if document is None:
                raise ValueError("candidate_document_required")
            if profile.governance_version is None:
                latest = await session.scalar(
                    select(func.max(CandidateProfileRecord.governance_version)).where(
                        CandidateProfileRecord.candidate_id == profile.candidate_id
                    )
                )
                profile = profile.model_copy(update={"governance_version": (latest or 0) + 1})
            else:
                duplicate = await session.scalar(
                    select(CandidateProfileRecord.id).where(
                        CandidateProfileRecord.candidate_id == profile.candidate_id,
                        CandidateProfileRecord.governance_version == profile.governance_version,
                    )
                )
                if duplicate is not None:
                    raise ValueError("candidate_governance_version_exists")
            session.add(_profile_record(profile))
        return profile.model_copy(deep=True)

    async def set_current_profile(self, candidate_id: UUID, profile_id: str) -> Candidate:
        async with self._session_factory() as session, session.begin():
            candidate = await session.get(CandidateRecord, candidate_id, with_for_update=True)
            if candidate is None:
                raise KeyError(candidate_id)
            record = await session.scalar(
                select(CandidateProfileRecord).where(
                    CandidateProfileRecord.candidate_id == candidate_id,
                    CandidateProfileRecord.profile_id == profile_id,
                )
            )
            if record is None:
                raise ValueError("candidate_profile_not_found")
            if record.review_state != CandidateReviewState.ACCEPTED.value:
                raise ValueError("candidate_current_profile_not_accepted")
            candidate.current_profile_id = record.profile_id
            candidate.current_profile_version = record.profile_version
            candidate.review_state = CandidateReviewState.ACCEPTED.value
            candidate.updated_at = datetime.now(UTC)
            await session.flush()
            return _candidate(candidate)

    async def promote_current_profile(
        self, candidate_id: UUID, profile_id: str, governance_version: int
    ) -> Candidate:
        async with self._session_factory() as session, session.begin():
            candidate = await session.get(CandidateRecord, candidate_id, with_for_update=True)
            if candidate is None:
                raise KeyError(candidate_id)
            target = await session.scalar(
                select(CandidateProfileRecord).where(
                    CandidateProfileRecord.candidate_id == candidate_id,
                    CandidateProfileRecord.profile_id == profile_id,
                )
            )
            if target is None:
                raise ValueError("candidate_profile_not_found")
            if target.governance_version != governance_version:
                raise ValueError("candidate_profile_governance_conflict")
            if target.review_state != CandidateReviewState.ACCEPTED.value:
                raise ValueError("candidate_current_profile_not_accepted")
            current = None
            if candidate.current_profile_id is not None:
                current = await session.scalar(
                    select(CandidateProfileRecord).where(
                        CandidateProfileRecord.candidate_id == candidate_id,
                        CandidateProfileRecord.profile_id == candidate.current_profile_id,
                    )
                )
            if current is not None and current.governance_version >= governance_version:
                return _candidate(candidate)
            candidate.current_profile_id = target.profile_id
            candidate.current_profile_version = target.profile_version
            candidate.review_state = CandidateReviewState.ACCEPTED.value
            candidate.updated_at = datetime.now(UTC)
            await session.flush()
            return _candidate(candidate)

    async def update_profile_link(self, profile: CandidateProfileLink) -> CandidateProfileLink:
        async with self._session_factory() as session, session.begin():
            record = await session.get(CandidateProfileRecord, profile.candidate_profile_id, with_for_update=True)
            if record is None:
                raise KeyError(profile.candidate_profile_id)
            record.profile_version = profile.profile_version
            record.review_state = profile.review_state.value
            record.document_id = profile.document_id
            await session.flush()
        return profile.model_copy(deep=True)

    async def get_profile_link(self, candidate_id: UUID, profile_id: str) -> CandidateProfileLink | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CandidateProfileRecord).where(
                    CandidateProfileRecord.candidate_id == candidate_id,
                    CandidateProfileRecord.profile_id == profile_id,
                )
            )
            return _profile(record) if record else None

    async def list_profiles(self, candidate_id: UUID) -> tuple[CandidateProfileLink, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(CandidateProfileRecord)
                    .where(CandidateProfileRecord.candidate_id == candidate_id)
                    .order_by(CandidateProfileRecord.linked_at, CandidateProfileRecord.id)
                )
            ).all()
            return tuple(_profile(record) for record in records)

    async def list_claims(self, candidate_id: UUID) -> tuple[CandidateClaim, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(CandidateClaimRecord)
                    .where(CandidateClaimRecord.candidate_id == candidate_id)
                    .order_by(CandidateClaimRecord.profile_version, CandidateClaimRecord.id)
                )
            ).all()
            evidence = await self._evidence_by_candidate(session, candidate_id)
            return tuple(_claim(record, evidence) for record in records)

    async def get_claim(self, candidate_id: UUID, claim_id: UUID) -> CandidateClaim | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CandidateClaimRecord).where(
                    CandidateClaimRecord.candidate_id == candidate_id,
                    CandidateClaimRecord.id == claim_id,
                )
            )
            if record is None:
                return None
            evidence = await self._evidence_by_candidate(session, candidate_id)
            return _claim(record, evidence)

    async def create_claims(
        self, candidate_id: UUID, claims: Sequence[CandidateClaim], evidence: Sequence[CandidateEvidence]
    ) -> tuple[CandidateClaim, ...]:
        async with self._session_factory() as session, session.begin():
            if await session.get(CandidateRecord, candidate_id) is None:
                raise KeyError(candidate_id)
            for item in claims:
                duplicate = await session.scalar(
                    select(CandidateClaimRecord).where(
                        CandidateClaimRecord.candidate_id == candidate_id,
                        CandidateClaimRecord.profile_id == item.profile_id,
                        CandidateClaimRecord.bucket == item.bucket,
                        CandidateClaimRecord.claim_index == item.claim_index,
                    )
                )
                if duplicate is not None:
                    raise ValueError("candidate_claim_exists")
            evidence_by_claim: dict[UUID, list[UUID]] = {}
            claim_ids = {item.claim_id for item in claims}
            for evidence_item in evidence:
                if evidence_item.candidate_id != candidate_id or evidence_item.claim_id not in claim_ids:
                    raise ValueError("candidate_evidence_invalid")
                session.add(_evidence_record(evidence_item))
                evidence_by_claim.setdefault(evidence_item.claim_id, []).append(evidence_item.evidence_id)
            for item in claims:
                session.add(_claim_record(item))
            await session.flush()
            return tuple(item.model_copy(update={"evidence_ids": evidence_by_claim.get(item.claim_id, [])}) for item in claims)

    async def list_evidence(self, candidate_id: UUID, claim_id: UUID) -> tuple[CandidateEvidence, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(CandidateEvidenceRecord)
                    .where(
                        CandidateEvidenceRecord.candidate_id == candidate_id,
                        CandidateEvidenceRecord.claim_id == claim_id,
                    )
                    .order_by(CandidateEvidenceRecord.id)
                )
            ).all()
            return tuple(_evidence(record) for record in records)

    async def _evidence_by_candidate(self, session: AsyncSession, candidate_id: UUID) -> dict[UUID, list[UUID]]:
        records = (
            await session.scalars(
                select(CandidateEvidenceRecord).where(CandidateEvidenceRecord.candidate_id == candidate_id)
            )
        ).all()
        result: dict[UUID, list[UUID]] = {}
        for record in records:
            result.setdefault(record.claim_id, []).append(record.id)
        return result


def _candidate_record(candidate: Candidate) -> CandidateRecord:
    return CandidateRecord(
        id=candidate.candidate_id,
        candidate_code=candidate.candidate_code or f"CAN-{candidate.candidate_id.hex[:12].upper()}",
        display_name=candidate.display_name,
        primary_email=candidate.primary_email,
        primary_phone=candidate.primary_phone,
        organization_id=candidate.organization_id,
        created_by_actor_id=candidate.created_by_actor_id,
        status=candidate.status.value,
        review_state=candidate.review_state.value,
        current_profile_id=candidate.current_profile_id,
        current_profile_version=candidate.current_profile_version,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


def _candidate(record: CandidateRecord) -> Candidate:
    from app.candidate.schemas import CandidateReviewState, CandidateStatus

    return Candidate(
        candidate_id=record.id,
        candidate_code=getattr(record, "candidate_code", f"CAN-{record.id.hex[:12].upper()}"),
        display_name=getattr(record, "display_name", None),
        primary_email=getattr(record, "primary_email", None),
        primary_phone=getattr(record, "primary_phone", None),
        organization_id=record.organization_id,
        created_by_actor_id=record.created_by_actor_id,
        status=CandidateStatus(record.status),
        review_state=CandidateReviewState(record.review_state),
        current_profile_id=record.current_profile_id,
        current_profile_version=record.current_profile_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _candidate_matches(candidate: Candidate, query: str) -> bool:
    needle = query.casefold()
    return any(
        needle in (value or "").casefold()
        for value in (candidate.candidate_code, candidate.display_name, candidate.primary_email, candidate.primary_phone)
    )


def _cv_version(record: CandidateCVVersionRecord, candidate_id: UUID) -> CandidateCVVersion:
    return CandidateCVVersion(
        cv_version_id=record.id,
        candidate_id=candidate_id,
        candidate_cv_id=record.candidate_cv_id,
        version=record.version,
        document_id=record.document_id,
        created_by_actor_id=record.created_by_actor_id,
        created_at=record.created_at,
    )


def _review_action(record: CandidateReviewActionRecordModel) -> CandidateReviewActionRecord:
    return CandidateReviewActionRecord(
        candidate_id=record.candidate_id,
        idempotency_key=record.idempotency_key,
        action=record.action,
        version=record.version,
    )


def _document_record(document: CandidateDocument) -> CandidateDocumentRecord:
    return CandidateDocumentRecord(
        id=document.candidate_document_id,
        candidate_id=document.candidate_id,
        document_id=document.document_id,
        document_kind=document.kind.value,
        is_primary=document.is_primary,
        attached_at=document.attached_at,
    )


def _document(record: CandidateDocumentRecord) -> CandidateDocument:
    from app.documents.schemas import DocumentKind

    return CandidateDocument(
        candidate_document_id=record.id,
        candidate_id=record.candidate_id,
        document_id=record.document_id,
        kind=DocumentKind(record.document_kind),
        is_primary=record.is_primary,
        attached_at=record.attached_at,
    )


def _profile_record(profile: CandidateProfileLink) -> CandidateProfileRecord:
    return CandidateProfileRecord(
        id=profile.candidate_profile_id,
        candidate_id=profile.candidate_id,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        governance_version=profile.governance_version,
        document_id=profile.document_id,
        review_state=profile.review_state.value,
        linked_at=profile.linked_at,
    )


def _profile(record: CandidateProfileRecord) -> CandidateProfileLink:
    from app.candidate.schemas import CandidateReviewState

    return CandidateProfileLink(
        candidate_profile_id=record.id,
        candidate_id=record.candidate_id,
        profile_id=record.profile_id,
        profile_version=record.profile_version,
        governance_version=record.governance_version,
        document_id=record.document_id,
        review_state=CandidateReviewState(record.review_state),
        linked_at=record.linked_at,
    )


def _claim_record(claim: CandidateClaim) -> CandidateClaimRecord:
    return CandidateClaimRecord(
        id=claim.claim_id,
        candidate_id=claim.candidate_id,
        profile_id=claim.profile_id,
        profile_version=claim.profile_version,
        bucket=claim.bucket,
        claim_index=claim.claim_index,
        value=claim.value,
        evidence_type=claim.evidence_type,
        evidence_status=claim.evidence_status,
        context=claim.context,
        confidence=claim.confidence,
    )


def _claim(record: CandidateClaimRecord, evidence: dict[UUID, list[UUID]]) -> CandidateClaim:
    return CandidateClaim(
        claim_id=record.id,
        candidate_id=record.candidate_id,
        profile_id=record.profile_id,
        profile_version=record.profile_version,
        bucket=record.bucket,
        claim_index=record.claim_index,
        value=record.value,
        evidence_type=record.evidence_type,
        evidence_status=record.evidence_status,
        context=record.context,
        confidence=record.confidence,
        evidence_ids=evidence.get(record.id, []),
        evidence_available=bool(evidence.get(record.id, [])),
    )


def _evidence_record(evidence: CandidateEvidence) -> CandidateEvidenceRecord:
    return CandidateEvidenceRecord(
        id=evidence.evidence_id,
        candidate_id=evidence.candidate_id,
        claim_id=evidence.claim_id,
        document_id=evidence.document_id,
        source_locator=evidence.source_locator,
        excerpt=evidence.excerpt,
        evidence_type=evidence.evidence_type,
        context=evidence.context,
        confidence=evidence.confidence,
        provenance=evidence.provenance,
    )


def _evidence(record: CandidateEvidenceRecord) -> CandidateEvidence:
    return CandidateEvidence(
        evidence_id=record.id,
        claim_id=record.claim_id,
        candidate_id=record.candidate_id,
        document_id=record.document_id,
        source_locator=record.source_locator,
        excerpt=record.excerpt,
        evidence_type=record.evidence_type,
        context=record.context,
        confidence=record.confidence,
        provenance=record.provenance,
    )
