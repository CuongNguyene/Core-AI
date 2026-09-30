from __future__ import annotations

import base64
import builtins
import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from app.authorization.schemas import ActorContext, Role
from app.candidate.errors import CandidateDomainError
from app.candidate.repository import CandidateRepository
from app.candidate.schemas import (
    Candidate,
    CandidateClaim,
    CandidateCVVersion,
    CandidateDocument,
    CandidateEvidence,
    CandidateExtractionDocumentStatus,
    CandidateExtractionStatus,
    CandidateProfileLink,
    CandidateReviewActionRecord,
    CandidateReviewState,
    CandidateStatus,
)
from app.documents.repository import DocumentRepository
from app.extraction.evidence import EvidenceContext
from app.extraction.profile import CandidateProfile as ExtractionCandidateProfile
from app.extraction.repository import ExtractionRepository
from app.extraction.schemas import (
    CVExtractionOutput,
    CVFullExtractionOutputV2,
    DocumentKind,
    EvidenceStatus,
    EvidenceType,
    ExtractedClaim,
    ExtractionJob,
    ExtractionProfile,
    JobStatus,
    ReviewState,
)
from app.extraction.schemas import DocumentKind as ExtractionDocumentKind


class CandidateService:
    def __init__(
        self,
        repository: CandidateRepository,
        documents: DocumentRepository,
        extractions: ExtractionRepository,
    ) -> None:
        self._repository = repository
        self._documents = documents
        self._extractions = extractions

    async def create(
        self, actor: ActorContext, *, display_name: str | None = None, email: str | None = None, phone: str | None = None
    ) -> Candidate:
        self._require_writer(actor)
        now = datetime.now(UTC)
        candidate_id = uuid4()
        return await self._repository.create(
            Candidate(
                candidate_id=candidate_id,
                candidate_code=f"CAN-{candidate_id.hex[:12].upper()}",
                display_name=display_name,
                primary_email=email,
                primary_phone=phone,
                organization_id=actor.organization_id,
                created_by_actor_id=actor.actor_id,
                status=CandidateStatus.ACTIVE,
                review_state=CandidateReviewState.DRAFT,
                created_at=now,
                updated_at=now,
            )
        )

    async def cv_versions(self, candidate_id: UUID, actor: ActorContext) -> tuple[dict[str, object], ...]:
        await self._require_candidate(candidate_id, actor)
        versions = await self._repository.list_cv_versions(candidate_id)
        result: list[dict[str, object]] = []
        for version in versions:
            profile = next(
                (item for item in await self._repository.list_profiles(candidate_id) if item.document_id == version.document_id),
                None,
            )
            job = await self._extractions.get_latest_job_for_document(str(version.document_id), DocumentKind.CV)
            result.append({
                "id": version.cv_version_id,
                "version": version.version,
                "document_id": version.document_id,
                "created_at": version.created_at,
                "extraction_status": job.status.value if job else None,
                "profile_version": profile.profile_version if profile else None,
            })
        return tuple(result)

    async def profile_history(self, candidate_id: UUID, actor: ActorContext) -> tuple[dict[str, object], ...]:
        candidate = await self._require_candidate(candidate_id, actor)
        profiles = await self._repository.list_profiles(candidate_id)
        cv_versions = await self._repository.list_cv_versions(candidate_id)
        cv_by_document = {item.document_id: item.version for item in cv_versions}
        return tuple(
            {
                "profile_id": item.profile_id,
                "governance_version": item.governance_version,
                "profile_version": item.profile_version,
                "review_state": item.review_state,
                "document_id": item.document_id,
                "source_cv_version": cv_by_document.get(item.document_id),
                "is_current": candidate.current_profile_id == item.profile_id,
            }
            for item in profiles
        )

    async def create_cv_version(self, candidate_id: UUID, document_id: UUID, actor: ActorContext) -> dict[str, object]:
        candidate = await self._require_candidate(candidate_id, actor)
        self._require_writer(actor)
        document = await self._documents.get(document_id)
        if document is None:
            raise CandidateDomainError("candidate_document_not_found", 404)
        if document.organization_id != candidate.organization_id or document.kind.value != DocumentKind.CV.value:
            raise CandidateDomainError("candidate_document_not_eligible", 409)
        existing = await self._repository.list_cv_versions(candidate_id)
        if any(item.document_id == document_id for item in existing):
            raise CandidateDomainError("candidate_cv_version_exists", 409)
        attached = await self._repository.list_documents(candidate_id)
        if not any(item.document_id == document_id for item in attached):
            try:
                await self._repository.attach_document(
                    CandidateDocument(candidate_document_id=uuid4(), candidate_id=candidate_id, document_id=document_id, kind=document.kind)
                )
            except ValueError as exc:
                raise CandidateDomainError(str(exc), 409) from exc
        cv_id = existing[0].candidate_cv_id if existing else uuid4()
        version = CandidateCVVersion(
            cv_version_id=uuid4(),
            candidate_id=candidate_id,
            candidate_cv_id=cv_id,
            version=(existing[0].version + 1 if existing else 1),
            document_id=document_id,
            created_by_actor_id=actor.actor_id,
        )
        try:
            stored = await self._repository.create_cv_version(version)
        except ValueError as exc:
            raise CandidateDomainError(str(exc), 409) from exc
        existing_job = await self._extractions.get_latest_job_for_document(str(document_id), DocumentKind.CV)
        if existing_job is None:
            await self._extractions.enqueue(
                ExtractionJob(
                    id=str(uuid4()),
                    document_id=str(document_id),
                    document_kind=DocumentKind.CV,
                    owner_actor_id=actor.actor_id,
                    correlation_id=str(uuid4()),
                    status=JobStatus.QUEUED,
                )
            )
        await self._repository.update(
            candidate.model_copy(
                update={
                    "review_state": CandidateReviewState.EXTRACTION_PENDING,
                    "updated_at": datetime.now(UTC),
                }
            )
        )
        return {
            "id": stored.cv_version_id,
            "version": stored.version,
            "document_id": stored.document_id,
            "created_at": stored.created_at,
            "extraction_status": None,
            "profile_version": None,
        }

    async def get(self, candidate_id: UUID, actor: ActorContext) -> Candidate:
        candidate = await self._require_candidate(candidate_id, actor)
        return candidate

    async def list(
        self,
        actor: ActorContext,
        *,
        status: CandidateStatus | None = None,
        limit: int = 50,
        cursor: str | None = None,
        sort: str = "updated_at_desc",
        query: str | None = None,
    ) -> tuple[tuple[Candidate, ...], str | None]:
        self._require_reader(actor)
        candidates = await self._repository.list_candidates(
            actor.organization_id, status=status.value if status else None, sort=sort, query=query
        )
        start = 0
        if cursor:
            try:
                marker = _decode_cursor(cursor)
            except (ValueError, KeyError, TypeError) as exc:
                raise CandidateDomainError("candidate_cursor_invalid", 422) from exc
            for index, candidate in enumerate(candidates):
                if _cursor_for(candidate, sort) == marker:
                    start = index + 1
                    break
            else:
                raise CandidateDomainError("candidate_cursor_invalid", 422)
        page = candidates[start : start + limit]
        next_cursor = _cursor_for(page[-1], sort) if len(page) == limit and start + limit < len(candidates) else None
        return page, next_cursor

    async def attach_document(
        self, candidate_id: UUID, document_id: UUID, is_primary: bool, actor: ActorContext
    ) -> CandidateDocument:
        candidate = await self._require_candidate(candidate_id, actor)
        self._require_writer(actor)
        document = await self._documents.get(document_id)
        if document is None:
            raise CandidateDomainError("candidate_document_not_found", 404)
        if document.organization_id != candidate.organization_id or document.kind.value != "cv":
            raise CandidateDomainError("candidate_document_not_eligible", 409)
        relation = CandidateDocument(
            candidate_document_id=uuid4(),
            candidate_id=candidate_id,
            document_id=document_id,
            kind=document.kind,
            is_primary=is_primary,
        )
        try:
            stored = await self._repository.attach_document(relation)
        except ValueError as exc:
            raise CandidateDomainError(str(exc), 409) from exc
        await self._repository.update(
            candidate.model_copy(
                update={
                    "review_state": CandidateReviewState.EXTRACTION_PENDING,
                    "updated_at": datetime.now(UTC),
                }
            )
        )
        return stored

    async def link_profile(
        self, candidate_id: UUID, profile_id: str, actor: ActorContext
    ) -> CandidateProfileLink:
        candidate = await self._require_candidate(candidate_id, actor)
        self._require_writer(actor)
        profile = await self._extractions.get_profile(profile_id)
        if profile is None:
            raise CandidateDomainError("candidate_profile_not_found", 404)
        if profile.document_kind is not DocumentKind.CV:
            raise CandidateDomainError("candidate_profile_not_cv", 422)
        try:
            document_id = UUID(profile.document_id)
        except ValueError as exc:
            raise CandidateDomainError("candidate_profile_document_invalid", 409) from exc
        documents = await self._repository.list_documents(candidate_id)
        if not any(item.document_id == document_id for item in documents):
            raise CandidateDomainError("candidate_document_required", 409)
        review_state = _candidate_review_state(profile.review_state)
        existing = await self._repository.get_profile_link(candidate_id, profile.id)
        if existing is not None:
            return existing
        relation = CandidateProfileLink(
            candidate_profile_id=uuid4(),
            candidate_id=candidate_id,
            profile_id=profile.id,
            profile_version=profile.version,
            document_id=document_id,
            review_state=review_state,
        )
        try:
            stored = await self._repository.link_profile(relation)
        except ValueError as exc:
            raise CandidateDomainError(str(exc), 409) from exc
        if profile.review_state is ReviewState.ACCEPTED:
            await self._materialize_profile(candidate_id, profile)
            target_state = CandidateReviewState.ACCEPTED
        else:
            target_state = CandidateReviewState.PENDING_REVIEW
        await self._repository.update(
            candidate.model_copy(
                update={
                    "review_state": target_state,
                    "updated_at": datetime.now(UTC),
                }
            )
        )
        if profile.review_state is ReviewState.ACCEPTED:
            await self._repository.set_current_profile(candidate_id, profile.id)
        return stored

    async def associate_extraction_profile(self, profile_id: str) -> tuple[CandidateProfileLink, ...]:
        """Associate a successful CV profile with every candidate owning its document."""
        profile = await self._extractions.get_profile(profile_id)
        if profile is None or profile.document_kind is not DocumentKind.CV:
            return ()
        try:
            document_id = UUID(profile.document_id)
        except ValueError as exc:
            raise CandidateDomainError("candidate_profile_document_invalid", 409) from exc
        links: list[CandidateProfileLink] = []
        for candidate_id in await self._repository.list_candidate_ids_for_document(document_id):
            candidate = await self._repository.get(candidate_id)
            if candidate is None:
                continue
            existing = await self._repository.get_profile_link(candidate_id, profile.id)
            if existing is None:
                existing = await self._repository.link_profile(
                    CandidateProfileLink(
                        candidate_profile_id=uuid4(),
                        candidate_id=candidate_id,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        document_id=document_id,
                        review_state=_candidate_review_state(profile.review_state),
                    )
                )
            await self._repository.update(
                candidate.model_copy(
                    update={
                        "review_state": _candidate_review_state(profile.review_state),
                        "updated_at": datetime.now(UTC),
                    }
                )
            )
            if profile.review_state is ReviewState.ACCEPTED:
                await self._repository.set_current_profile(candidate_id, profile.id)
            links.append(existing)
        return tuple(links)

    async def extraction_status(
        self, candidate_id: UUID, actor: ActorContext
    ) -> CandidateExtractionStatus:
        candidate = await self._require_candidate(candidate_id, actor)
        documents = await self._repository.list_documents(candidate_id)
        profiles = await self._repository.list_profiles(candidate_id)
        profile_by_document = {item.document_id: item for item in profiles}
        statuses = []
        latest_jobs = []
        for item in documents:
            profile = profile_by_document.get(item.document_id)
            job = await self._extractions.get_latest_job_for_document(
                str(item.document_id), ExtractionDocumentKind(item.kind.value)
            )
            if job is not None:
                latest_jobs.append(job)
            statuses.append(
                CandidateExtractionDocumentStatus(
                    candidate_document_id=item.candidate_document_id,
                    kind=item.kind,
                    status=(
                        job.status.value
                        if job is not None
                        else "succeeded" if profile else "pending"
                    ),
                    review_state=profile.review_state if profile else None,
                    profile_version=profile.profile_version if profile else None,
                )
            )

        failed_job = next(
            (job for job in latest_jobs if job.status is JobStatus.FAILED), None
        )
        progress_job = failed_job
        if failed_job is not None:
            status = JobStatus.FAILED.value
            latest_error = _extraction_failure_message(failed_job.error_category)
        elif running_job := next((job for job in latest_jobs if job.status is JobStatus.RUNNING), None):
            status = JobStatus.RUNNING.value
            progress_job = running_job
            latest_error = None
        elif queued_job := next((job for job in latest_jobs if job.status is JobStatus.QUEUED), None):
            status = JobStatus.QUEUED.value
            progress_job = queued_job
            latest_error = None
        elif latest_jobs and all(job.status is JobStatus.SUCCEEDED for job in latest_jobs):
            status = JobStatus.SUCCEEDED.value
            latest_error = None
        else:
            status = candidate.review_state.value
            latest_error = None

        return CandidateExtractionStatus(
            candidate_id=candidate_id,
            status=status,
            documents=statuses,
            stage=progress_job.stage.value if progress_job is not None else None,
            completed_units=progress_job.completed_units if progress_job is not None else None,
            total_units=progress_job.total_units if progress_job is not None else None,
            latest_error=latest_error,
        )

    async def detail_claims(self, candidate_id: UUID, actor: ActorContext) -> tuple[CandidateClaim, ...]:
        await self._require_candidate(candidate_id, actor)
        return await self._repository.list_claims(candidate_id)

    async def current_profile_reference(
        self, candidate_id: UUID, actor: ActorContext
    ) -> CandidateProfileLink | None:
        candidate = await self._require_candidate(candidate_id, actor)
        if candidate.current_profile_id is None:
            return None
        return await self._repository.get_profile_link(candidate_id, candidate.current_profile_id)

    async def extraction_review(
        self, candidate_id: UUID, actor: ActorContext
    ) -> dict[str, object] | None:
        """Return a learner-safe/admin review projection of the linked extraction artifact.

        This is deliberately separate from canonical claims: only accepting the extraction
        profile materializes claims, so pending review never masquerades as a profile.
        """
        candidate = await self._require_candidate(candidate_id, actor)
        profile_id = candidate.current_profile_id
        if profile_id is None:
            links = await self._repository.list_profiles(candidate_id)
            reviewable = [link for link in links if link.review_state is not CandidateReviewState.REJECTED]
            if len(reviewable) != 1:
                return None
            profile_id = reviewable[0].profile_id
        profile = await self._extractions.get_profile(profile_id)
        if not isinstance(profile, ExtractionProfile) or profile.document_kind is not DocumentKind.CV:
            return None
        if isinstance(profile.output, CVFullExtractionOutputV2):
            projection = _safe_v2_review_projection(profile)
        elif isinstance(profile.output, CVExtractionOutput):
            projection = _safe_legacy_review_projection(profile)
        else:
            return None
        link = await self._repository.get_profile_link(candidate_id, profile.id)
        if link is not None:
            projection["governance_version"] = link.governance_version
        return projection

    async def evidence(
        self, candidate_id: UUID, claim_id: UUID, actor: ActorContext
    ) -> tuple[CandidateEvidence, ...]:
        await self._require_candidate(candidate_id, actor)
        if await self._repository.get_claim(candidate_id, claim_id) is None:
            raise CandidateDomainError("candidate_claim_not_found", 404)
        return await self._repository.list_evidence(candidate_id, claim_id)

    async def evidence_document_reference(
        self, candidate_id: UUID, document_id: UUID, actor: ActorContext
    ) -> UUID:
        await self._require_candidate(candidate_id, actor)
        reference = await self._repository.get_candidate_document_reference(candidate_id, document_id)
        if reference is None:
            raise CandidateDomainError("candidate_document_not_found", 404)
        return reference

    async def review(
        self,
        candidate_id: UUID,
        actor: ActorContext,
        action: str,
        expected_profile_version: int | None,
        reason: str | None,
        idempotency_key: str,
    ) -> Candidate:
        candidate = await self._require_candidate(candidate_id, actor)
        self._require_writer(actor)
        link = await self._review_target_link(candidate_id, candidate, expected_profile_version)
        if link is None or link.governance_version is None:
            raise CandidateDomainError("candidate_profile_not_found", 404)
        return await self.review_exact(
            candidate_id,
            link.profile_id,
            link.governance_version,
            actor,
            action,
            reason,
            idempotency_key,
        )

    async def review_exact(
        self,
        candidate_id: UUID,
        profile_id: str,
        expected_governance_version: int | None,
        actor: ActorContext,
        action: str,
        reason: str | None,
        idempotency_key: str,
    ) -> Candidate:
        del reason
        candidate = await self._require_candidate(candidate_id, actor)
        self._require_writer(actor)
        link = await self._repository.get_profile_link(candidate_id, profile_id)
        if link is None:
            raise CandidateDomainError("candidate_profile_not_found", 404)
        if expected_governance_version is None or link.governance_version != expected_governance_version:
            raise CandidateDomainError("candidate_profile_governance_conflict", 409)
        previous = await self._repository.get_review_action(candidate_id, idempotency_key)
        if previous is not None:
            if previous.action != action or previous.version != link.profile_version:
                raise CandidateDomainError("candidate_review_idempotency_conflict", 409)
            return candidate.model_copy(update={"current_profile_version": previous.version})
        profile = await self._extractions.get_profile(profile_id)
        if profile is None:
            raise CandidateDomainError("candidate_profile_not_found", 404)
        if action in {"request_revision", "reject"} and profile.review_state is ReviewState.ACCEPTED:
            raise CandidateDomainError("candidate_profile_not_editable", 409)
        if action == "accept":
            if profile.review_state is not ReviewState.ACCEPTED:
                profile = await self._extractions.accept_profile(
                    profile.id, actor.actor_id, profile.version
                )
                await self._materialize_profile(candidate_id, profile)
            elif link.review_state is not CandidateReviewState.ACCEPTED:
                await self._materialize_profile(candidate_id, profile)
            target = CandidateReviewState.ACCEPTED
            link_state = CandidateReviewState.ACCEPTED
        elif action == "request_revision":
            if profile.review_state in {ReviewState.PENDING_REVIEW, ReviewState.CORRECTED}:
                profile = await self._extractions.request_revision(
                    profile.id, actor.actor_id, profile.version
                )
            target = CandidateReviewState.NEEDS_REVISION
            link_state = CandidateReviewState.NEEDS_REVISION
        else:
            if profile.review_state in {ReviewState.PENDING_REVIEW, ReviewState.CORRECTED}:
                profile = await self._extractions.reject_profile(
                    profile.id, actor.actor_id, profile.version
                )
            target = CandidateReviewState.REJECTED
            link_state = CandidateReviewState.REJECTED
        await self._repository.update_profile_link(
            link.model_copy(update={"profile_version": profile.version, "review_state": link_state})
        )
        updated = await self._repository.update(
            candidate.model_copy(
                update={
                    "review_state": target,
                    "updated_at": datetime.now(UTC),
                }
            )
        )
        if action == "accept":
            updated = await self._repository.promote_current_profile(
                candidate_id, profile.id, expected_governance_version
            )
        try:
            await self._repository.save_review_action(
                CandidateReviewActionRecord(
                    candidate_id=candidate_id,
                    idempotency_key=idempotency_key,
                    action=action,
                    version=profile.version,
                )
            )
        except ValueError as exc:
            if str(exc) != "candidate_review_idempotency_exists":
                raise
        return updated

    async def _review_target_link(
        self,
        candidate_id: UUID,
        candidate: Candidate,
        expected_profile_version: int | None,
    ) -> CandidateProfileLink | None:
        links = await self._repository.list_profiles(candidate_id)
        if expected_profile_version is not None:
            matching = [
                link for link in links if link.profile_version == expected_profile_version
            ]
            if len(matching) > 1:
                raise CandidateDomainError("candidate_profile_version_conflict", 409)
            if matching:
                return matching[0]
        if candidate.current_profile_id is not None:
            return await self._repository.get_profile_link(candidate_id, candidate.current_profile_id)
        if len(links) == 1:
            return links[0]
        raise CandidateDomainError("candidate_profile_required", 409)

    async def _materialize_profile(self, candidate_id: UUID, profile: object) -> None:
        from app.extraction.schemas import ExtractionProfile

        if not isinstance(profile, ExtractionProfile):
            raise CandidateDomainError("candidate_profile_not_cv", 422)
        document_id = UUID(profile.document_id)
        claims: list[CandidateClaim] = []
        evidence: list[CandidateEvidence] = []
        claim_inputs: Any
        if isinstance(profile.output, CVExtractionOutput):
            claim_inputs = (
                (bucket, values)
                for bucket in ("skills", "experience", "education")
                for values in (getattr(profile.output, bucket),)
            )
        elif isinstance(profile.output, CVFullExtractionOutputV2) and profile.candidate_profile is not None:
            claim_inputs = self._candidate_projection_claims(profile.candidate_profile)
        else:
            raise CandidateDomainError("candidate_profile_not_cv", 422)
        next_index: dict[str, int] = {}
        for bucket, values in claim_inputs:
            for item in values:
                index = next_index.get(bucket, 0)
                next_index[bucket] = index + 1
                if item.evidence_status.value != "supported" or item.value is None or item.source_locator is None or not item.source_excerpt:
                    continue
                claim_id = uuid4()
                evidence_id = uuid4()
                context = _context_for(bucket, item.evidence_type.value)
                claims.append(
                    CandidateClaim(
                        claim_id=claim_id,
                        candidate_id=candidate_id,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        bucket=bucket,
                        claim_index=index,
                        value=item.value,
                        evidence_type=item.evidence_type.value,
                        evidence_status=item.evidence_status.value,
                        context=context,
                        confidence=item.confidence,
                    )
                )
                evidence.append(
                    CandidateEvidence(
                        evidence_id=evidence_id,
                        claim_id=claim_id,
                        candidate_id=candidate_id,
                        document_id=document_id,
                        source_locator=item.source_locator.model_dump(mode="json"),
                        excerpt=item.source_excerpt,
                        evidence_type=item.evidence_type.value,
                        context=context,
                        confidence=item.confidence,
                        provenance={
                            "profile_id": profile.id,
                            "profile_version": profile.version,
                            "source": "accepted_cv_extraction",
                        },
                    )
                )
        if claims:
            try:
                await self._repository.create_claims(candidate_id, claims, evidence)
            except ValueError as exc:
                if str(exc) != "candidate_claim_exists":
                    raise CandidateDomainError(str(exc), 409) from exc

    @staticmethod
    def _candidate_projection_claims(
        profile: ExtractionCandidateProfile,
    ) -> builtins.list[tuple[str, builtins.list[ExtractedClaim]]]:
        def convert(value: str, items: builtins.list[object], evidence_type: EvidenceType) -> builtins.list[ExtractedClaim]:
            result: list[ExtractedClaim] = []
            for entity in items:
                for item in getattr(entity, "evidence", []):
                    if item.source_locator is None:
                        continue
                    result.append(
                        ExtractedClaim(
                            value=value,
                            evidence_type=evidence_type,
                            confidence=item.confidence,
                            evidence_status=EvidenceStatus.SUPPORTED,
                            source_locator=item.source_locator,
                            source_excerpt=item.source_excerpt,
                        )
                    )
            return result

        return [
            ("skills", convert(item.entity, [item], EvidenceType.EXPLICIT_SKILL))
            for item in profile.skills
        ] + [
            ("experience", convert(item.name, [item], EvidenceType.WORK_EXPERIENCE))
            for item in profile.employment_history
        ] + [
            ("experience", convert(item.name, [item], EvidenceType.PROJECT_USAGE))
            for item in profile.projects
        ] + [
            ("education", convert(item.degree or item.institution, [item], EvidenceType.EDUCATION))
            for item in profile.education
            if item.degree or item.institution
        ]

    async def _require_candidate(self, candidate_id: UUID, actor: ActorContext) -> Candidate:
        self._require_reader(actor)
        candidate = await self._repository.get(candidate_id)
        if candidate is None:
            raise CandidateDomainError("candidate_not_found", 404)
        if candidate.organization_id != actor.organization_id:
            raise CandidateDomainError("candidate_access_denied", 403)
        return candidate

    @staticmethod
    def _require_reader(actor: ActorContext) -> None:
        if not actor.roles.intersection({Role.ADMIN, Role.REVIEWER, Role.SME}):
            raise CandidateDomainError("candidate_reader_role_required", 403)

    @staticmethod
    def _require_writer(actor: ActorContext) -> None:
        if not actor.roles.intersection({Role.ADMIN, Role.REVIEWER}):
            raise CandidateDomainError("candidate_reviewer_role_required", 403)

