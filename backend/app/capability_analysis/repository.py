import re
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.capability_analysis.errors import AuditPersistenceError
from app.capability_analysis.models import (
    CapabilityGapAuditEventRecord,
    CapabilityGapPortfolioRecord,
    GapOverlapLinkRecord,
    RequirementAssessmentRecord,
    TargetGapRecord,
)
from app.capability_analysis.schemas import (
    AnalysisStatus,
    CapabilityGapProfile,
    CombinedGapPortfolio,
    GapOverlapLink,
    HumanAssistedEvidenceSelection,
    PreviewReadiness,
    RequirementAssessment,
    TargetGap,
    TargetGapAnalysis,
    TargetSemanticPolicySnapshot,
    TargetType,
    TargetUsageMode,
    VerificationQueueItem,
)

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REJECTION_AUDIT_FIELDS = {
    "cv_profile_id",
    "current_target_profile_id",
    "future_target_profile_id",
    "correlation_id",
}


class CapabilityGapPortfolioRepository(Protocol):
    async def create_profile(self, profile: CapabilityGapProfile) -> CapabilityGapProfile: ...

    async def get_profile(self, portfolio_id: str) -> CapabilityGapProfile | None: ...

    async def get_profile_for_candidate(
        self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID
    ) -> CapabilityGapProfile | None: ...

    async def create(self, portfolio: CombinedGapPortfolio) -> CombinedGapPortfolio: ...

    async def get(self, portfolio_id: str) -> CombinedGapPortfolio | None: ...

    async def get_for_candidate(
        self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID
    ) -> CombinedGapPortfolio | None: ...

    async def list_for_candidate(
        self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID
    ) -> tuple[CombinedGapPortfolio, ...]: ...

    async def list_for_target_references(
        self,
        target_references: tuple[tuple[str, str], ...],
        *,
        actor_id: UUID,
        organization_id: UUID,
    ) -> tuple[CombinedGapPortfolio, ...]: ...

    async def record_rejected_input(
        self, *, portfolio_id: str | None, action: str, metadata: dict[str, object]
    ) -> None: ...

    async def record_human_assisted_reanalysis(
        self,
        *,
        portfolio_id: str,
        source_analysis_id: str,
        evidence_selections: list[HumanAssistedEvidenceSelection],
        reviewer_actor_id: UUID,
    ) -> None: ...


