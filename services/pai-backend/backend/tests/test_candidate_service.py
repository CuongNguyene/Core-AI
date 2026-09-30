from datetime import UTC, datetime, timedelta
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
from app.documents.schemas import DocumentKind as StoredDocumentKind
from app.documents.schemas import DocumentStatus, StoredDocument
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.schemas import (
    CapabilityEvidence,
    CapabilityItem,
    CapabilityMappingStatus,
    CVExtractionOutput,
    CVFullExtractionOutputV2,
    DocumentKind,
    EducationItem,
    EvidenceStatus,
    EvidenceStrength,
    EvidenceType,
    ExperienceItem,
    ExtractedClaim,
    ExtractionJob,
    ExtractionProfile,
    JobStatus,
    ReviewState,
    SourceLocator,
)

DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")


def document() -> StoredDocument:
    return StoredDocument(
        id=DOCUMENT_ID,
        owner_actor_id=REVIEWER_ID,
        organization_id=ORG_PAI_ID,
        kind=StoredDocumentKind.CV,
        content_type="application/pdf",
        byte_size=10,
        sha256="a" * 64,
        object_key="candidate/test.pdf",
        status=DocumentStatus.CLEAN,
        retention_until=datetime.now(UTC) + timedelta(days=1),
    )


def profile(state: ReviewState = ReviewState.PENDING_REVIEW) -> ExtractionProfile:
    return ExtractionProfile(
        id="profile-1",
        job_id="job-1",
        document_id=str(DOCUMENT_ID),
            document_kind=DocumentKind.CV,
        owner_actor_id=REVIEWER_ID,
        version=1,
        review_state=state,
        accepted_by=REVIEWER_ID if state is ReviewState.ACCEPTED else None,
        accepted_at=datetime.now(UTC) if state is ReviewState.ACCEPTED else None,
        output=CVExtractionOutput(
            skills=[
                ExtractedClaim(
                    value="Python",
                    evidence_type=EvidenceType.EXPLICIT_SKILL,
                    confidence=0.9,
                    evidence_status=EvidenceStatus.SUPPORTED,
                    source_locator=SourceLocator(
                        document_id=str(DOCUMENT_ID),
                        section="skills",
                        start_offset=1,
                        end_offset=7,
                    ),
                    source_excerpt="Python",
                )
            ],
            experience=[],
            education=[],
        ),
        audit={"source": "test"},
    )


