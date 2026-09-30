import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.authorization.fixtures import ORG_PAI_ID, REVIEWER_ID
from app.candidate.repository import InMemoryCandidateRepository
from app.candidate.schemas import (
    Candidate,
    CandidateDocument,
    CandidateProfileLink,
    CandidateReviewState,
    CandidateStatus,
)
from app.documents.schemas import DocumentKind


def _candidate() -> Candidate:
    return Candidate(
        candidate_id=uuid4(),
        candidate_code=f"CAN-{uuid4().hex[:12].upper()}",
        organization_id=ORG_PAI_ID,
        created_by_actor_id=REVIEWER_ID,
        status=CandidateStatus.ACTIVE,
        review_state=CandidateReviewState.DRAFT,
    )


def _profile(candidate_id: UUID, document_id: UUID, profile_id: str, state: CandidateReviewState) -> CandidateProfileLink:
    return CandidateProfileLink(
        candidate_profile_id=uuid4(),
        candidate_id=candidate_id,
        profile_id=profile_id,
        profile_version=1,
        governance_version=None,
        document_id=document_id,
        review_state=state,
        linked_at=datetime.now(UTC),
    )


def test_governance_version_is_distinct_from_legacy_profile_version() -> None:
    profile = _profile(uuid4(), uuid4(), "profile-1", CandidateReviewState.PENDING_REVIEW)

    assert profile.profile_version == 1
    assert profile.governance_version is None


def test_in_memory_repository_allocates_monotonic_governance_versions() -> None:
    async def scenario() -> tuple[CandidateProfileLink, CandidateProfileLink]:
        repository = InMemoryCandidateRepository()
        candidate = _candidate()
        await repository.create(candidate)
        document_a = CandidateDocument(
            candidate_document_id=uuid4(),
            candidate_id=candidate.candidate_id,
            document_id=uuid4(),
            kind=DocumentKind.CV,
        )
        document_b = document_a.model_copy(
            update={"candidate_document_id": uuid4(), "document_id": uuid4()}
        )
        await repository.attach_document(document_a)
        await repository.attach_document(document_b)
        first = await repository.link_profile(
            _profile(candidate.candidate_id, document_a.document_id, "profile-1", CandidateReviewState.PENDING_REVIEW)
        )
        second = await repository.link_profile(
            _profile(candidate.candidate_id, document_b.document_id, "profile-2", CandidateReviewState.PENDING_REVIEW)
        )
        return first, second

    first, second = asyncio.run(scenario())
    assert first.governance_version == 1
    assert second.governance_version == 2
    assert first.profile_version == second.profile_version == 1


def test_current_profile_guard_rejects_pending_and_accepts_exact_accepted_profile() -> None:
    async def scenario() -> None:
        repository = InMemoryCandidateRepository()
        candidate = _candidate()
        await repository.create(candidate)
        document = CandidateDocument(
            candidate_document_id=uuid4(),
            candidate_id=candidate.candidate_id,
            document_id=uuid4(),
            kind=DocumentKind.CV,
        )
        await repository.attach_document(document)
        pending = await repository.link_profile(
            _profile(candidate.candidate_id, document.document_id, "pending", CandidateReviewState.PENDING_REVIEW)
        )
        with pytest.raises(ValueError, match="candidate_current_profile_not_accepted"):
            await repository.set_current_profile(candidate.candidate_id, pending.profile_id)

        accepted = pending.model_copy(
            update={
                "profile_id": "accepted",
                "governance_version": None,
                "review_state": CandidateReviewState.ACCEPTED,
            }
        )
        await repository.link_profile(accepted)
        updated = await repository.set_current_profile(candidate.candidate_id, accepted.profile_id)
        assert updated.current_profile_id == accepted.profile_id

    asyncio.run(scenario())