class InMemoryCapabilityGapPortfolioRepository:
    def __init__(self) -> None:
        self._profiles: dict[str, CapabilityGapProfile] = {}
        self.audit_events: list[dict[str, object]] = []

    async def create(self, portfolio: CombinedGapPortfolio) -> CombinedGapPortfolio:
        profile = await self.create_profile(CapabilityGapProfile.from_combined_gap_portfolio(portfolio))
        return profile.to_combined_gap_portfolio()

    async def create_profile(self, profile: CapabilityGapProfile) -> CapabilityGapProfile:
        if profile.id in self._profiles:
            raise ValueError("Capability gap portfolio is immutable")
        self._validate(profile)
        self._profiles[profile.id] = profile.model_copy(deep=True)
        self.audit_events.append(
            {"action": "CAPABILITY_GAP_PORTFOLIO_CREATED", **self._safe_audit_metadata(profile)}
        )
        return profile.model_copy(deep=True)

    async def get(self, portfolio_id: str) -> CombinedGapPortfolio | None:
        profile = await self.get_profile(portfolio_id)
        return profile.to_combined_gap_portfolio() if profile else None

    async def get_profile(self, portfolio_id: str) -> CapabilityGapProfile | None:
        profile = self._profiles.get(portfolio_id)
        return profile.model_copy(deep=True) if profile else None

    async def get_for_candidate(
        self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID
    ) -> CombinedGapPortfolio | None:
        candidates = [
            item for item in self._profiles.values()
            if item.candidate_id == candidate_id
            and item.owner_actor_id == actor_id
            and item.organization_id == organization_id
        ]
        profile = max(candidates, key=lambda item: item.analysis_version).model_copy(deep=True) if candidates else None
        return profile.to_combined_gap_portfolio() if profile else None

    async def get_profile_for_candidate(
        self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID
    ) -> CapabilityGapProfile | None:
        candidates = [
            item for item in self._profiles.values()
            if item.candidate_id == candidate_id
            and item.owner_actor_id == actor_id
            and item.organization_id == organization_id
        ]
        return max(candidates, key=lambda item: item.analysis_version).model_copy(deep=True) if candidates else None

    async def list_for_candidate(
        self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID
    ) -> tuple[CombinedGapPortfolio, ...]:
        candidates = [
            item for item in self._profiles.values()
            if item.candidate_id == candidate_id
            and item.owner_actor_id == actor_id
            and item.organization_id == organization_id
        ]
        return tuple(
            item.to_combined_gap_portfolio()
            for item in sorted(candidates, key=lambda item: item.analysis_version, reverse=True)
        )

    async def list_for_target_references(
        self,
        target_references: tuple[tuple[str, str], ...],
        *,
        actor_id: UUID,
        organization_id: UUID,
    ) -> tuple[CombinedGapPortfolio, ...]:
        references = set(target_references)
        candidates = [
            item
            for item in self._profiles.values()
            if item.owner_actor_id == actor_id
            and item.organization_id == organization_id
            and (item.current_role.target_id, item.current_target_version) in references
        ]
        return tuple(
            item.to_combined_gap_portfolio()
            for item in sorted(candidates, key=lambda item: item.analysis_version, reverse=True)
        )

    async def record_rejected_input(
        self, *, portfolio_id: str | None, action: str, metadata: dict[str, object]
    ) -> None:
        self.audit_events.append(
            {
                "action": action,
                "portfolio_id": portfolio_id,
                **self._safe_rejection_metadata(metadata),
            }
        )

    async def record_human_assisted_reanalysis(
        self,
        *,
        portfolio_id: str,
        source_analysis_id: str,
        evidence_selections: list[HumanAssistedEvidenceSelection],
        reviewer_actor_id: UUID,
    ) -> None:
        self.audit_events.append(
            {
                "action": "CAPABILITY_GAP_HUMAN_ASSISTED_REANALYSIS_CREATED",
                "portfolio_id": portfolio_id,
                "source_analysis_id": source_analysis_id,
                "origin": "HUMAN_ASSISTED_EVIDENCE",
                "reviewer_actor_id": str(reviewer_actor_id),
                "evidence_selections": [item.model_dump(mode="json") for item in evidence_selections],
            }
        )

    @staticmethod
    def _validate(profile: CapabilityGapProfile) -> None:
        portfolio = profile.to_combined_gap_portfolio()
        gap_ids = [gap.id for gap in portfolio.current_role.gaps]
        if portfolio.future_role is not None:
            gap_ids.extend(gap.id for gap in portfolio.future_role.gaps)
        if len(gap_ids) != len(set(gap_ids)):
            raise ValueError("Capability gap identities must be unique")
        known_gap_ids = set(gap_ids)
        links = [(link.source_gap_id, link.target_gap_id) for link in portfolio.overlap_links]
        if len(links) != len(set(links)):
            raise ValueError("Capability gap overlap links must be unique")
        if any(
            source not in known_gap_ids or target not in known_gap_ids for source, target in links
        ):
            raise ValueError("Capability gap overlap links must reference persisted gaps")

    @staticmethod
    def _safe_audit_metadata(profile: CapabilityGapProfile) -> dict[str, object]:
        portfolio = profile.to_combined_gap_portfolio()
        return {
            "portfolio_id": portfolio.id,
            "cv_profile_id": portfolio.cv_profile_id,
            "cv_profile_version": portfolio.cv_profile_version,
            "current_target_id": portfolio.current_role.target_id,
            "current_target_version": portfolio.current_target_version,
            "current_usage_mode": portfolio.current_role.usage_mode.value,
            "future_target_id": portfolio.future_role.target_id if portfolio.future_role else None,
            "future_target_version": portfolio.future_target_version,
            "future_usage_mode": portfolio.future_role.usage_mode.value
            if portfolio.future_role
            else None,
            "owner_actor_id": str(portfolio.owner_actor_id),
            "organization_id": str(portfolio.organization_id),
            "correlation_id": portfolio.correlation_id,
            "warning_codes": portfolio.future_role.warning_codes if portfolio.future_role else [],
            "gap_count": len(portfolio.current_role.gaps)
            + (len(portfolio.future_role.gaps) if portfolio.future_role else 0),
        }

    @staticmethod
    def _safe_rejection_metadata(metadata: dict[str, object]) -> dict[str, object]:
        return {
            key: value
            for key, value in metadata.items()
            if key in _REJECTION_AUDIT_FIELDS
            and (value is None or (isinstance(value, str) and _IDENTIFIER_PATTERN.fullmatch(value)))
        }


