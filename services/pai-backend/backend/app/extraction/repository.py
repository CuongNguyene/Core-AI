import inspect
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.extraction.capability_projection import project_v2_to_candidate_profile
from app.extraction.errors import ExtractionProfileStateConflict, ExtractionProfileVersionConflict
from app.extraction.fixtures import DocumentSource
from app.extraction.models import (
    ExtractionAuditEventRecord,
    ExtractionJobRecord,
    ExtractionProfileRecord,
)
from app.extraction.profile import CandidateProfile
from app.extraction.schemas import (
    CVExtractionOutput,
    CVFullExtractionOutputV2,
    DocumentKind,
    ExtractionJob,
    ExtractionStage,
    ExtractionProfile,
    JDExtractionOutput,
    JDRequirementExtractionOutputV2,
    JobStatus,
    ReviewState,
)

ExtractionOutput = (
    CVExtractionOutput
    | CVFullExtractionOutputV2
    | JDExtractionOutput
    | JDRequirementExtractionOutputV2
)


class ExtractionRepository(Protocol):
    async def enqueue(self, job: ExtractionJob) -> ExtractionJob: ...

    async def claim_next(self) -> ExtractionJob | None: ...

    async def update_progress(
        self,
        job_id: str,
        stage: ExtractionStage,
        completed_units: int | None = None,
        total_units: int | None = None,
    ) -> ExtractionJob | None: ...

    async def touch(self, job_id: str) -> None: ...

    async def recover_stale_jobs(self, stale_after_seconds: int) -> int: ...

    async def mark_succeeded(self, job_id: str, profile: ExtractionProfile) -> None: ...

    async def mark_failed(
        self,
        job_id: str,
        error_category: str,
        error_details: dict[str, object] | None = None,
    ) -> None: ...

    async def cancel(self, job_id: str) -> ExtractionJob: ...

    async def get_job(self, job_id: str) -> ExtractionJob | None: ...

    async def get_latest_job_for_document(
        self, document_id: str, document_kind: DocumentKind
    ) -> ExtractionJob | None: ...

    async def get_profile(self, profile_id: str) -> ExtractionProfile | None: ...

    async def list_profiles(self, document_kind: DocumentKind) -> list[ExtractionProfile]: ...

    async def is_superseded(self, profile_id: str) -> bool: ...

    async def delete_profile(self, profile_id: str) -> None: ...

    async def create_correction(
        self, profile_id: str, reviewer_actor_id: UUID, output: ExtractionOutput
    ) -> ExtractionProfile: ...

    async def accept_profile(
        self, profile_id: str, reviewer_actor_id: UUID, expected_version: int
    ) -> ExtractionProfile: ...

    async def request_revision(
        self, profile_id: str, reviewer_actor_id: UUID, expected_version: int
    ) -> ExtractionProfile: ...

    async def reject_profile(
        self, profile_id: str, reviewer_actor_id: UUID, expected_version: int
    ) -> ExtractionProfile: ...