def _safe_source(locator: object) -> dict[str, object] | None:
    if not hasattr(locator, "model_dump"):
        return None
    return cast(dict[str, object], locator.model_dump(mode="json"))


def _safe_v2_evidence(items: Iterable[object]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for item in items:
        locator = _safe_source(getattr(item, "source_locator", None))
        excerpt = getattr(item, "source_excerpt", None)
        if not locator or not isinstance(excerpt, str) or not excerpt:
            continue
        result.append(
            {
                "source_excerpt": excerpt,
                "source_locator": locator,
                "evidence_strength": getattr(getattr(item, "evidence_strength", None), "value", None),
                "confidence": getattr(item, "confidence", 0.0),
            }
        )
    return result


def _review_item_id(profile: ExtractionProfile, kind: str, index: int, item: object) -> str:
    payload = json.dumps(
        cast(Any, item).model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()[:12]
    return f"{profile.id}:v{profile.version}:{kind}:{index}:{digest}"


def _safe_v2_review_projection(profile: ExtractionProfile) -> dict[str, object]:
    output = cast(CVFullExtractionOutputV2, profile.output)
    experience = [
        {
            "review_item_id": _review_item_id(profile, "experience", index, item),
            "kind": "experience",
            "title": item.title,
            "company": item.company,
            "start_date": item.start_date,
            "end_date": item.end_date,
            "responsibilities": list(item.responsibilities),
            "achievements": list(item.achievements),
            "evidence": _safe_v2_evidence(item.evidence),
        }
        for index, item in enumerate(output.experience)
    ]
    capabilities = [
        {
            "review_item_id": _review_item_id(profile, "capability", index, item),
            "kind": "capability",
            "raw_name": item.raw_name,
            "canonical_name": item.canonical_name,
            "category": item.category,
            "mapping_status": item.mapping_status.value,
            "supporting_experience_refs": list(item.supporting_experience_refs),
            "evidence": _safe_v2_evidence(item.evidence),
        }
        for index, item in enumerate(output.capabilities)
        if item.mapping_status.value != "rejected_unsupported"
    ]
    tools = [
        {
            "review_item_id": _review_item_id(profile, "tool", index, item),
            "kind": "tool",
            "name": item.name,
            "evidence": _safe_v2_evidence(item.evidence),
        }
        for index, item in enumerate(output.tools_platforms)
    ]
    education = [
        {
            "review_item_id": _review_item_id(profile, "education", index, item),
            "kind": "education",
            "degree": item.degree,
            "field": item.field,
            "institution": item.institution,
            "location": item.location,
            "year": item.year,
            "evidence": _safe_v2_evidence(item.evidence),
        }
        for index, item in enumerate(output.education)
    ]
    allowed_audit_keys = {
        "pipeline_mode",
        "capability_mode",
        "taxonomy_id",
        "taxonomy_version",
        "schema_version",
    }
    audit = {
        key: value
        for key, value in profile.audit.items()
        if key in allowed_audit_keys and isinstance(value, (str, int, float, bool))
    }
    return {
        "profile_id": profile.id,
        "version": profile.version,
        "review_state": profile.review_state.value,
        "candidate_summary": output.candidate_summary,
        "experience": experience,
        "capabilities": capabilities,
        "tools_platforms": tools,
        "education": education,
        "safe_metadata": audit,
    }


def _safe_legacy_review_projection(profile: ExtractionProfile) -> dict[str, object]:
    output = cast(CVExtractionOutput, profile.output)

    def claims(items: list[ExtractedClaim], kind: str) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for item in items:
            locator = _safe_source(item.source_locator)
            if item.value is None or not locator or not item.source_excerpt:
                continue
            result.append(
                {
                    "review_item_id": _review_item_id(profile, kind, len(result), item),
                    "kind": kind,
                    "value": item.value,
                    "evidence_type": item.evidence_type.value,
                    "confidence": item.confidence,
                    "source_excerpt": item.source_excerpt,
                    "source_locator": locator,
                }
            )
        return result

    return {
        "profile_id": profile.id,
        "version": profile.version,
        "review_state": profile.review_state.value,
        "candidate_summary": None,
        "experience": claims(output.experience, "experience"),
        "capabilities": claims(output.skills, "capability"),
        "tools_platforms": [],
        "education": claims(output.education, "education"),
        "safe_metadata": {},
    }


def _candidate_review_state(state: ReviewState) -> CandidateReviewState:
    if state is ReviewState.ACCEPTED:
        return CandidateReviewState.ACCEPTED
    if state in {ReviewState.PENDING_REVIEW, ReviewState.CORRECTED}:
        return CandidateReviewState.PENDING_REVIEW
    if state is ReviewState.NEEDS_REVISION:
        return CandidateReviewState.NEEDS_REVISION
    return CandidateReviewState.REJECTED


def _extraction_failure_message(error_category: str | None) -> str:
    if error_category and "model_rate_limited" in error_category:
        return "The AI provider is rate limited. Wait a moment before retrying."
    if error_category == "grounding_validation_failed":
        return "The extracted evidence could not be validated against the source document."
    if error_category == "worker_unresponsive":
        return "The extraction worker stopped responding. Please retry the document."
    return "The document extraction failed. Please try again."


def _cursor_for(candidate: Candidate, sort: str) -> str:
    value = candidate.created_at if sort.startswith("created_at") else candidate.updated_at
    payload = {"value": value.isoformat(), "id": str(candidate.candidate_id)}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> str:
    padding = "=" * (-len(cursor) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(cursor + padding))
    if not isinstance(decoded, dict) or not isinstance(decoded.get("value"), str) or not isinstance(decoded.get("id"), str):
        raise ValueError("invalid cursor")
    UUID(decoded["id"])
    return cursor


def _context_for(bucket: str, evidence_type: str) -> str:
    if bucket == "experience":
        return EvidenceContext.USED_IN_EMPLOYMENT.value
    if bucket == "education":
        return EvidenceContext.STUDIED.value
    if evidence_type == "project_usage":
        return EvidenceContext.USED_IN_PROJECT.value
    if evidence_type == "certification":
        return EvidenceContext.CREDENTIALED.value
    return EvidenceContext.MENTIONED.value
