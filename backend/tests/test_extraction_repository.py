from datetime import UTC, datetime, timedelta

import pytest

from app.authorization.fixtures import LEARNER_ID, REVIEWER_ID
from app.extraction.errors import ExtractionProfileStateConflict, ExtractionProfileVersionConflict
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.schemas import (
    CVExtractionOutput,
    DocumentKind,
    EvidenceStatus,
    ExtractedClaim,
    ExtractionJob,
    ExtractionStage,
    ExtractionProfile,
    JobStatus,
    ReviewState,
    SourceLocator,
)


def queued_job() -> ExtractionJob:
    return ExtractionJob(
        id="job-1",
        document_id="fixture-cv-basic",
        document_kind=DocumentKind.CV,
        owner_actor_id=LEARNER_ID,
        correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        status=JobStatus.QUEUED,
    )


def pending_profile() -> ExtractionProfile:
    return ExtractionProfile(
        id="profile-1",
        job_id="job-1",
        document_id="fixture-cv-basic",
        document_kind=DocumentKind.CV,
        owner_actor_id=LEARNER_ID,
        version=1,
        review_state=ReviewState.PENDING_REVIEW,
        output=CVExtractionOutput(
            skills=[
                ExtractedClaim(
                    value="Python",
                    confidence=0.9,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_locator=SourceLocator(
                        document_id="fixture-cv-basic",
                        section="skills",
                        start_offset=16,
                        end_offset=22,
                    ),
                    source_excerpt="Python",
                )
            ],
            experience=[],
            education=[],
        ),
        audit={
            "provider": "mock",
            "model": "mock-v1",
            "prompt_template_version": "1.0",
            "policy_version": "privacy-v1",
        },
    )


@pytest.mark.asyncio
async def test_claimed_job_transitions_to_succeeded_with_pending_profile() -> None:
    repository = InMemoryExtractionRepository()
    job = await repository.enqueue(queued_job())

    claimed = await repository.claim_next()
    assert claimed is not None
    assert claimed.status is JobStatus.RUNNING

    await repository.mark_succeeded(claimed.id, pending_profile())

    stored_job = await repository.get_job(job.id)
    stored_profile = await repository.get_profile("profile-1")
    assert stored_job is not None
    assert stored_job.status is JobStatus.SUCCEEDED
    assert stored_job.profile_id == "profile-1"
    assert stored_profile is not None
    assert stored_profile.review_state is ReviewState.PENDING_REVIEW


@pytest.mark.asyncio
async def test_active_job_persists_worker_stage_and_chunk_units() -> None:
    repository = InMemoryExtractionRepository()
    await repository.enqueue(queued_job())

    claimed = await repository.claim_next()
    assert claimed is not None
    assert claimed.stage is ExtractionStage.READING_DOCUMENT

    updated = await repository.update_progress(
        claimed.id,
        ExtractionStage.EXTRACTING,
        completed_units=2,
        total_units=5,
    )

    assert updated is not None
    assert updated.stage is ExtractionStage.EXTRACTING
    assert updated.completed_units == 2
    assert updated.total_units == 5


@pytest.mark.asyncio
async def test_watchdog_marks_stale_active_job_as_failed() -> None:
    repository = InMemoryExtractionRepository()
    stale = queued_job().model_copy(
        update={"updated_at": datetime.now(UTC) - timedelta(minutes=30)}
    )
    await repository.enqueue(stale)

    recovered = await repository.recover_stale_jobs(stale_after_seconds=60)
    stored = await repository.get_job(stale.id)

    assert recovered == 1
    assert stored is not None
    assert stored.status is JobStatus.FAILED
    assert stored.error_category == "worker_unresponsive"
    assert stored.error_details == {
        "failure_stage": "watchdog",
        "failure_code": "job_heartbeat_expired",
    }