class InMemoryExtractionRepository:
    """Deterministic repository used by API/worker tests only."""

    def __init__(self) -> None:
        self._jobs: dict[str, ExtractionJob] = {}
        self._profiles: dict[str, ExtractionProfile] = {}

    async def enqueue(self, job: ExtractionJob) -> ExtractionJob:
        if job.id in self._jobs:
            raise ValueError("Extraction job already exists")
        now = datetime.now(UTC)
        self._jobs[job.id] = job.model_copy(
            update={"created_at": job.created_at or now, "updated_at": job.updated_at or now},
            deep=True,
        )
        return self._jobs[job.id].model_copy(deep=True)

    async def claim_next(self) -> ExtractionJob | None:
        for job in self._jobs.values():
            if job.status is JobStatus.QUEUED:
                job.status = JobStatus.RUNNING
                job.stage = ExtractionStage.READING_DOCUMENT
                job.updated_at = datetime.now(UTC)
                return job.model_copy(deep=True)
        return None

    async def update_progress(
        self,
        job_id: str,
        stage: ExtractionStage,
        completed_units: int | None = None,
        total_units: int | None = None,
    ) -> ExtractionJob | None:
        job = self._require_job(job_id)
        if job.status is not JobStatus.RUNNING:
            return job.model_copy(deep=True)
        job.stage = stage
        job.completed_units = completed_units
        job.total_units = total_units
        job.updated_at = datetime.now(UTC)
        return job.model_copy(deep=True)

    async def touch(self, job_id: str) -> None:
        job = self._require_job(job_id)
        if job.status is JobStatus.RUNNING:
            job.updated_at = datetime.now(UTC)

    async def recover_stale_jobs(self, stale_after_seconds: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        recovered = 0
        for job in self._jobs.values():
            if (
                job.status in {JobStatus.QUEUED, JobStatus.RUNNING}
                and job.updated_at is not None
                and job.updated_at < cutoff
            ):
                job.status = JobStatus.FAILED
                job.error_category = "worker_unresponsive"
                job.error_details = {
                    "failure_stage": "watchdog",
                    "failure_code": "job_heartbeat_expired",
                }
                job.updated_at = datetime.now(UTC)
                recovered += 1
        return recovered

    async def mark_succeeded(self, job_id: str, profile: ExtractionProfile) -> None:
        job = self._require_job(job_id)
        if job.status is not JobStatus.RUNNING and job.status is not JobStatus.QUEUED:
            raise ValueError("Only active job can succeed")
        job.status = JobStatus.SUCCEEDED
        job.profile_id = profile.id
        job.updated_at = datetime.now(UTC)
        self._profiles[profile.id] = profile.model_copy(deep=True)

    async def mark_failed(
        self,
        job_id: str,
        error_category: str,
        error_details: dict[str, object] | None = None,
    ) -> None:
        job = self._require_job(job_id)
        if job.status is JobStatus.FAILED and job.error_category == "cancelled_by_user":
            return
        job.status = JobStatus.FAILED
        job.error_category = error_category
        job.error_details = error_details
        job.updated_at = datetime.now(UTC)

    async def cancel(self, job_id: str) -> ExtractionJob:
        job = self._require_job(job_id)
        if job.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
            raise ValueError("Only active job can be cancelled")
        job.status = JobStatus.FAILED
        job.error_category = "cancelled_by_user"
        job.error_details = {"failure_stage": "user_action", "failure_code": "cancelled"}
        job.updated_at = datetime.now(UTC)
        return job.model_copy(deep=True)

    async def get_job(self, job_id: str) -> ExtractionJob | None:
        job = self._jobs.get(job_id)
        return job.model_copy(deep=True) if job else None

    async def get_latest_job_for_document(
        self, document_id: str, document_kind: DocumentKind
    ) -> ExtractionJob | None:
        for job in reversed(tuple(self._jobs.values())):
            if job.document_id == document_id and job.document_kind == document_kind:
                return job.model_copy(deep=True)
        return None

    async def get_profile(self, profile_id: str) -> ExtractionProfile | None:
        profile = self._profiles.get(profile_id)
        return profile.model_copy(deep=True) if profile else None

    async def list_profiles(self, document_kind: DocumentKind) -> list[ExtractionProfile]:
        profiles = [profile for profile in self._profiles.values() if profile.document_kind is document_kind]
        superseded = {profile.supersedes_profile_id for profile in self._profiles.values() if profile.supersedes_profile_id}
        return [profile.model_copy(deep=True) for profile in profiles if profile.id not in superseded]

    async def is_superseded(self, profile_id: str) -> bool:
        return any(
            profile.supersedes_profile_id == profile_id for profile in self._profiles.values()
        )

    async def delete_profile(self, profile_id: str) -> None:
        if await self.is_superseded(profile_id):
            raise ExtractionProfileStateConflict(profile_id)
        profile = self._profiles.pop(profile_id, None)
        if profile is None:
            raise KeyError(profile_id)
        job = self._jobs.get(profile.job_id)
        if job is not None:
            job.profile_id = None

    async def create_correction(
        self, profile_id: str, reviewer_actor_id: UUID, output: ExtractionOutput
    ) -> ExtractionProfile:
        from app.extraction.profile_builder import build_candidate_profile_from_output

        previous = self._profiles.get(profile_id)
        if previous is None:
            raise KeyError(profile_id)
        if await self.is_superseded(profile_id):
            raise ExtractionProfileStateConflict(profile_id)
        candidate_profile = (
            project_v2_to_candidate_profile(output)
            if isinstance(output, CVFullExtractionOutputV2)
            else build_candidate_profile_from_output(output)
            if isinstance(output, CVExtractionOutput)
            else None
        )
        corrected = ExtractionProfile(
            id=str(uuid4()),
            job_id=previous.job_id,
            document_id=previous.document_id,
            document_kind=previous.document_kind,
            owner_actor_id=previous.owner_actor_id,
            version=previous.version + 1,
            review_state=ReviewState.CORRECTED,
            supersedes_profile_id=previous.id,
            output=output,
            candidate_profile=candidate_profile,
            audit={
                **previous.audit,
                "action": "profile_corrected",
                "actor_id": str(reviewer_actor_id),
            },
        )
        self._profiles[corrected.id] = corrected
        return corrected.model_copy(deep=True)

    async def accept_profile(
        self, profile_id: str, reviewer_actor_id: UUID, expected_version: int
    ) -> ExtractionProfile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise KeyError(profile_id)
        if profile.version != expected_version:
            raise ExtractionProfileVersionConflict(profile_id)
        if profile.review_state not in {ReviewState.PENDING_REVIEW, ReviewState.CORRECTED}:
            raise ExtractionProfileStateConflict(profile_id)
        accepted = profile.model_copy(
            update={
                "review_state": ReviewState.ACCEPTED,
                "accepted_by": reviewer_actor_id,
                "accepted_at": datetime.now(UTC),
                "audit": {
                    **profile.audit,
                    "action": "extraction_profile_accepted",
                    "actor_id": reviewer_actor_id,
                },
            }
        )
        self._profiles[profile_id] = accepted
        return accepted.model_copy(deep=True)

    async def request_revision(
        self, profile_id: str, reviewer_actor_id: UUID, expected_version: int
    ) -> ExtractionProfile:
        return self._transition_profile(
            profile_id, reviewer_actor_id, expected_version, ReviewState.NEEDS_REVISION
        )

    async def reject_profile(
        self, profile_id: str, reviewer_actor_id: UUID, expected_version: int
    ) -> ExtractionProfile:
        return self._transition_profile(
            profile_id, reviewer_actor_id, expected_version, ReviewState.REJECTED
        )

    def _transition_profile(
        self,
        profile_id: str,
        reviewer_actor_id: UUID,
        expected_version: int,
        state: ReviewState,
    ) -> ExtractionProfile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise KeyError(profile_id)
        if profile.version != expected_version:
            raise ExtractionProfileVersionConflict(profile_id)
        if profile.review_state not in {ReviewState.PENDING_REVIEW, ReviewState.CORRECTED}:
            raise ExtractionProfileStateConflict(profile_id)
        transitioned = profile.model_copy(
            update={
                "review_state": state,
                "audit": {
                    **profile.audit,
                    "action": f"extraction_profile_{state.value}",
                    "actor_id": reviewer_actor_id,
                },
            }
        )
        self._profiles[profile_id] = transitioned
        return transitioned.model_copy(deep=True)

    def _require_job(self, job_id: str) -> ExtractionJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job


class SqlAlchemyExtractionRepository:
    """Async PostgreSQL adapter for extraction jobs and review lifecycle."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        document_source: DocumentSource,
    ) -> None:
        self._session_factory = session_factory
        self._document_source = document_source

    async def enqueue(self, job: ExtractionJob) -> ExtractionJob:
        async with self._session_factory() as session, session.begin():
            session.add(
                ExtractionJobRecord(
                    id=job.id,
                    document_id=job.document_id,
                    document_kind=job.document_kind.value,
                    owner_actor_id=job.owner_actor_id,
                    correlation_id=job.correlation_id,
                    status=job.status.value,
                    stage=job.stage.value,
                    completed_units=job.completed_units,
                    total_units=job.total_units,
                    error_category=job.error_category,
                    error_details=job.error_details,
                    profile_id=job.profile_id,
                )
            )
        return job.model_copy(deep=True)

    async def claim_next(self) -> ExtractionJob | None:
        async with self._session_factory() as session, session.begin():
            record = await session.scalar(
                select(ExtractionJobRecord)
                .where(ExtractionJobRecord.status == JobStatus.QUEUED.value)
                .order_by(ExtractionJobRecord.created_at, ExtractionJobRecord.id)
                .with_for_update(skip_locked=True)
            )
            if record is None:
                return None
            record.status = JobStatus.RUNNING.value
            record.stage = ExtractionStage.READING_DOCUMENT.value
            record.updated_at = datetime.now(UTC)
            return self._job_from_record(record)

    async def update_progress(
        self,
        job_id: str,
        stage: ExtractionStage,
        completed_units: int | None = None,
        total_units: int | None = None,
    ) -> ExtractionJob | None:
        async with self._session_factory() as session, session.begin():
            job = await self._require_job_record(session, job_id)
            if job.status != JobStatus.RUNNING.value:
                return self._job_from_record(job)
            job.stage = stage.value
            job.completed_units = completed_units
            job.total_units = total_units
            job.updated_at = datetime.now(UTC)
            return self._job_from_record(job)

    async def touch(self, job_id: str) -> None:
        async with self._session_factory() as session, session.begin():
            job = await self._require_job_record(session, job_id)
            if job.status == JobStatus.RUNNING.value:
                job.updated_at = datetime.now(UTC)

    async def recover_stale_jobs(self, stale_after_seconds: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        async with self._session_factory() as session, session.begin():
            records = list(
                (await session.scalars(
                    select(ExtractionJobRecord)
                    .where(
                        ExtractionJobRecord.status.in_(
                            [JobStatus.QUEUED.value, JobStatus.RUNNING.value]
                        ),
                        ExtractionJobRecord.updated_at < cutoff,
                    )
                    .with_for_update(skip_locked=True)
                )).all()
            )
            for job in records:
                job.status = JobStatus.FAILED.value
                job.error_category = "worker_unresponsive"
                job.error_details = {
                    "failure_stage": "watchdog",
                    "failure_code": "job_heartbeat_expired",
                }
                job.updated_at = datetime.now(UTC)
            return len(records)

    async def mark_succeeded(self, job_id: str, profile: ExtractionProfile) -> None:
        async with self._session_factory() as session, session.begin():
            job = await self._require_job_record(session, job_id)
            if job.status not in {JobStatus.QUEUED.value, JobStatus.RUNNING.value}:
                raise ExtractionProfileStateConflict(job_id)
            session.add(self._profile_record(profile))
            job.status = JobStatus.SUCCEEDED.value
            job.profile_id = profile.id
            job.updated_at = datetime.now(UTC)

    async def mark_failed(
        self,
        job_id: str,
        error_category: str,
        error_details: dict[str, object] | None = None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            job = await self._require_job_record(session, job_id)
            if job.status == JobStatus.FAILED.value and job.error_category == "cancelled_by_user":
                return
            job.status = JobStatus.FAILED.value
            job.error_category = error_category
            job.error_details = error_details
            job.updated_at = datetime.now(UTC)

    async def cancel(self, job_id: str) -> ExtractionJob:
        async with self._session_factory() as session, session.begin():
            job = await self._require_job_record(session, job_id)
            if job.status not in {JobStatus.QUEUED.value, JobStatus.RUNNING.value}:
                raise ValueError("Only active job can be cancelled")
            job.status = JobStatus.FAILED.value
            job.error_category = "cancelled_by_user"
            job.error_details = {
                "failure_stage": "user_action",
                "failure_code": "cancelled",
            }
            job.updated_at = datetime.now(UTC)
            return self._job_from_record(job)

    async def get_job(self, job_id: str) -> ExtractionJob | None:
        async with self._session_factory() as session:
            record = await session.get(ExtractionJobRecord, job_id)
            return self._job_from_record(record) if record is not None else None

    async def get_latest_job_for_document(
        self, document_id: str, document_kind: DocumentKind
    ) -> ExtractionJob | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(ExtractionJobRecord)
                .where(
                    ExtractionJobRecord.document_id == document_id,
                    ExtractionJobRecord.document_kind == document_kind.value,
                )
                .order_by(ExtractionJobRecord.created_at.desc(), ExtractionJobRecord.id.desc())
            )
            return self._job_from_record(record) if record is not None else None

    async def get_profile(self, profile_id: str) -> ExtractionProfile | None:
        async with self._session_factory() as session:
            record = await session.get(ExtractionProfileRecord, profile_id)
            return self._profile_from_record(record) if record is not None else None

    async def list_profiles(self, document_kind: DocumentKind) -> list[ExtractionProfile]:
        async with self._session_factory() as session:
            records = list((await session.execute(
                select(ExtractionProfileRecord, ExtractionJobRecord.created_at)
                .join(ExtractionJobRecord, ExtractionJobRecord.id == ExtractionProfileRecord.job_id)
                .where(ExtractionProfileRecord.document_kind == document_kind.value)
                .order_by(ExtractionJobRecord.created_at.desc(), ExtractionProfileRecord.version.desc())
            )).all())
            superseded = {record.supersedes_profile_id for record, _ in records if record.supersedes_profile_id}
            return [
                self._profile_from_record(record, created_at=created_at)
                for record, created_at in records
                if record.id not in superseded
            ]

    async def is_superseded(self, profile_id: str) -> bool:
        async with self._session_factory() as session:
            return (
                await session.scalar(
                    select(ExtractionProfileRecord.id).where(
                        ExtractionProfileRecord.supersedes_profile_id == profile_id
                    )
                )
                is not None
            )

    async def delete_profile(self, profile_id: str) -> None:
        from app.role_profile_authoring.models import RoleProfileDraftRecord

        async with self._session_factory() as session, session.begin():
            profile = await self._require_profile_record(session, profile_id, lock=True)
            if await self.is_superseded(profile_id):
                raise ExtractionProfileStateConflict(profile_id)
            has_role_profile = await session.scalar(
                select(RoleProfileDraftRecord.id).where(
                    RoleProfileDraftRecord.source_jd_profile_id == profile_id
                )
            )
            if has_role_profile is not None:
                raise ExtractionProfileStateConflict(profile_id)
            job = await self._require_job_record(session, profile.job_id)
            job.profile_id = None
            await session.delete(profile)

    async def create_correction(
        self, profile_id: str, reviewer_actor_id: UUID, output: ExtractionOutput
    ) -> ExtractionProfile:
        from app.extraction.profile_builder import build_candidate_profile_from_output

        async with self._session_factory() as session, session.begin():
            previous = await self._require_profile_record(session, profile_id)
            if await self.is_superseded(profile_id):
                raise ExtractionProfileStateConflict(profile_id)
            candidate_profile = (
                project_v2_to_candidate_profile(output)
                if isinstance(output, CVFullExtractionOutputV2)
                else build_candidate_profile_from_output(output)
                if isinstance(output, CVExtractionOutput)
                else None
            )
            corrected = ExtractionProfile(
                id=str(uuid4()),
                job_id=previous.job_id,
                document_id=previous.document_id,
                document_kind=DocumentKind(previous.document_kind),
                owner_actor_id=previous.owner_actor_id,
                version=previous.version + 1,
                review_state=ReviewState.CORRECTED,
                supersedes_profile_id=previous.id,
                output=output,
                candidate_profile=candidate_profile,
                audit={
                    **previous.audit_metadata,
                    "action": "profile_corrected",
                    "actor_id": str(reviewer_actor_id),
                },
            )
            session.add(self._profile_record(corrected))
            return corrected

    async def accept_profile(
        self, profile_id: str, reviewer_actor_id: UUID, expected_version: int
    ) -> ExtractionProfile:
        async with self._session_factory() as session, session.begin():
            profile = await self._require_profile_record(session, profile_id, lock=True)
            if profile.version != expected_version:
                raise ExtractionProfileVersionConflict(profile_id)
            if profile.review_state not in {
                ReviewState.PENDING_REVIEW.value,
                ReviewState.CORRECTED.value,
            }:
                raise ExtractionProfileStateConflict(profile_id)
            document_result = self._document_source.get(
                profile.document_id, DocumentKind(profile.document_kind)
            )
            if inspect.isawaitable(document_result):
                await document_result
            accepted_at = datetime.now(UTC)
            profile.review_state = ReviewState.ACCEPTED.value
            profile.accepted_by = reviewer_actor_id
            profile.accepted_at = accepted_at
            await self._append_audit(
                session,
                job_id=profile.job_id,
                profile_id=profile.id,
                actor_id=reviewer_actor_id,
                action="EXTRACTION_PROFILE_ACCEPTED",
                metadata={"profile_version": profile.version},
            )
            return self._profile_from_record(profile)

    async def request_revision(
        self, profile_id: str, reviewer_actor_id: UUID, expected_version: int
    ) -> ExtractionProfile:
        return await self._transition_profile(
            profile_id, reviewer_actor_id, expected_version, ReviewState.NEEDS_REVISION
        )

    async def reject_profile(
        self, profile_id: str, reviewer_actor_id: UUID, expected_version: int
    ) -> ExtractionProfile:
        return await self._transition_profile(
            profile_id, reviewer_actor_id, expected_version, ReviewState.REJECTED
        )

    async def _transition_profile(
        self,
        profile_id: str,
        reviewer_actor_id: UUID,
        expected_version: int,
        state: ReviewState,
    ) -> ExtractionProfile:
        async with self._session_factory() as session, session.begin():
            profile = await self._require_profile_record(session, profile_id, lock=True)
            if profile.version != expected_version:
                raise ExtractionProfileVersionConflict(profile_id)
            if profile.review_state not in {
                ReviewState.PENDING_REVIEW.value,
                ReviewState.CORRECTED.value,
            }:
                raise ExtractionProfileStateConflict(profile_id)
            profile.review_state = state.value
            await self._append_audit(
                session,
                job_id=profile.job_id,
                profile_id=profile.id,
                actor_id=reviewer_actor_id,
                action=f"EXTRACTION_PROFILE_{state.value.upper()}",
                metadata={"profile_version": profile.version},
            )
            return self._profile_from_record(profile)

    async def _append_audit(
        self,
        session: AsyncSession,
        *,
        job_id: str,
        profile_id: str,
        actor_id: UUID,
        action: str,
        metadata: dict[str, object],
    ) -> None:
        session.add(
            ExtractionAuditEventRecord(
                id=str(uuid4()),
                job_id=job_id,
                profile_id=profile_id,
                actor_id=actor_id,
                action=action,
                audit_metadata=metadata,
            )
        )

    @staticmethod
    async def _require_job_record(session: AsyncSession, job_id: str) -> ExtractionJobRecord:
        record = await session.get(ExtractionJobRecord, job_id)
        if record is None:
            raise KeyError(job_id)
        return record

    @staticmethod
    async def _require_profile_record(
        session: AsyncSession, profile_id: str, *, lock: bool = False
    ) -> ExtractionProfileRecord:
        query = select(ExtractionProfileRecord).where(ExtractionProfileRecord.id == profile_id)
        if lock:
            query = query.with_for_update()
        record = await session.scalar(query)
        if record is None:
            raise KeyError(profile_id)
        return record

    @staticmethod
    def _job_from_record(record: ExtractionJobRecord) -> ExtractionJob:
        return ExtractionJob(
            id=record.id,
            document_id=record.document_id,
            document_kind=DocumentKind(record.document_kind),
            owner_actor_id=record.owner_actor_id,
            correlation_id=record.correlation_id,
            status=JobStatus(record.status),
            stage=ExtractionStage(record.stage),
            completed_units=record.completed_units,
            total_units=record.total_units,
            created_at=record.created_at,
            updated_at=record.updated_at,
            error_category=record.error_category,
            error_details=record.error_details,
            profile_id=record.profile_id,
        )

    @staticmethod
    def _profile_record(profile: ExtractionProfile) -> ExtractionProfileRecord:
        normalized_output = profile.output.model_dump(mode="json")
        if profile.candidate_profile is not None:
            normalized_output["_candidate_profile"] = profile.candidate_profile.model_dump(
                mode="json"
            )
        return ExtractionProfileRecord(
            id=profile.id,
            job_id=profile.job_id,
            document_id=profile.document_id,
            document_kind=profile.document_kind.value,
            owner_actor_id=profile.owner_actor_id,
            version=profile.version,
            review_state=profile.review_state.value,
            accepted_by=profile.accepted_by,
            accepted_at=profile.accepted_at,
            supersedes_profile_id=profile.supersedes_profile_id,
            normalized_output=normalized_output,
            audit_metadata=profile.audit,
        )

    @staticmethod
    def _profile_from_record(
        record: ExtractionProfileRecord, *, created_at: datetime | None = None
    ) -> ExtractionProfile:
        candidate_profile_payload = record.normalized_output.get("_candidate_profile")
        output_payload = {
            key: value
            for key, value in record.normalized_output.items()
            if key != "_candidate_profile"
        }
        output: ExtractionOutput
        if record.document_kind == DocumentKind.CV.value:
            output = (
                CVFullExtractionOutputV2.model_validate(output_payload, strict=False)
                if "capabilities" in output_payload
                else CVExtractionOutput.model_validate(output_payload, strict=False)
            )
        elif "requirements" in output_payload:
            output = JDRequirementExtractionOutputV2.model_validate(output_payload, strict=False)
        else:
            output = JDExtractionOutput.model_validate(output_payload, strict=False)
        return ExtractionProfile(
            id=record.id,
            job_id=record.job_id,
            document_id=record.document_id,
            document_kind=DocumentKind(record.document_kind),
            owner_actor_id=record.owner_actor_id,
            version=record.version,
            review_state=ReviewState(record.review_state),
            created_at=created_at,
            accepted_by=record.accepted_by,
            accepted_at=record.accepted_at,
            supersedes_profile_id=record.supersedes_profile_id,
            output=output,
            candidate_profile=(
                CandidateProfile.model_validate(candidate_profile_payload, strict=False)
                if isinstance(candidate_profile_payload, dict)
                else None
            ),
            audit=record.audit_metadata,
        )
