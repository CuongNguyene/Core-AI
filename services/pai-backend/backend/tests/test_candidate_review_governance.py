from uuid import UUID

import pytest

from app.authorization.fixtures import ORG_PAI_ID, REVIEWER_ID
from app.authorization.repository import InMemorySubjectRepository
from app.authorization.service import DevelopmentIdentityAdapter
from app.candidate.errors import CandidateDomainError
from app.candidate.repository import InMemoryCandidateRepository
from app.candidate.schemas import CandidateReviewState
from app.candidate.service import CandidateService
from app.documents.repository import InMemoryDocumentRepository
from app.documents.schemas import DocumentKind, DocumentStatus, StoredDocument
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.schemas import (
    CVExtractionOutput,
    EvidenceStatus,
    EvidenceType,
    ExtractedClaim,
    ExtractionJob,
    ExtractionProfile,
    JobStatus,
    ReviewState,
    SourceLocator,
)
from app.extraction.schemas import DocumentKind as ExtractionDocumentKind

DOC_A = UUID("61111111-1111-1111-1111-111111111111")
DOC_B = UUID("62222222-2222-2222-2222-222222222222")


def _document(document_id: UUID) -> StoredDocument:
    from datetime import UTC, datetime, timedelta

    return StoredDocument(
        id=document_id,
        owner_actor_id=REVIEWER_ID,
        organization_id=ORG_PAI_ID,
        kind=DocumentKind.CV,
        content_type="application/pdf",
        byte_size=10,
        sha256="c" * 64,
        object_key=f"candidate/{document_id}.pdf",
        status=DocumentStatus.CLEAN,
        retention_until=datetime.now(UTC) + timedelta(days=1),
    )


def _profile(profile_id: str, document_id: UUID) -> ExtractionProfile:
    return ExtractionProfile(
        id=profile_id,
        job_id=f"job-{profile_id}",
        document_id=str(document_id),
        document_kind=ExtractionDocumentKind.CV,
        owner_actor_id=REVIEWER_ID,
        version=1,
        review_state=ReviewState.PENDING_REVIEW,
        output=CVExtractionOutput(
            skills=[
                ExtractedClaim(
                    value=profile_id,
                    evidence_type=EvidenceType.EXPLICIT_SKILL,
                    confidence=0.9,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_locator=SourceLocator(
                        document_id=str(document_id), section="skills", start_offset=1, end_offset=4
                    ),
                    source_excerpt=profile_id,
                )
            ],
            experience=[],
            education=[],
        ),
        audit={"source": "06b2-test"},
    )


async def _fixture() -> tuple[CandidateService, InMemoryCandidateRepository, object]:
    documents = InMemoryDocumentRepository()
    await documents.create(_document(DOC_A))
    await documents.create(_document(DOC_B))
    extractions = InMemoryExtractionRepository()
    for profile_id, document_id in (("profile-a", DOC_A), ("profile-b", DOC_B)):
        await extractions.enqueue(
            ExtractionJob(
                id=f"job-{profile_id}",
                document_id=str(document_id),
                document_kind=ExtractionDocumentKind.CV,
                owner_actor_id=REVIEWER_ID,
                correlation_id=f"correlation-{profile_id}",
                status=JobStatus.QUEUED,
            )
        )
        await extractions.mark_succeeded(f"job-{profile_id}", _profile(profile_id, document_id))
    repository = InMemoryCandidateRepository()
    return CandidateService(repository, documents, extractions), repository, extractions


async def _linked_candidate(service: CandidateService, profile_ids: tuple[str, ...]):
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await service.create(actor)
    for index, profile_id in enumerate(profile_ids):
        document_id = (DOC_A, DOC_B)[index]
        await service.attach_document(candidate.candidate_id, document_id, index == 0, actor)
        await service.link_profile(candidate.candidate_id, profile_id, actor)
    return candidate, actor


@pytest.mark.asyncio
async def test_exact_accept_promotes_highest_governance_and_does_not_regress() -> None:
    service, repository, _ = await _fixture()
    candidate, actor = await _linked_candidate(service, ("profile-a", "profile-b"))
    links = await repository.list_profiles(candidate.candidate_id)
    low, high = sorted(links, key=lambda item: item.governance_version or 0)

    accepted_high = await service.review_exact(
        candidate.candidate_id, high.profile_id, high.governance_version, actor, "accept", None, "exact-high"
    )
    accepted_low = await service.review_exact(
        candidate.candidate_id, low.profile_id, low.governance_version, actor, "accept", None, "exact-low"
    )

    assert accepted_high.current_profile_id == high.profile_id
    assert accepted_low.current_profile_id == high.profile_id
    assert (await service.get(candidate.candidate_id, actor)).current_profile_id == high.profile_id


@pytest.mark.asyncio
async def test_exact_target_rejects_wrong_governance_and_cross_profile() -> None:
    service, repository, _ = await _fixture()
    candidate, actor = await _linked_candidate(service, ("profile-a", "profile-b"))
    links = await repository.list_profiles(candidate.candidate_id)
    target = links[0]

    with pytest.raises(CandidateDomainError, match="candidate_profile_governance_conflict"):
        await service.review_exact(
            candidate.candidate_id, target.profile_id, (target.governance_version or 0) + 1,
            actor, "accept", None, "wrong-governance"
        )

    with pytest.raises(CandidateDomainError, match="candidate_profile_not_found"):
        await service.review_exact(
            candidate.candidate_id, "profile-not-linked", target.governance_version,
            actor, "accept", None, "wrong-profile"
        )


@pytest.mark.asyncio
async def test_exact_reject_does_not_promote_and_is_idempotent() -> None:
    service, repository, _ = await _fixture()
    candidate, actor = await _linked_candidate(service, ("profile-a", "profile-b"))
    target = (await repository.list_profiles(candidate.candidate_id))[1]

    first = await service.review_exact(
        candidate.candidate_id, target.profile_id, target.governance_version, actor, "reject", "not usable", "exact-reject"
    )
    second = await service.review_exact(
        candidate.candidate_id, target.profile_id, target.governance_version, actor, "reject", "not usable", "exact-reject"
    )

    assert first.current_profile_id is None
    assert second.current_profile_id is None
    assert (await repository.get_profile_link(candidate.candidate_id, target.profile_id)).review_state is CandidateReviewState.REJECTED
