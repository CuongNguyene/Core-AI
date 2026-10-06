from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.authorization.schemas import ActorContext
from app.candidate.models import CandidateRecord
from app.candidate.schemas import CandidateReviewState, CandidateStatus
from app.candidate_source.domain import (
    CandidateSourceError,
    canonical_fingerprint,
    snapshot_disposition,
    source_content_fingerprint,
)
from app.candidate_source.models import (
    CandidateExternalEmployeeIdentityRecord,
    CandidateSourceSnapshotRecord,
    CandidateStructuredEvidenceRecord,
    OrganizationExternalMappingRecord,
)
from app.candidate_source.schemas import CandidateSourceEnvelope, EmployeeLearningProjectionV1


@dataclass(frozen=True)
class IngestedCandidateSnapshot:
    candidate_id: UUID
    snapshot_id: UUID
    source_revision: int
    fingerprint: str
    disposition: str
    current_snapshot_id: UUID | None


@dataclass(frozen=True)
class CurrentCandidateSourceSnapshot:
    candidate_id: UUID
    organization_id: UUID
    external_identity_id: UUID
    source_system: str
    employee_ref: str
    snapshot_id: UUID
    schema_id: str
    schema_version: str
    source_revision: int
    content_fingerprint: str
    payload: dict[str, object]


def is_external_identity_unique_violation(error: IntegrityError) -> bool:
    original = error.orig
    constraint_name = getattr(original, "constraint_name", None)
    if constraint_name is None:
        constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint_name == "uq_candidate_external_employee_identity":
        return True
    message = str(original).lower()
    return (
        "uq_candidate_external_employee_identity" in message
        or "candidate_external_employee_identities.organization_id, "
        "candidate_external_employee_identities.source_system, "
        "candidate_external_employee_identities.employee_ref"
        in message
    )


class SqlAlchemyCandidateSourceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_organization_mapping(
        self, *, organization_id: UUID, source_system: str, external_company_ref: str
    ) -> UUID:
        record_id = uuid4()
        async with self._session_factory() as session, session.begin():
            session.add(
                OrganizationExternalMappingRecord(
                    id=record_id,
                    organization_id=organization_id,
                    source_system=source_system,
                    external_company_ref=external_company_ref,
                    status="ACTIVE",
                )
            )
            try:
                await session.flush()
            except IntegrityError as exc:
                raise CandidateSourceError("organization_mapping_conflict") from exc
        return record_id

    async def list_snapshots(
        self, *, candidate_id: UUID, organization_id: UUID
    ) -> tuple[CandidateSourceSnapshotRecord, ...]:
        async with self._session_factory() as session:
            records = await session.scalars(
                select(CandidateSourceSnapshotRecord)
                .where(
                    CandidateSourceSnapshotRecord.candidate_id == candidate_id,
                    CandidateSourceSnapshotRecord.organization_id == organization_id,
                )
                .order_by(
                    CandidateSourceSnapshotRecord.ingested_at, CandidateSourceSnapshotRecord.id
                )
            )
            return tuple(records.all())

    async def get_current_snapshot(
        self, *, candidate_id: UUID, organization_id: UUID, source_system: str
    ) -> CurrentCandidateSourceSnapshot:
        """Read only the exact current snapshot selected by its source identity pointer."""
        if not source_system or source_system != source_system.strip():
            raise CandidateSourceError("candidate_source_identity_not_found")
        async with self._session_factory() as session:
            identities = list(
                (
                    await session.scalars(
                        select(CandidateExternalEmployeeIdentityRecord).where(
                            CandidateExternalEmployeeIdentityRecord.candidate_id == candidate_id,
                            CandidateExternalEmployeeIdentityRecord.organization_id
                            == organization_id,
                            CandidateExternalEmployeeIdentityRecord.source_system == source_system,
                        )
                    )
                ).all()
            )
            if len(identities) != 1:
                code = (
                    "candidate_source_identity_not_found"
                    if not identities
                    else "candidate_source_identity_ambiguous"
                )
                raise CandidateSourceError(code)

            identity = identities[0]
            if identity.current_snapshot_id is None:
                raise CandidateSourceError("candidate_source_current_snapshot_unavailable")
            snapshot = await session.scalar(
                select(CandidateSourceSnapshotRecord).where(
                    CandidateSourceSnapshotRecord.id == identity.current_snapshot_id,
                    CandidateSourceSnapshotRecord.external_identity_id == identity.id,
                    CandidateSourceSnapshotRecord.candidate_id == candidate_id,
                    CandidateSourceSnapshotRecord.organization_id == organization_id,
                    CandidateSourceSnapshotRecord.source_system == source_system,
                )
            )
            if snapshot is None:
                raise CandidateSourceError("candidate_source_current_snapshot_invalid")
            if (
                snapshot.source_revision is None
                or snapshot.source_revision <= 0
                or not snapshot.content_fingerprint
            ):
                raise CandidateSourceError("candidate_source_current_snapshot_unavailable")
            return CurrentCandidateSourceSnapshot(
                candidate_id=candidate_id,
                organization_id=organization_id,
                external_identity_id=identity.id,
                source_system=source_system,
                employee_ref=identity.employee_ref,
                snapshot_id=snapshot.id,
                schema_id=snapshot.schema_id,
                schema_version=snapshot.schema_version,
                source_revision=snapshot.source_revision,
                content_fingerprint=snapshot.content_fingerprint,
                payload=snapshot.payload,
            )

    async def ingest(
        self, envelope: CandidateSourceEnvelope, *, actor: ActorContext
    ) -> IngestedCandidateSnapshot:
        return await self._ingest_with_retry(envelope, actor=actor)

    async def ingest_learning_projection(
        self, projection: EmployeeLearningProjectionV1, *, actor: ActorContext
    ) -> IngestedCandidateSnapshot:
        return await self._ingest_with_retry(
            projection.to_candidate_source_envelope(), actor=actor, projection=projection
        )

    async def _ingest_with_retry(
        self,
        envelope: CandidateSourceEnvelope,
        *,
        actor: ActorContext,
        projection: EmployeeLearningProjectionV1 | None = None,
    ) -> IngestedCandidateSnapshot:
        try:
            return await self._ingest_once(envelope, actor=actor, projection=projection)
        except IntegrityError as exc:
            if not is_external_identity_unique_violation(exc):
                raise
        # A concurrent first write won the unique identity race. The failed
        # transaction is fully rolled back before this fresh transaction retries.
        return await self._ingest_once(envelope, actor=actor, projection=projection)

    async def _ingest_once(
        self,
        envelope: CandidateSourceEnvelope,
        *,
        actor: ActorContext,
        projection: EmployeeLearningProjectionV1 | None = None,
    ) -> IngestedCandidateSnapshot:
        payload = (
            projection.source_payload()
            if projection is not None
            else envelope.model_dump(mode="json")
        )
        fingerprint = canonical_fingerprint(payload)
        content_fingerprint = (
            canonical_fingerprint(projection.content_fingerprint_payload())
            if projection is not None
            else source_content_fingerprint(envelope)
        )
        source_system = envelope.identity.source_system
        employee_ref = envelope.identity.employee_ref
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            mapping = await session.scalar(
                select(OrganizationExternalMappingRecord).where(
                    OrganizationExternalMappingRecord.source_system == source_system,
                    OrganizationExternalMappingRecord.external_company_ref == envelope.company,
                    OrganizationExternalMappingRecord.status == "ACTIVE",
                )
            )
            if mapping is None:
                raise CandidateSourceError("organization_mapping_not_found")
            if mapping.organization_id != actor.organization_id:
                raise CandidateSourceError("candidate_source_organization_forbidden")

            identity = await session.scalar(
                select(CandidateExternalEmployeeIdentityRecord)
                .where(
                    CandidateExternalEmployeeIdentityRecord.organization_id
                    == mapping.organization_id,
                    CandidateExternalEmployeeIdentityRecord.source_system == source_system,
                    CandidateExternalEmployeeIdentityRecord.employee_ref == employee_ref,
                )
                .with_for_update()
            )
            if identity is None:
                candidate_id = uuid4()
                session.add(
                    CandidateRecord(
                        id=candidate_id,
                        candidate_code=f"CAN-{candidate_id.hex[:12].upper()}",
                        display_name=None,
                        primary_email=None,
                        primary_phone=None,
                        organization_id=mapping.organization_id,
                        created_by_actor_id=actor.actor_id,
                        status=CandidateStatus.ACTIVE.value,
                        review_state=CandidateReviewState.DRAFT.value,
                        created_at=now,
                        updated_at=now,
                    )
                )
                identity = CandidateExternalEmployeeIdentityRecord(
                    id=uuid4(),
                    candidate_id=candidate_id,
                    organization_id=mapping.organization_id,
                    source_system=source_system,
                    employee_ref=employee_ref,
                    current_snapshot_id=None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(identity)
                await session.flush()
            else:
                candidate_id = identity.candidate_id

            current_snapshot = None
            if identity.current_snapshot_id is not None:
                current_snapshot = await session.get(
                    CandidateSourceSnapshotRecord, identity.current_snapshot_id
                )
                if current_snapshot is None or current_snapshot.source_revision is None:
                    raise CandidateSourceError("candidate_source_current_revision_unavailable")
            disposition = snapshot_disposition(
                envelope.source_revision,
                content_fingerprint,
                current_revision=current_snapshot.source_revision if current_snapshot else None,
                current_content_fingerprint=current_snapshot.content_fingerprint
                if current_snapshot
                else None,
            )
            if disposition == "REPLAY":
                if current_snapshot is None:
                    raise CandidateSourceError("candidate_source_current_revision_unavailable")
                return IngestedCandidateSnapshot(
                    candidate_id,
                    current_snapshot.id,
                    envelope.source_revision,
                    current_snapshot.fingerprint,
                    "REPLAY",
                    identity.current_snapshot_id,
                )

            snapshot_id = uuid4()
            metadata = envelope.source_snapshot
            snapshot = CandidateSourceSnapshotRecord(
                id=snapshot_id,
                external_identity_id=identity.id,
                candidate_id=candidate_id,
                organization_id=mapping.organization_id,
                source_system=source_system,
                employee_ref=employee_ref,
                schema_id=projection.schema_id if projection is not None else envelope.schema_id,
                schema_version=projection.schema_version
                if projection is not None
                else envelope.schema_version,
                source_snapshot_ref=metadata.source_snapshot_ref,
                source_version=metadata.source_version,
                source_updated_at=metadata.source_updated_at,
                source_revision=envelope.source_revision,
                fingerprint=fingerprint,
                content_fingerprint=content_fingerprint,
                ordering_state="CURRENT",
                previous_snapshot_id=identity.current_snapshot_id,
                payload=payload,
                ingested_at=now,
            )
            session.add(snapshot)
            # The identity row points back to this snapshot. Flush the snapshot
            # before moving that pointer so the FK cycle is valid on PostgreSQL.
            await session.flush([snapshot])
            for path, record_ref, value in _source_values(payload):
                session.add(
                    CandidateStructuredEvidenceRecord(
                        id=uuid4(),
                        candidate_id=candidate_id,
                        snapshot_id=snapshot_id,
                        source_system=source_system,
                        employee_ref=employee_ref,
                        source_record_ref=record_ref,
                        source_field_path=path,
                        source_updated_at=metadata.source_updated_at,
                        source_version=metadata.source_version,
                        source_value=value,
                    )
                )
            identity.current_snapshot_id = snapshot_id
            identity.updated_at = now
            await session.flush()
            return IngestedCandidateSnapshot(
                candidate_id,
                snapshot_id,
                envelope.source_revision,
                fingerprint,
                disposition,
                identity.current_snapshot_id,
            )


def _source_values(payload: dict[str, object]) -> Iterator[tuple[str, str | None, object]]:
    excluded = {"schema_id", "schema_version"}

    def walk(
        value: object, path: str, record_ref: str | None
    ) -> Iterator[tuple[str, str | None, object]]:
        if isinstance(value, dict):
            next_ref = value.get("source_record_ref")
            if not isinstance(next_ref, str):
                next_ref = record_ref
            if not value:
                yield path, record_ref, value
            for key, child in value.items():
                if key == "source_record_ref":
                    yield f"{path}.{key}" if path else key, next_ref, child
                else:
                    yield from walk(child, f"{path}.{key}" if path else key, next_ref)
        elif isinstance(value, list):
            if not value:
                yield path, record_ref, value
            for index, child in enumerate(value):
                yield from walk(child, f"{path}[{index}]", record_ref)
        else:
            yield path, record_ref, value

    for key, value in payload.items():
        if key not in excluded:
            yield from walk(value, key, None)