async def service() -> tuple[CandidateService, InMemoryCandidateRepository, InMemoryExtractionRepository]:
    documents = InMemoryDocumentRepository()
    await documents.create(document())
    extractions = InMemoryExtractionRepository()
    await extractions.enqueue(
        ExtractionJob(
            id="job-1",
            document_id=str(DOCUMENT_ID),
            document_kind=DocumentKind.CV,
            owner_actor_id=REVIEWER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await extractions.mark_succeeded("job-1", profile())
    repository = InMemoryCandidateRepository()
    return CandidateService(repository, documents, extractions), repository, extractions


@pytest.mark.asyncio
async def test_link_pending_profile_then_accept_materializes_stable_claim_and_evidence() -> None:
    candidate_service, repository, _ = await service()
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await candidate_service.create(actor)
    await candidate_service.attach_document(candidate.candidate_id, DOCUMENT_ID, True, actor)
    link = await candidate_service.link_profile(candidate.candidate_id, "profile-1", actor)

    assert link.review_state is CandidateReviewState.PENDING_REVIEW
    pending = await repository.list_claims(candidate.candidate_id)
    assert pending == ()

    accepted = await candidate_service.review(
        candidate.candidate_id,
        actor,
        "accept",
        1,
        None,
        "review-1",
    )
    claims = await repository.list_claims(candidate.candidate_id)
    assert accepted.review_state is CandidateReviewState.ACCEPTED
    assert accepted.current_profile_version == 1
    assert len(claims) == 1
    assert claims[0].claim_id != UUID("00000000-0000-0000-0000-000000000000")
    evidence = await repository.list_evidence(candidate.candidate_id, claims[0].claim_id)
    assert len(evidence) == 1
    assert evidence[0].document_id == DOCUMENT_ID
    assert evidence[0].provenance["profile_id"] == "profile-1"


@pytest.mark.asyncio
async def test_extraction_status_exposes_the_latest_failed_job() -> None:
    candidate_service, _repository, extractions = await service()
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await candidate_service.create(actor)
    await candidate_service.attach_document(candidate.candidate_id, DOCUMENT_ID, True, actor)
    await extractions.enqueue(
        ExtractionJob(
            id="job-2",
            document_id=str(DOCUMENT_ID),
            document_kind=DocumentKind.CV,
            owner_actor_id=REVIEWER_ID,
            correlation_id="2fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await extractions.mark_failed("job-2", "grounding_validation_failed")

    status = await candidate_service.extraction_status(candidate.candidate_id, actor)

    assert status.status == "failed"
    assert status.documents[0].status == "failed"
    assert status.latest_error == (
        "The extracted evidence could not be validated against the source document."
    )


def v2_profile() -> ExtractionProfile:
    return profile().model_copy(
        update={
            "output": CVFullExtractionOutputV2(
                candidate_summary="HR specialist with recruiting experience.",
                experience=[
                    ExperienceItem(
                        title="Recruitment Specialist",
                        company="Acme",
                        responsibilities=["Managed hiring pipeline"],
                        evidence=[
                            CapabilityEvidence(
                                source_excerpt="Managed hiring pipeline",
                                source_locator=SourceLocator(
                                    document_id=str(DOCUMENT_ID),
                                    section="experience",
                                    start_offset=10,
                                    end_offset=34,
                                ),
                                evidence_strength=EvidenceStrength.DEMONSTRATED_IN_ROLE,
                                confidence=0.92,
                            )
                        ],
                    )
                ],
                capabilities=[
                    CapabilityItem(
                        raw_name="Talent Acquisition",
                        canonical_name="Talent Acquisition",
                        category="CORE",
                        mapping_status=CapabilityMappingStatus.UNMAPPED_BUT_GROUNDED,
                        supporting_experience_refs=["exp-1"],
                        evidence=[
                            CapabilityEvidence(
                                source_excerpt="Managed hiring pipeline",
                                source_locator=SourceLocator(
                                    document_id=str(DOCUMENT_ID),
                                    section="experience",
                                    start_offset=10,
                                    end_offset=34,
                                ),
                                evidence_strength=EvidenceStrength.DEMONSTRATED_IN_ROLE,
                                confidence=0.92,
                            )
                        ],
                    )
                ],
                tools_platforms=[],
                education=[EducationItem(degree="MBA")],
            ),
            "audit": {
                "pipeline_mode": "two_stage",
                "capability_mode": "discovery",
                "taxonomy_id": "professional_capability_core",
                "taxonomy_version": "0.1",
                "provider": "must-not-leak",
                "raw_prompt": "must-not-leak",
            },
        }
    )


@pytest.mark.asyncio
async def test_pending_v2_extraction_review_is_projected_without_canonical_claims() -> None:
    documents = InMemoryDocumentRepository()
    await documents.create(document())
    extractions = InMemoryExtractionRepository()
    await extractions.enqueue(
        ExtractionJob(
            id="job-v2",
            document_id=str(DOCUMENT_ID),
            document_kind=DocumentKind.CV,
            owner_actor_id=REVIEWER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await extractions.mark_succeeded("job-v2", v2_profile())
    repository = InMemoryCandidateRepository()
    candidate_service = CandidateService(repository, documents, extractions)
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await candidate_service.create(actor)
    await candidate_service.attach_document(candidate.candidate_id, DOCUMENT_ID, True, actor)
    await candidate_service.link_profile(candidate.candidate_id, "profile-1", actor)

    review = await candidate_service.extraction_review(candidate.candidate_id, actor)

    assert review is not None
    assert review["review_state"] == "pending_review"
    assert review["capabilities"][0]["kind"] == "capability"
    assert review["capabilities"][0]["review_item_id"]
    assert review["experience"][0]["review_item_id"]
    assert review["education"][0]["review_item_id"]
    assert review["capabilities"][0]["mapping_status"] == "unmapped_but_grounded"
    assert review["experience"][0]["evidence"][0]["source_excerpt"] == "Managed hiring pipeline"
    assert review["safe_metadata"] == {
        "pipeline_mode": "two_stage",
        "capability_mode": "discovery",
        "taxonomy_id": "professional_capability_core",
        "taxonomy_version": "0.1",
    }
    review_text = str(review)
    for private_key in ("provider", "raw_prompt", "source_reference", "objective_refs"):
        assert private_key not in review_text
    assert await repository.list_claims(candidate.candidate_id) == ()


@pytest.mark.asyncio
async def test_review_item_ids_are_deterministic_within_profile_version() -> None:
    documents = InMemoryDocumentRepository()
    await documents.create(document())
    extractions = InMemoryExtractionRepository()
    await extractions.enqueue(
        ExtractionJob(
            id="job-v2",
            document_id=str(DOCUMENT_ID),
            document_kind=DocumentKind.CV,
            owner_actor_id=REVIEWER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await extractions.mark_succeeded("job-v2", v2_profile())
    repository = InMemoryCandidateRepository()
    candidate_service = CandidateService(repository, documents, extractions)
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await candidate_service.create(actor)
    await candidate_service.attach_document(candidate.candidate_id, DOCUMENT_ID, True, actor)
    await candidate_service.link_profile(candidate.candidate_id, "profile-1", actor)

    first = await candidate_service.extraction_review(candidate.candidate_id, actor)
    second = await candidate_service.extraction_review(candidate.candidate_id, actor)

    assert first is not None and second is not None
    assert first["capabilities"][0]["review_item_id"] == second["capabilities"][0]["review_item_id"]
    assert first["experience"][0]["review_item_id"] == second["experience"][0]["review_item_id"]
    assert first["capabilities"][0]["review_item_id"] != first["experience"][0]["review_item_id"]


@pytest.mark.asyncio
async def test_extraction_review_is_none_without_linked_profile() -> None:
    candidate_service, _, _ = await service()
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await candidate_service.create(actor)

    assert await candidate_service.extraction_review(candidate.candidate_id, actor) is None


@pytest.mark.asyncio
async def test_accept_uses_latest_corrected_profile_version() -> None:
    documents = InMemoryDocumentRepository()
    await documents.create(document())
    extractions = InMemoryExtractionRepository()
    await extractions.enqueue(
        ExtractionJob(
            id="job-v2",
            document_id=str(DOCUMENT_ID),
            document_kind=DocumentKind.CV,
            owner_actor_id=REVIEWER_ID,
            correlation_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            status=JobStatus.QUEUED,
        )
    )
    await extractions.mark_succeeded("job-v2", v2_profile())
    repository = InMemoryCandidateRepository()
    candidate_service = CandidateService(repository, documents, extractions)
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await candidate_service.create(actor)
    await candidate_service.attach_document(candidate.candidate_id, DOCUMENT_ID, True, actor)
    await candidate_service.link_profile(candidate.candidate_id, "profile-1", actor)

    corrected = await extractions.create_correction("profile-1", REVIEWER_ID, v2_profile().output)
    await candidate_service.link_profile(candidate.candidate_id, corrected.id, actor)
    accepted = await candidate_service.review(candidate.candidate_id, actor, "accept", 2, None, "accept-v2")

    assert accepted.current_profile_id == corrected.id
    assert accepted.current_profile_version == 2
    assert accepted.review_state is CandidateReviewState.ACCEPTED


@pytest.mark.asyncio
async def test_successful_extraction_association_links_profile_without_materializing_evidence() -> None:
    candidate_service, repository, _ = await service()
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await candidate_service.create(actor)
    await candidate_service.attach_document(candidate.candidate_id, DOCUMENT_ID, True, actor)

    links = await candidate_service.associate_extraction_profile("profile-1")

    assert len(links) == 1
    linked = await repository.list_profiles(candidate.candidate_id)
    assert linked[0].review_state is CandidateReviewState.PENDING_REVIEW
    assert await repository.list_claims(candidate.candidate_id) == ()
    current = await candidate_service.get(candidate.candidate_id, actor)
    assert current.current_profile_id is None




@pytest.mark.asyncio
async def test_profile_link_is_idempotent_and_does_not_alias_candidate_id() -> None:
    candidate_service, repository, extractions = await service()
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await candidate_service.create(actor)
    await candidate_service.attach_document(candidate.candidate_id, DOCUMENT_ID, True, actor)
    first = await candidate_service.link_profile(candidate.candidate_id, "profile-1", actor)
    second = await candidate_service.link_profile(candidate.candidate_id, "profile-1", actor)

    assert first.candidate_profile_id == second.candidate_profile_id
    assert str(candidate.candidate_id) != "profile-1"
    assert len(await repository.list_profiles(candidate.candidate_id)) == 1
    assert await extractions.get_profile("profile-1") is not None


@pytest.mark.asyncio
async def test_candidate_read_rejects_actor_from_another_organization() -> None:
    candidate_service, _, _ = await service()
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await candidate_service.create(actor)
    foreign_actor = actor.model_copy(
        update={"organization_id": UUID("99999999-9999-9999-9999-999999999999")}
    )

    with pytest.raises(CandidateDomainError, match="candidate_access_denied"):
        await candidate_service.get(candidate.candidate_id, foreign_actor)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["request_revision", "reject"])
async def test_accepted_profile_cannot_be_transitioned_without_correction(action: str) -> None:
    candidate_service, _, _ = await service()
    actor = await DevelopmentIdentityAdapter(InMemorySubjectRepository.fixture()).resolve(REVIEWER_ID)
    candidate = await candidate_service.create(actor)
    await candidate_service.attach_document(candidate.candidate_id, DOCUMENT_ID, True, actor)
    await candidate_service.link_profile(candidate.candidate_id, "profile-1", actor)
    await candidate_service.review(
        candidate.candidate_id,
        actor,
        "accept",
        1,
        None,
        "review-accepted",
    )

    with pytest.raises(CandidateDomainError, match="candidate_profile_not_editable"):
        await candidate_service.review(
            candidate.candidate_id,
            actor,
            action,
            1,
            None,
            f"review-{action}",
        )
