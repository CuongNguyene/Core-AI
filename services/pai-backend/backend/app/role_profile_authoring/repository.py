from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.capability_analysis.domain_packs.contracts import DomainPackReference
from app.documents.repository import DocumentRepository
from app.extraction.repository import ExtractionRepository
from app.extraction.schemas import (
    DocumentKind,
    ExtractionProfile,
    ReviewState,
)
from app.matching.repository import RoleProfileRepository
from app.matching.schemas import (
    RoleCompetencyProfile,
    RoleProfileSemanticPolicy,
    RoleProfileStatus,
    RoleRequirement,
)
from app.role_profile_authoring.errors import (
    RoleProfileDraftSourceError,
    RoleProfileDraftStateError,
    RoleProfileDraftVersionConflictError,
)
from app.role_profile_authoring.lineage import validate_role_jd_lineage
from app.role_profile_authoring.models import (
    RoleProfileDraftAuditRecord,
    RoleProfileDraftRecord,
    RoleProfileDraftVersionRecord,
)
from app.role_profile_authoring.quality_gate import evaluate_role_profile_draft
from app.role_profile_authoring.schemas import (
    ApprovalEligibility,
    QualityGateResult,
    RequirementFinding,
    RoleProfileDraft,
    RoleProfileDraftStatus,
)
from app.role_profile_authoring.source_adapter import adapt_jd_profile, detect_duplicate_candidates
from app.role_registry.repository import RoleRegistryRepository
from app.role_registry.schemas import Role, RoleJDVersion
from app.semantic_policy.schemas import SemanticPolicyRef
from app.semantic_policy.service import SemanticPolicyResolver


class RoleProfileDraftRepository(Protocol):
    async def create_from_jd(
        self,
        source_jd_profile_id: str,
        actor_id: UUID,
        organization_id: UUID,
        correlation_id: str,
        role_id: UUID | None = None,
        role_jd_version_id: UUID | None = None,
    ) -> RoleProfileDraft: ...

    async def get(self, draft_id: str) -> RoleProfileDraft | None: ...

    async def list_for_organization(self, organization_id: UUID) -> list[RoleProfileDraft]: ...

    async def author(
        self,
        draft_id: str,
        *,
        expected_version: int,
        actor_id: UUID,
        title: str | None,
        requirements: list[RoleRequirement],
    ) -> RoleProfileDraft: ...

    async def validate(
        self, draft_id: str, *, expected_version: int, actor_id: UUID
    ) -> RoleProfileDraft: ...

    async def approve(
        self,
        draft_id: str,
        *,
        expected_version: int,
        actor_id: UUID,
        requested_status: RoleProfileStatus,
        semantic_policy: RoleProfileSemanticPolicy,
        semantic_policy_ref: SemanticPolicyRef | None = None,
    ) -> RoleProfileDraft: ...


class SqlAlchemyRoleProfileDraftRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        extraction: ExtractionRepository,
        role_profiles: RoleProfileRepository,
        semantic_policy_resolver: SemanticPolicyResolver | None = None,
        role_registry: RoleRegistryRepository | None = None,
        documents: DocumentRepository | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._extraction = extraction
        self._role_profiles = role_profiles
        self._semantic_policy_resolver = semantic_policy_resolver
        self._role_registry = role_registry
        self._documents = documents

    async def create_from_jd(
        self,
        source_jd_profile_id: str,
        actor_id: UUID,
        organization_id: UUID,
        correlation_id: str,
        role_id: UUID | None = None,
        role_jd_version_id: UUID | None = None,
    ) -> RoleProfileDraft:
        source = await self._accepted_source(source_jd_profile_id)
        role, jd_version = await self._resolve_lineage(
            source,
            organization_id=organization_id,
            role_id=role_id,
            role_jd_version_id=role_jd_version_id,
        )
        adapted = adapt_jd_profile(source)
        requirements = adapted.requirements
        gate, findings, eligibility = _evaluate_draft(
            requirements,
            source_jd_profile_id=source.id,
            source_jd_profile_version=source.version,
            source_schema=adapted.source_schema,
            source_version=adapted.source_version,
        )
        draft_id = f"role-draft-{uuid4().hex}"
        draft = RoleProfileDraft(
            id=draft_id,
            source_jd_profile_id=source.id,
            source_jd_profile_version=source.version,
            owner_actor_id=actor_id,
            organization_id=organization_id,
            version=1,
            status=RoleProfileDraftStatus.DRAFT,
            title=None,
            requirements=requirements,
            quality_gate=gate,
            approval_eligibility=eligibility,
            source_schema=adapted.source_schema,
            source_version=adapted.source_version,
            authoring_findings=findings,
            duplicate_candidate_groups=adapted.duplicate_candidate_groups,
            role_id=role.id if role is not None else None,
            role_jd_version_id=jd_version.id if jd_version is not None else None,
            correlation_id=correlation_id,
        )
        async with self._session_factory() as session, session.begin():
            session.add(self._draft_record(draft))
            await session.flush()
            self._add_snapshot(session, draft, actor_id)
            self._audit(session, draft, actor_id, "ROLE_PROFILE_DRAFT_CREATED")
        return draft

    async def get(self, draft_id: str) -> RoleProfileDraft | None:
        async with self._session_factory() as session:
            record = await session.get(RoleProfileDraftRecord, draft_id)
            return _to_schema(record) if record is not None else None

    async def list_for_organization(self, organization_id: UUID) -> list[RoleProfileDraft]:
        async with self._session_factory() as session:
            records = list((await session.scalars(
                select(RoleProfileDraftRecord)
                .where(RoleProfileDraftRecord.organization_id == organization_id)
                .order_by(RoleProfileDraftRecord.updated_at.desc())
            )).all())
            return [_to_schema(record) for record in records]

    async def author(
        self,
        draft_id: str,
        *,
        expected_version: int,
        actor_id: UUID,
        title: str | None,
        requirements: list[RoleRequirement],
    ) -> RoleProfileDraft:
        async with self._session_factory() as session, session.begin():
            record = await session.get(RoleProfileDraftRecord, draft_id, with_for_update=True)
            draft = self._require_current(record, expected_version)
            assert record is not None
            if draft.status is RoleProfileDraftStatus.APPROVED:
                raise RoleProfileDraftStateError("approved draft is immutable")
            gate, findings, eligibility = _evaluate_draft(
                requirements,
                source_jd_profile_id=draft.source_jd_profile_id,
                source_jd_profile_version=draft.source_jd_profile_version,
                source_schema=draft.source_schema,
                source_version=draft.source_version,
            )
            updated = draft.model_copy(
                update={
                    "version": draft.version + 1,
                    "status": RoleProfileDraftStatus.DRAFT,
                    "title": title,
                    "requirements": requirements,
                    "quality_gate": gate,
                    "approval_eligibility": eligibility,
                    "authoring_findings": findings,
                    "duplicate_candidate_groups": detect_duplicate_candidates(requirements),
                },
                deep=True,
            )
            self._update_record(record, updated)
            self._add_snapshot(session, updated, actor_id)
            self._audit(session, updated, actor_id, "ROLE_PROFILE_DRAFT_AUTHORED")
        return updated

    async def validate(
        self, draft_id: str, *, expected_version: int, actor_id: UUID
    ) -> RoleProfileDraft:
        async with self._session_factory() as session, session.begin():
            record = await session.get(RoleProfileDraftRecord, draft_id, with_for_update=True)
            draft = self._require_current(record, expected_version)
            assert record is not None
            if draft.status is RoleProfileDraftStatus.APPROVED:
                raise RoleProfileDraftStateError("approved draft is immutable")
            gate, findings, eligibility = _evaluate_draft(
                draft.requirements,
                source_jd_profile_id=draft.source_jd_profile_id,
                source_jd_profile_version=draft.source_jd_profile_version,
                source_schema=draft.source_schema,
                source_version=draft.source_version,
            )
            updated = draft.model_copy(
                update={
                    "status": (
                        RoleProfileDraftStatus.NEEDS_REVISION
                        if gate.has_blocking
                        else RoleProfileDraftStatus.IN_REVIEW
                    ),
                    "quality_gate": gate,
                    "approval_eligibility": eligibility,
                    "authoring_findings": findings,
                },
                deep=True,
            )
            self._update_record(record, updated)
            self._audit(session, updated, actor_id, "ROLE_PROFILE_DRAFT_VALIDATED")
        return updated

    async def approve(
        self,
        draft_id: str,
        *,
        expected_version: int,
        actor_id: UUID,
        requested_status: RoleProfileStatus,
        semantic_policy: RoleProfileSemanticPolicy,
        semantic_policy_ref: SemanticPolicyRef | None = None,
    ) -> RoleProfileDraft:
        async with self._session_factory() as session:
            record = await session.get(RoleProfileDraftRecord, draft_id)
            draft = self._require_current(record, expected_version)
        if draft.status not in {
            RoleProfileDraftStatus.VALIDATED,
            RoleProfileDraftStatus.IN_REVIEW,
        }:
            raise RoleProfileDraftStateError("draft must be validated before approval")
        if not draft.approval_eligibility.can_approve_provisional:
            raise RoleProfileDraftStateError("blocking quality gate finding prevents approval")
        if requested_status is RoleProfileStatus.ACTIVE and not draft.approval_eligibility.can_approve_active:
            raise RoleProfileDraftStateError("active approval requires a passing quality gate")
        if requested_status not in {RoleProfileStatus.ACTIVE, RoleProfileStatus.PROVISIONAL}:
            raise RoleProfileDraftStateError("approval status must be active or provisional")
        if draft.role_id is not None or draft.role_jd_version_id is not None:
            source = await self._accepted_source(draft.source_jd_profile_id)
            try:
                await self._resolve_lineage(
                    source,
                    organization_id=draft.organization_id,
                    role_id=draft.role_id,
                    role_jd_version_id=draft.role_jd_version_id,
                )
            except RoleProfileDraftSourceError as error:
                raise RoleProfileDraftStateError(
                    "role lineage is inconsistent and cannot be approved"
                ) from error
        if semantic_policy_ref is not None:
            if self._semantic_policy_resolver is None:
                raise RoleProfileDraftStateError("semantic policy resolver is unavailable")
            try:
                resolved_policy = await self._semantic_policy_resolver.resolve(
                    semantic_policy_ref,
                    target_id=draft.id,
                    target_type="role_profile",
                )
                if (
                    semantic_policy.core_version != resolved_policy.core_version
                    or semantic_policy.pack_refs
                    != (
                        DomainPackReference(
                            pack_id=resolved_policy.domain_pack_id,
                            version=resolved_policy.domain_pack_version,
                        ),
                    )
                ):
                    raise RoleProfileDraftStateError(
                        "semantic policy binding does not match the selected policy version"
                    )
            except Exception as error:
                if isinstance(error, RoleProfileDraftStateError):
                    raise
                raise RoleProfileDraftStateError("semantic policy binding is not valid") from error
        profile = RoleCompetencyProfile(
            id=f"role-profile-{uuid4().hex}",
            version=str(draft.version),
            status=requested_status,
            source_jd_profile_id=draft.source_jd_profile_id,
            source_jd_profile_version=draft.source_jd_profile_version,
            rule_set_version="role-profile-authoring-v1",
            policy_version="role-profile-policy-v1",
            requirements=draft.requirements,
            semantic_policy_ref=semantic_policy_ref,
            semantic_policy=semantic_policy,
            role_id=draft.role_id,
            role_jd_version_id=draft.role_jd_version_id,
        )
        save = getattr(self._role_profiles, "save", None)
        if save is None:
            raise RoleProfileDraftStateError("role profile persistence is unavailable")
        profile = await save(profile)
        async with self._session_factory() as session, session.begin():
            record = await session.get(RoleProfileDraftRecord, draft.id, with_for_update=True)
            current = self._require_current(record, expected_version)
            assert record is not None
            updated = current.model_copy(
                update={
                    "status": RoleProfileDraftStatus.APPROVED,
                    "approved_role_profile_id": profile.id,
                    "approved_role_profile_version": profile.version,
                },
                deep=True,
            )
            self._update_record(record, updated)
            self._audit(
                session,
                updated,
                actor_id,
                "ROLE_PROFILE_DRAFT_APPROVED",
                {
                    "approved_status": requested_status.value,
                    "quality_gate_passed": profile.status is RoleProfileStatus.ACTIVE
                    or current.quality_gate.passed,
                },
            )
        return updated

    async def _accepted_source(self, profile_id: str) -> ExtractionProfile:
        source = await self._extraction.get_profile(profile_id)
        if (
            source is None
            or source.document_kind is not DocumentKind.JD
            or source.review_state is not ReviewState.ACCEPTED
            or await self._extraction.is_superseded(profile_id)
        ):
            raise RoleProfileDraftSourceError("JD profile must be accepted and current")
        return source

    async def _resolve_lineage(
        self,
        source: ExtractionProfile,
        *,
        organization_id: UUID,
        role_id: UUID | None,
        role_jd_version_id: UUID | None,
    ) -> tuple[Role | None, RoleJDVersion | None]:
        if role_id is None and role_jd_version_id is None:
            return None, None
        if role_id is None or role_jd_version_id is None:
            raise RoleProfileDraftSourceError(
                "role_id and role_jd_version_id must be supplied together"
            )
        if self._role_registry is None or self._documents is None:
            raise RoleProfileDraftSourceError("role lineage registry is unavailable")
        role = await self._role_registry.get_role(role_id, organization_id)
        jd_version = await self._role_registry.get_jd_version(role_jd_version_id)
        if role is None or jd_version is None:
            raise RoleProfileDraftSourceError("role lineage was not found in this organization")
        try:
            document_id = UUID(source.document_id)
        except ValueError as error:
            raise RoleProfileDraftSourceError("source document identity is invalid") from error
        document = await self._documents.get(document_id)
        if document is None:
            raise RoleProfileDraftSourceError("source document was not found")
        try:
            validate_role_jd_lineage(
                role=role,
                jd_version=jd_version,
                source_profile=source,
                document=document,
                organization_id=organization_id,
            )
        except ValueError as error:
            raise RoleProfileDraftSourceError(str(error)) from error
        return role, jd_version

    @staticmethod
    def _require_current(
        record: RoleProfileDraftRecord | None, expected_version: int
    ) -> RoleProfileDraft:
        if record is None:
            raise RoleProfileDraftStateError("role profile draft was not found")
        draft = _to_schema(record)
        if draft.version != expected_version:
            raise RoleProfileDraftVersionConflictError("role profile draft version conflict")
        return draft

    @staticmethod
    def _draft_record(draft: RoleProfileDraft) -> RoleProfileDraftRecord:
        return RoleProfileDraftRecord(
            id=draft.id,
            source_jd_profile_id=draft.source_jd_profile_id,
            source_jd_profile_version=draft.source_jd_profile_version,
            owner_actor_id=draft.owner_actor_id,
            organization_id=draft.organization_id,
            version=draft.version,
            status=draft.status.value,
            title=draft.title,
            requirements=[item.model_dump(mode="json") for item in draft.requirements],
            quality_gate=draft.quality_gate.model_dump(mode="json"),
            approval_eligibility=draft.approval_eligibility.model_dump(mode="json"),
            source_schema=draft.source_schema,
            source_version=draft.source_version,
            authoring_findings=[item.model_dump(mode="json") for item in draft.authoring_findings],
            duplicate_candidate_groups=[
                item.model_dump(mode="json") for item in draft.duplicate_candidate_groups
            ],
            approved_role_profile_id=draft.approved_role_profile_id,
            role_id=draft.role_id,
            role_jd_version_id=draft.role_jd_version_id,
            correlation_id=draft.correlation_id,
        )

    @staticmethod
    def _update_record(record: RoleProfileDraftRecord, draft: RoleProfileDraft) -> None:
        values = SqlAlchemyRoleProfileDraftRepository._draft_record(draft)
        record.version = values.version
        record.status = values.status
        record.title = values.title
        record.requirements = values.requirements
        record.quality_gate = values.quality_gate
        record.approval_eligibility = values.approval_eligibility
        record.source_schema = values.source_schema
        record.source_version = values.source_version
        record.authoring_findings = values.authoring_findings
        record.duplicate_candidate_groups = values.duplicate_candidate_groups
        record.approved_role_profile_id = values.approved_role_profile_id
        record.role_id = values.role_id
        record.role_jd_version_id = values.role_jd_version_id

    @staticmethod
    def _add_snapshot(session: AsyncSession, draft: RoleProfileDraft, actor_id: UUID) -> None:
        session.add(
            RoleProfileDraftVersionRecord(
                record_id=f"{draft.id}:{draft.version}",
                draft_id=draft.id,
                version=draft.version,
                actor_id=actor_id,
                status=draft.status.value,
                title=draft.title,
                requirements=[item.model_dump(mode="json") for item in draft.requirements],
                quality_gate=draft.quality_gate.model_dump(mode="json"),
                approval_eligibility=draft.approval_eligibility.model_dump(mode="json"),
                source_schema=draft.source_schema,
                source_version=draft.source_version,
                authoring_findings=[item.model_dump(mode="json") for item in draft.authoring_findings],
                duplicate_candidate_groups=[
                    item.model_dump(mode="json") for item in draft.duplicate_candidate_groups
                ],
            )
        )

    @staticmethod
    def _audit(
        session: AsyncSession,
        draft: RoleProfileDraft,
        actor_id: UUID,
        action: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        session.add(
            RoleProfileDraftAuditRecord(
                id=str(uuid4()),
                draft_id=draft.id,
                actor_id=actor_id,
                action=action,
                audit_metadata={
                    "draft_id": draft.id,
                    "draft_version": draft.version,
                    "source_jd_profile_id": draft.source_jd_profile_id,
                    "source_jd_profile_version": draft.source_jd_profile_version,
                    **(metadata or {}),
                },
            )
        )


def _to_schema(record: RoleProfileDraftRecord) -> RoleProfileDraft:
    return RoleProfileDraft.model_validate(
        {
            "id": record.id,
            "source_jd_profile_id": record.source_jd_profile_id,
            "source_jd_profile_version": record.source_jd_profile_version,
            "owner_actor_id": record.owner_actor_id,
            "organization_id": record.organization_id,
            "version": record.version,
            "status": record.status,
            "title": record.title,
            "requirements": record.requirements,
            "quality_gate": record.quality_gate,
            "approval_eligibility": record.approval_eligibility
            or {"can_create_draft": True, "can_approve_provisional": False, "can_approve_active": False},
            "source_schema": record.source_schema,
            "source_version": record.source_version,
            "authoring_findings": record.authoring_findings,
            "duplicate_candidate_groups": record.duplicate_candidate_groups,
            "approved_role_profile_id": record.approved_role_profile_id,
            "approved_role_profile_version": (
                str(record.version) if record.approved_role_profile_id else None
            ),
            "role_id": record.role_id,
            "role_jd_version_id": record.role_jd_version_id,
            "correlation_id": record.correlation_id,
        },
        strict=False,
    )


def _evaluate_draft(
    requirements: list[RoleRequirement],
    *,
    source_jd_profile_id: str | None,
    source_jd_profile_version: int | None,
    source_schema: str | None,
    source_version: str | None,
) -> tuple[QualityGateResult, list[RequirementFinding], ApprovalEligibility]:
    gate, findings, eligibility = evaluate_role_profile_draft(
        requirements,
        source_jd_profile_id=source_jd_profile_id,
        source_jd_profile_version=source_jd_profile_version,
        source_schema=source_schema,
        source_version=source_version,
    )
    return gate, findings, eligibility
