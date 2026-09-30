from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.authorization.fixtures import ORG_PAI_ID, REVIEWER_ID
from app.candidate.repository import InMemoryCandidateRepository
from app.candidate.schemas import (
    Candidate,
    CandidateClaim,
    CandidateDocument,
    CandidateEvidence,
    CandidateProfileLink,
    CandidateReviewState,
    CandidateStatus,
)
from app.documents.schemas import DocumentKind


def candidate() -> Candidate:
    now = datetime.now(UTC)
    return Candidate(
        candidate_id=uuid4(),
        organization_id=ORG_PAI_ID,
        created_by_actor_id=REVIEWER_ID,
        status=CandidateStatus.ACTIVE,
        review_state=CandidateReviewState.DRAFT,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_candidate_identity_is_independent_and_document_profile_links_are_persisted() -> None:
    repository = InMemoryCandidateRepository()
    current = candidate()
    stored = await repository.create(current)

    assert stored.candidate_id != UUID("00000000-0000-0000-0000-000000000001")
    document = CandidateDocument(
        candidate_document_id=uuid4(),
        candidate_id=current.candidate_id,
        document_id=uuid4(),
        kind=DocumentKind.CV,
        is_primary=True,
        attached_at=datetime.now(UTC),
    )
    profile = CandidateProfileLink(
        candidate_profile_id=uuid4(),
        candidate_id=current.candidate_id,
        profile_id="profile-1",
        profile_version=2,
        document_id=document.document_id,
        review_state=CandidateReviewState.ACCEPTED,
        linked_at=datetime.now(UTC),
    )
    await repository.attach_document(document)
    profile = await repository.link_profile(profile)

    assert (await repository.get(current.candidate_id)) == current
    assert (await repository.list_documents(current.candidate_id)) == (document,)
    assert (await repository.list_profiles(current.candidate_id)) == (profile,)
    assert document.document_id != current.candidate_id
    assert profile.profile_id != str(current.candidate_id)


@pytest.mark.asyncio
async def test_claim_and_evidence_ids_round_trip_and_duplicate_profile_claim_is_rejected() -> None:
    repository = InMemoryCandidateRepository()
    current = candidate()
    await repository.create(current)
    claim = CandidateClaim(
        claim_id=uuid4(),
        candidate_id=current.candidate_id,
        profile_id="profile-1",
        profile_version=1,
        bucket="skills",
        claim_index=0,
        value="Python",
        evidence_type="explicit_skill",
        evidence_status="supported",
        context="mentioned",
        confidence=0.9,
        evidence_ids=[],
    )
    evidence = CandidateEvidence(
        evidence_id=uuid4(),
        claim_id=claim.claim_id,
        candidate_id=current.candidate_id,
        document_id=uuid4(),
        source_locator={"section": "skills", "start_offset": 1, "end_offset": 7},
        excerpt="Python",
        evidence_type="explicit_skill",
        context="mentioned",
        confidence=0.9,
        provenance={"profile_id": "profile-1", "profile_version": 1},
    )
    await repository.create_claims(current.candidate_id, [claim], [evidence])

    assert await repository.get_claim(current.candidate_id, claim.claim_id) == claim.model_copy(
        update={"evidence_ids": [evidence.evidence_id], "evidence_available": True}
    )
    assert await repository.list_evidence(current.candidate_id, claim.claim_id) == (evidence,)
    with pytest.raises(ValueError, match="candidate_claim_exists"):
        await repository.create_claims(current.candidate_id, [claim], [evidence])


@pytest.mark.asyncio
async def test_missing_candidate_is_not_created_by_link_commands() -> None:
    repository = InMemoryCandidateRepository()
    with pytest.raises(KeyError):
        await repository.attach_document(
            CandidateDocument(
                candidate_document_id=uuid4(),
                candidate_id=uuid4(),
                document_id=uuid4(),
                kind=DocumentKind.CV,
                is_primary=True,
                attached_at=datetime.now(UTC),
            )
        )