class SqlAlchemyCapabilityGapPortfolioRepository(InMemoryCapabilityGapPortfolioRepository):
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, fail_audit: bool = False
    ) -> None:
        super().__init__()
        self._session_factory = session_factory
        self._fail_audit = fail_audit

    async def create(self, portfolio: CombinedGapPortfolio) -> CombinedGapPortfolio:
        profile = await self.create_profile(CapabilityGapProfile.from_combined_gap_portfolio(portfolio))
        return profile.to_combined_gap_portfolio()

    async def create_profile(self, profile: CapabilityGapProfile) -> CapabilityGapProfile:
        self._validate(profile)
        portfolio = profile.to_combined_gap_portfolio()
        try:
            async with self._session_factory() as session, session.begin():
                existing = await session.get(CapabilityGapPortfolioRecord, portfolio.id)
                if existing is not None:
                    raise ValueError("Capability gap portfolio is immutable")
                session.add(self._portfolio_record(portfolio))
                await session.flush()
                self._add_track(session, portfolio.id, portfolio.current_role)
                if portfolio.future_role is not None:
                    self._add_track(session, portfolio.id, portfolio.future_role)
                for link in portfolio.overlap_links:
                    session.add(
                        GapOverlapLinkRecord(
                            record_id=str(uuid4()),
                            portfolio_id=portfolio.id,
                            source_gap_id=link.source_gap_id,
                            target_gap_id=link.target_gap_id,
                            shared_theme=link.shared_theme,
                        )
                    )
                if self._fail_audit:
                    raise AuditPersistenceError("Capability gap audit persistence failed")
                session.add(self._audit_record(portfolio))
        except AuditPersistenceError:
            raise
        except SQLAlchemyError as error:
            raise AuditPersistenceError("Capability gap portfolio persistence failed") from error
        return profile.model_copy(deep=True)

    async def get(self, portfolio_id: str) -> CombinedGapPortfolio | None:
        profile = await self.get_profile(portfolio_id)
        return profile.to_combined_gap_portfolio() if profile else None

    async def get_profile(self, portfolio_id: str) -> CapabilityGapProfile | None:
        async with self._session_factory() as session:
            record = await session.get(CapabilityGapPortfolioRecord, portfolio_id)
            if record is None:
                return None
            assessments = list(
                (
                    await session.scalars(
                        select(RequirementAssessmentRecord).where(
                            RequirementAssessmentRecord.portfolio_id == portfolio_id
                        )
                    )
                ).all()
            )
            gaps = list(
                (
                    await session.scalars(
                        select(TargetGapRecord).where(TargetGapRecord.portfolio_id == portfolio_id)
                    )
                ).all()
            )
            links = list(
                (
                    await session.scalars(
                        select(GapOverlapLinkRecord).where(
                            GapOverlapLinkRecord.portfolio_id == portfolio_id
                        )
                    )
                ).all()
            )
        raw_semantic_targets = (
            record.semantic_policy.get("targets", [])
            if record.semantic_policy is not None
            else []
        )
        if not isinstance(raw_semantic_targets, list):
            raw_semantic_targets = []
        legacy = CombinedGapPortfolio(
            id=record.id,
            cv_profile_id=record.cv_profile_id,
            cv_profile_version=record.cv_profile_version,
            current_target_version=record.current_target_version,
            future_target_version=record.future_target_version,
            owner_actor_id=UUID(record.owner_actor_id),
            organization_id=UUID(record.organization_id),
            correlation_id=record.correlation_id,
            candidate_id=UUID(record.candidate_id) if record.candidate_id else None,
            analysis_status=AnalysisStatus(record.analysis_status),
            analysis_version=record.analysis_version,
            idempotency_key=record.idempotency_key,
            current_role=self._track(
                record.current_target_id,
                record.current_usage_mode,
                TargetType.CURRENT_ROLE,
                assessments,
                gaps,
            ),
            future_role=(
                self._track(
                    record.future_target_id,
                    record.future_usage_mode,
                    TargetType.FUTURE_ROLE,
                    assessments,
                    gaps,
                )
                if record.future_target_id is not None and record.future_usage_mode is not None
                else None
            ),
            overlap_links=[
                GapOverlapLink(
                    source_gap_id=item.source_gap_id,
                    target_gap_id=item.target_gap_id,
                    shared_theme=item.shared_theme,
                )
                for item in links
            ],
            snapshot_schema_version=record.snapshot_schema_version,
            preview_readiness=(
                PreviewReadiness.model_validate(record.preview_readiness, strict=False)
                if record.preview_readiness is not None
                else None
            ),
            verification_queue=[
                VerificationQueueItem.model_validate(item, strict=False)
                for item in record.verification_queue
            ],
            semantic_policies=tuple(
                TargetSemanticPolicySnapshot.model_validate(item, strict=False)
                for item in raw_semantic_targets
            ),
        )
        return CapabilityGapProfile.from_combined_gap_portfolio(legacy)

    async def get_for_candidate(
        self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID
    ) -> CombinedGapPortfolio | None:
        profile = await self.get_profile_for_candidate(
            candidate_id, actor_id=actor_id, organization_id=organization_id
        )
        return profile.to_combined_gap_portfolio() if profile else None

    async def get_profile_for_candidate(
        self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID
    ) -> CapabilityGapProfile | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CapabilityGapPortfolioRecord)
                .where(
                    CapabilityGapPortfolioRecord.candidate_id == str(candidate_id),
                    CapabilityGapPortfolioRecord.owner_actor_id == str(actor_id),
                    CapabilityGapPortfolioRecord.organization_id == str(organization_id),
                )
                .order_by(CapabilityGapPortfolioRecord.analysis_version.desc())
                .limit(1)
            )
        return await self.get_profile(record.id) if record is not None else None

    async def list_for_candidate(
        self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID
    ) -> tuple[CombinedGapPortfolio, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(CapabilityGapPortfolioRecord)
                    .where(
                        CapabilityGapPortfolioRecord.candidate_id == str(candidate_id),
                        CapabilityGapPortfolioRecord.owner_actor_id == str(actor_id),
                        CapabilityGapPortfolioRecord.organization_id == str(organization_id),
                    )
                    .order_by(
                        CapabilityGapPortfolioRecord.created_at.desc(),
                        CapabilityGapPortfolioRecord.id.desc(),
                    )
                )
            ).all()
        portfolios: list[CombinedGapPortfolio] = []
        for record in records:
            profile = await self.get_profile(record.id)
            if profile is not None:
                portfolios.append(profile.to_combined_gap_portfolio())
        return tuple(portfolios)

    async def list_for_target_references(
        self,
        target_references: tuple[tuple[str, str], ...],
        *,
        actor_id: UUID,
        organization_id: UUID,
    ) -> tuple[CombinedGapPortfolio, ...]:
        if not target_references:
            return ()
        reference_filter = or_(*[
            and_(
                CapabilityGapPortfolioRecord.current_target_id == target_id,
                CapabilityGapPortfolioRecord.current_target_version == target_version,
            )
            for target_id, target_version in target_references
        ])
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(CapabilityGapPortfolioRecord)
                    .where(
                        CapabilityGapPortfolioRecord.owner_actor_id == str(actor_id),
                        CapabilityGapPortfolioRecord.organization_id == str(organization_id),
                        reference_filter,
                    )
                    .order_by(
                        CapabilityGapPortfolioRecord.created_at.desc(),
                        CapabilityGapPortfolioRecord.id.desc(),
                    )
                )
            ).all()
        portfolios: list[CombinedGapPortfolio] = []
        for record in records:
            profile = await self.get_profile(record.id)
            if profile is not None:
                portfolios.append(profile.to_combined_gap_portfolio())
        return tuple(portfolios)

    async def record_rejected_input(
        self, *, portfolio_id: str | None, action: str, metadata: dict[str, object]
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                CapabilityGapAuditEventRecord(
                    id=str(uuid4()),
                    portfolio_id=portfolio_id,
                    action=action,
                    audit_metadata=self._safe_rejection_metadata(metadata),
                )
            )

    async def record_human_assisted_reanalysis(
        self,
        *,
        portfolio_id: str,
        source_analysis_id: str,
        evidence_selections: list[HumanAssistedEvidenceSelection],
        reviewer_actor_id: UUID,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                CapabilityGapAuditEventRecord(
                    id=str(uuid4()),
                    portfolio_id=portfolio_id,
                    action="CAPABILITY_GAP_HUMAN_ASSISTED_REANALYSIS_CREATED",
                    audit_metadata={
                        "origin": "HUMAN_ASSISTED_EVIDENCE",
                        "source_analysis_id": source_analysis_id,
                        "reviewer_actor_id": str(reviewer_actor_id),
                        "evidence_selections": [
                            item.model_dump(mode="json") for item in evidence_selections
                        ],
                    },
                )
            )

    @staticmethod
    def _portfolio_record(portfolio: CombinedGapPortfolio) -> CapabilityGapPortfolioRecord:
        return CapabilityGapPortfolioRecord(
            id=portfolio.id,
            cv_profile_id=portfolio.cv_profile_id,
            cv_profile_version=portfolio.cv_profile_version,
            current_target_id=portfolio.current_role.target_id,
            current_target_version=portfolio.current_target_version,
            current_usage_mode=portfolio.current_role.usage_mode.value,
            future_target_id=portfolio.future_role.target_id if portfolio.future_role else None,
            future_target_version=portfolio.future_target_version,
            future_usage_mode=portfolio.future_role.usage_mode.value
            if portfolio.future_role
            else None,
            owner_actor_id=str(portfolio.owner_actor_id),
            organization_id=str(portfolio.organization_id),
            correlation_id=portfolio.correlation_id,
            candidate_id=str(portfolio.candidate_id) if portfolio.candidate_id else None,
            analysis_status=portfolio.analysis_status.value,
            analysis_version=portfolio.analysis_version,
            idempotency_key=portfolio.idempotency_key,
            snapshot_schema_version=portfolio.snapshot_schema_version,
            preview_readiness=(
                portfolio.preview_readiness.model_dump(mode="json")
                if portfolio.preview_readiness is not None
                else None
            ),
            verification_queue=[item.model_dump(mode="json") for item in portfolio.verification_queue],
            semantic_policy=(
                {
                    "targets": [
                        item.model_dump(mode="json")
                        for item in portfolio.semantic_policies
                    ]
                }
                if portfolio.semantic_policies
                else None
            ),
        )

    @staticmethod
    def _add_track(session: AsyncSession, portfolio_id: str, track: TargetGapAnalysis) -> None:
        for assessment in track.assessments:
            session.add(
                RequirementAssessmentRecord(
                    record_id=str(uuid4()),
                    portfolio_id=portfolio_id,
                    target_id=track.target_id,
                    target_type=track.target_type.value,
                    requirement_id=assessment.requirement_id,
                    payload=assessment.model_dump(mode="json"),
                )
            )
        for gap in track.gaps:
            session.add(
                TargetGapRecord(
                    id=f"{portfolio_id}:{gap.id}",
                    portfolio_id=portfolio_id,
                    target_id=track.target_id,
                    target_type=track.target_type.value,
                    requirement_id=gap.requirement_id,
                    payload=gap.model_dump(mode="json"),
                )
            )

    @staticmethod
    def _track(
        target_id: str,
        usage_mode: str,
        target_type: TargetType,
        assessment_records: list[RequirementAssessmentRecord],
        gap_records: list[TargetGapRecord],
    ) -> TargetGapAnalysis:
        assessments = [
            RequirementAssessment.model_validate(item.payload, strict=False)
            for item in assessment_records
            if item.target_type == target_type.value
        ]
        gaps = [
            TargetGap.model_validate(item.payload, strict=False)
            for item in gap_records
            if item.target_type == target_type.value
        ]
        return TargetGapAnalysis(
            target_id=target_id,
            target_type=target_type,
            usage_mode=TargetUsageMode(usage_mode),
            assessments=assessments,
            gaps=gaps,
            warning_codes=(
                [
                    "current_target_profile_provisional"
                    if target_type is TargetType.CURRENT_ROLE
                    else "future_target_profile_provisional"
                ]
                if usage_mode == TargetUsageMode.PREVIEW.value
                else []
            ),
        )

    @classmethod
    def _audit_record(cls, portfolio: CombinedGapPortfolio) -> CapabilityGapAuditEventRecord:
        return CapabilityGapAuditEventRecord(
            id=str(uuid4()),
            portfolio_id=portfolio.id,
            action="CAPABILITY_GAP_PORTFOLIO_CREATED",
            audit_metadata=cls._safe_audit_metadata(
                CapabilityGapProfile.from_combined_gap_portfolio(portfolio)
            ),
        )