@pytest.mark.asyncio
async def test_watchdog_does_not_fail_recent_heartbeating_job() -> None:
    repository = InMemoryExtractionRepository()
    await repository.enqueue(queued_job())
    claimed = await repository.claim_next()
    assert claimed is not None

    await repository.touch(claimed.id)
    recovered = await repository.recover_stale_jobs(stale_after_seconds=60)
    stored = await repository.get_job(claimed.id)

    assert recovered == 0
    assert stored is not None
    assert stored.status is JobStatus.RUNNING


@pytest.mark.asyncio
async def test_reviewer_correction_creates_new_profile_version() -> None:
    repository = InMemoryExtractionRepository()
    await repository.enqueue(queued_job())
    await repository.mark_succeeded("job-1", pending_profile())

    corrected = await repository.create_correction(
        profile_id="profile-1",
        reviewer_actor_id="reviewer-1",
        output=pending_profile().output,
    )

    assert corrected.version == 2
    assert corrected.review_state is ReviewState.CORRECTED
    assert corrected.id != "profile-1"


@pytest.mark.asyncio
async def test_reviewer_accepts_current_pending_profile() -> None:
    repository = InMemoryExtractionRepository()
    await repository.enqueue(queued_job())
    await repository.mark_succeeded("job-1", pending_profile())

    accepted = await repository.accept_profile("profile-1", REVIEWER_ID, expected_version=1)

    assert accepted.review_state is ReviewState.ACCEPTED
    assert accepted.accepted_by == REVIEWER_ID
    assert accepted.accepted_at is not None


@pytest.mark.asyncio
async def test_stale_accept_version_keeps_profile_pending() -> None:
    repository = InMemoryExtractionRepository()
    await repository.enqueue(queued_job())
    await repository.mark_succeeded("job-1", pending_profile())

    with pytest.raises(ExtractionProfileVersionConflict):
        await repository.accept_profile("profile-1", REVIEWER_ID, expected_version=2)

    stored = await repository.get_profile("profile-1")
    assert stored is not None
    assert stored.review_state is ReviewState.PENDING_REVIEW


@pytest.mark.asyncio
async def test_reviewer_can_request_revision_or_reject_pending_profile() -> None:
    repository = InMemoryExtractionRepository()
    await repository.enqueue(queued_job())
    await repository.mark_succeeded("job-1", pending_profile())

    revision = await repository.request_revision("profile-1", REVIEWER_ID, expected_version=1)
    assert revision.review_state is ReviewState.NEEDS_REVISION

    repository = InMemoryExtractionRepository()
    await repository.enqueue(queued_job())
    await repository.mark_succeeded("job-1", pending_profile())
    rejected = await repository.reject_profile("profile-1", REVIEWER_ID, expected_version=1)
    assert rejected.review_state is ReviewState.REJECTED


@pytest.mark.asyncio
async def test_correction_after_acceptance_creates_superseding_revision() -> None:
    repository = InMemoryExtractionRepository()
    await repository.enqueue(queued_job())
    await repository.mark_succeeded("job-1", pending_profile())
    await repository.accept_profile("profile-1", REVIEWER_ID, expected_version=1)

    revision = await repository.create_correction(
        profile_id="profile-1",
        reviewer_actor_id=REVIEWER_ID,
        output=pending_profile().output,
    )

    assert revision.review_state is ReviewState.CORRECTED
    assert revision.version == 2
    assert revision.supersedes_profile_id == "profile-1"


@pytest.mark.asyncio
async def test_correction_cannot_start_again_from_superseded_profile() -> None:
    repository = InMemoryExtractionRepository()
    await repository.enqueue(queued_job())
    await repository.mark_succeeded("job-1", pending_profile())
    await repository.accept_profile("profile-1", REVIEWER_ID, expected_version=1)
    revision = await repository.create_correction(
        profile_id="profile-1",
        reviewer_actor_id=REVIEWER_ID,
        output=pending_profile().output,
    )

    with pytest.raises(ExtractionProfileStateConflict):
        await repository.create_correction(
            profile_id="profile-1",
            reviewer_actor_id=REVIEWER_ID,
            output=pending_profile().output,
        )

    assert revision.review_state is ReviewState.CORRECTED
