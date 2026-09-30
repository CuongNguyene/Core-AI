from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.matching.models import (
    MatchEvidenceAllocationRecord,
    MatchingAuditEventRecord,
    PreliminaryMatchRecord,
    RoleCompetencyProfileRecord,
    RoleProfileSemanticPolicyMappingRecord,
)
from app.matching.schemas import (
    PreliminaryMatch,
    PreliminaryMatchStatus,
    RoleCompetencyProfile,
    RoleProfileSemanticPolicyMapping,
    RoleProfileStatus,
)
from app.role_registry.models import RoleRecord
from app.semantic_policy.schemas import SemanticPolicyRef


class RoleProfileRepository(Protocol):
    async def save(self, profile: RoleCompetencyProfile) -> RoleCompetencyProfile: ...

    async def get_active(self, role_profile_id: str) -> RoleCompetencyProfile | None: ...

    async def get_version(
        self, role_profile_id: str, version: str
    ) -> RoleCompetencyProfile | None: ...

    async def get_preferred_target(self, role_profile_id: str) -> RoleCompetencyProfile | None: ...

    async def get_latest(self, role_profile_id: str) -> RoleCompetencyProfile | None: ...

    async def get_active_for_role(self, role_id: UUID) -> RoleCompetencyProfile | None: ...

    async def list_for_role(self, role_id: UUID) -> list[RoleCompetencyProfile]: ...

    async def activate_for_role(
        self, role_id: UUID, *, profile_id: str, governance_version: int
    ) -> RoleCompetencyProfile: ...

    async def get_semantic_policy_mapping(
        self, role_profile_id: str, role_profile_version: str
    ) -> RoleProfileSemanticPolicyMapping | None: ...

    async def bind_semantic_policy(
        self, role_profile_id: str, role_profile_version: str, reference: SemanticPolicyRef
    ) -> None: ...


class PreliminaryMatchRepository(Protocol):
    async def create(self, match: PreliminaryMatch) -> PreliminaryMatch: ...

    async def get(self, match_id: str) -> PreliminaryMatch | None: ...

    async def review(
        self,
        match_id: str,
        *,
        reviewer_id: UUID,
        approved_gap_ids: list[str],
        expected_version: int,
        reviewed_at: datetime,
    ) -> PreliminaryMatch: ...

    async def record_rejected_input(
        self,
        *,
        actor_id: UUID,
        correlation_id: str,
        cv_profile_id: str,
        role_profile_id: str,
        action: str,
    ) -> None: ...


class InMemoryRoleProfileRepository:
    """Fixture-backed role profile adapter for deterministic MVP tests."""

    def __init__(
        self,
        profiles: list[RoleCompetencyProfile],
        *,
        semantic_policy_mappings: tuple[RoleProfileSemanticPolicyMapping, ...] = (),
    ) -> None:
        self._profiles = [profile.model_copy(deep=True) for profile in profiles]
        self._active_by_role: dict[UUID, str] = {}
        self._semantic_policy_mappings = {
            (mapping.role_profile_id, mapping.role_profile_version): mapping.model_copy(deep=True)
            for mapping in semantic_policy_mappings
        }

    async def save(self, profile: RoleCompetencyProfile) -> RoleCompetencyProfile:
        if any(item.id == profile.id and item.version == profile.version for item in self._profiles):
            raise ValueError("Role profile versions are immutable")
        if profile.role_id is None:
            saved = profile.model_copy(deep=True)
        else:
            existing_versions = [
                item.governance_version
                for item in self._profiles
                if item.role_id == profile.role_id and item.governance_version is not None
            ]
            saved = profile.model_copy(
                update={"governance_version": max(existing_versions, default=0) + 1}
                if profile.governance_version is None
                else {}
            )
            if any(
                item.role_id == saved.role_id
                and item.governance_version == saved.governance_version
                for item in self._profiles
            ):
                raise ValueError("Role governance versions are not unique")
        self._profiles.append(saved.model_copy(deep=True))
        return saved.model_copy(deep=True)

    async def replace(self, profile: RoleCompetencyProfile) -> RoleCompetencyProfile:
        for index, item in enumerate(self._profiles):
            if item.id == profile.id and item.version == profile.version:
                self._profiles[index] = profile.model_copy(deep=True)
                return profile.model_copy(deep=True)
        raise KeyError((profile.id, profile.version))

    async def activate_for_role(
        self, role_id: UUID, *, profile_id: str, governance_version: int
    ) -> RoleCompetencyProfile:
        target = next(
            (
                item
                for item in self._profiles
                if item.id == profile_id
                and item.role_id == role_id
                and item.governance_version == governance_version
            ),
            None,
        )
        if target is None:
            raise KeyError("role profile governance version")
        current_id = self._active_by_role.get(role_id)
        if current_id == target.id:
            if target.status is not RoleProfileStatus.ACTIVE:
                raise ValueError("only active-eligible profiles can be activated")
            return target.model_copy(deep=True)
        if current_id is not None and current_id != target.id:
            current = next(item for item in self._profiles if item.id == current_id)
            if (current.governance_version or 0) >= (target.governance_version or 0):
                raise ValueError("older governance version cannot become active")
            await self.replace(current.model_copy(update={"status": RoleProfileStatus.RETIRED}))
        if target.status is not RoleProfileStatus.ACTIVE:
            raise ValueError("only active-eligible profiles can be activated")
        self._active_by_role[role_id] = target.id
        return target.model_copy(deep=True)

    async def get_active_for_role(self, role_id: UUID) -> RoleCompetencyProfile | None:
        profile_id = self._active_by_role.get(role_id)
        if profile_id is None:
            return None
        profile = next((item for item in self._profiles if item.id == profile_id), None)
        return profile.model_copy(deep=True) if profile else None

    async def list_for_role(self, role_id: UUID) -> list[RoleCompetencyProfile]:
        return [
            item.model_copy(deep=True)
            for item in self._profiles
            if item.role_id == role_id
        ]

    async def get_active(self, role_profile_id: str) -> RoleCompetencyProfile | None:
        profile = next(
            (
                item
                for item in self._profiles
                if item.id == role_profile_id and item.status is RoleProfileStatus.ACTIVE
            ),
            None,
        )
        return profile.model_copy(deep=True) if profile else None

    async def get_version(self, role_profile_id: str, version: str) -> RoleCompetencyProfile | None:
        profile = next(
            (
                item
                for item in self._profiles
                if item.id == role_profile_id and item.version == version
            ),
            None,
        )
        return profile.model_copy(deep=True) if profile else None

    async def get_preferred_target(self, role_profile_id: str) -> RoleCompetencyProfile | None:
        for status in (RoleProfileStatus.ACTIVE, RoleProfileStatus.PROVISIONAL):
            profile = next(
                (
                    item
                    for item in self._profiles
                    if item.id == role_profile_id and item.status is status
                ),
                None,
            )
            if profile is not None:
                return profile.model_copy(deep=True)
        return None

    async def get_latest(self, role_profile_id: str) -> RoleCompetencyProfile | None:
        profile = next(
            (item for item in reversed(self._profiles) if item.id == role_profile_id), None
        )
        return profile.model_copy(deep=True) if profile else None

    async def save_semantic_policy_mapping(
        self, mapping: RoleProfileSemanticPolicyMapping
    ) -> None:
        key = (mapping.role_profile_id, mapping.role_profile_version)
        if key in self._semantic_policy_mappings:
            raise ValueError("Role profile semantic policy mappings are immutable")
        self._semantic_policy_mappings[key] = mapping.model_copy(deep=True)

    async def get_semantic_policy_mapping(
        self, role_profile_id: str, role_profile_version: str
    ) -> RoleProfileSemanticPolicyMapping | None:
        mapping = self._semantic_policy_mappings.get((role_profile_id, role_profile_version))
        return mapping.model_copy(deep=True) if mapping else None

    async def bind_semantic_policy(
        self, role_profile_id: str, role_profile_version: str, reference: SemanticPolicyRef
    ) -> None:
        for index, profile in enumerate(self._profiles):
            if profile.id == role_profile_id and profile.version == role_profile_version:
                if profile.status is RoleProfileStatus.ACTIVE:
                    raise ValueError("active role profile semantic policy is immutable")
                self._profiles[index] = profile.model_copy(
                    update={"semantic_policy_ref": reference}, deep=True
                )
                return
        raise KeyError((role_profile_id, role_profile_version))


class InMemoryPreliminaryMatchRepository:
    """Deterministic match repository used by unit and API tests."""

    def __init__(self) -> None:
        self._matches: dict[str, PreliminaryMatch] = {}
        self.audit_events: list[dict[str, object]] = []

    async def create(self, match: PreliminaryMatch) -> PreliminaryMatch:
        if match.id in self._matches:
            raise ValueError("Preliminary match already exists")
        evidence_ids = [allocation.evidence_id for allocation in match.evidence_allocations]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("A decisive evidence claim can only be allocated once")
        self._matches[match.id] = match.model_copy(deep=True)
        metadata = self._safe_audit_metadata(match)
        self.audit_events.append(
            {
                "action": "MATCHING_STARTED",
                "match_id": match.id,
                **metadata,
            }
        )
        self.audit_events.append(
            {
                "action": "MATCHING_COMPLETED",
                "match_id": match.id,
                **metadata,
            }
        )
        return self._matches[match.id].model_copy(deep=True)

    async def get(self, match_id: str) -> PreliminaryMatch | None:
        match = self._matches.get(match_id)
        return match.model_copy(deep=True) if match else None

    async def review(
        self,
        match_id: str,
        *,
        reviewer_id: UUID,
        approved_gap_ids: list[str],
        expected_version: int,
        reviewed_at: datetime,
    ) -> PreliminaryMatch:
        match = self._matches.get(match_id)
        if match is None:
            raise KeyError(match_id)
        if match.version != expected_version:
            raise ValueError("version_conflict")
        if match.status is not PreliminaryMatchStatus.COMPLETED:
            raise ValueError("invalid_review_transition")
        gap_ids = {gap.requirement_id for gap in match.preliminary_skill_gaps}
        if any(gap_id not in gap_ids for gap_id in approved_gap_ids):
            raise ValueError("unknown_gap")
        reviewed = match.model_copy(
            update={
                "status": PreliminaryMatchStatus.REVIEWED,
                "version": match.version + 1,
                "approved_gap_ids": list(dict.fromkeys(approved_gap_ids)),
                "reviewed_by": reviewer_id,
                "reviewed_at": reviewed_at,
            },
            deep=True,
        )
        self._matches[match_id] = reviewed
        self.audit_events.append(
            {
                "action": "MATCHING_REVIEWED",
                "match_id": match_id,
                "reviewer_id": reviewer_id,
                "approved_gap_count": len(reviewed.approved_gap_ids),
            }
        )
        return reviewed.model_copy(deep=True)

    async def record_rejected_input(
        self,
        *,
        actor_id: UUID,
        correlation_id: str,
        cv_profile_id: str,
        role_profile_id: str,
        action: str,
    ) -> None:
        self.audit_events.append(
            {
                "action": action,
                "actor_id": actor_id,
                "correlation_id": correlation_id,
                "cv_profile_id": cv_profile_id,
                "role_profile_id": role_profile_id,
            }
        )

    @staticmethod
    def _safe_audit_metadata(match: PreliminaryMatch) -> dict[str, object]:
        return {
            "cv_profile_id": match.cv_profile_id,
            "cv_profile_version": match.cv_profile_version,
            "role_profile_id": match.role_profile_id,
            "role_profile_version": match.role_profile_version,
            "rule_set_version": match.rule_set_version,
            "policy_version": match.policy_version,
            "correlation_id": match.correlation_id,
        }


class SqlAlchemyRoleProfileRepository:
    """Persistence adapter for the active, versioned role profile fixture."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, profile: RoleCompetencyProfile) -> RoleCompetencyProfile:
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(RoleCompetencyProfileRecord).where(
                    RoleCompetencyProfileRecord.id == profile.id,
                    RoleCompetencyProfileRecord.version == profile.version,
                )
            )
            if existing is not None:
                raise ValueError("Role profile versions are immutable")
            if profile.role_id is not None and profile.governance_version is None:
                role = await session.get(RoleRecord, profile.role_id, with_for_update=True)
                if role is None:
                    raise ValueError("Stable Role was not found")
                next_governance_version = await session.scalar(
                    select(func.max(RoleCompetencyProfileRecord.governance_version)).where(
                        RoleCompetencyProfileRecord.role_id == profile.role_id
                    )
                )
                profile = profile.model_copy(
                    update={"governance_version": (next_governance_version or 0) + 1}
                )
            if profile.role_id is not None and profile.governance_version is not None:
                duplicate_governance_version = await session.scalar(
                    select(RoleCompetencyProfileRecord).where(
                        RoleCompetencyProfileRecord.role_id == profile.role_id,
                        RoleCompetencyProfileRecord.governance_version
                        == profile.governance_version,
                    )
                )
                if duplicate_governance_version is not None:
                    raise ValueError("Role governance versions are not unique")
            if profile.status is RoleProfileStatus.ACTIVE:
                active_version = await session.scalar(
                    select(RoleCompetencyProfileRecord).where(
                        RoleCompetencyProfileRecord.id == profile.id,
                        RoleCompetencyProfileRecord.status == RoleProfileStatus.ACTIVE.value,
                    )
                )
                if active_version is not None:
                    raise ValueError("Only one role profile version may be active")
            values = {
                "version": profile.version,
                "status": profile.status.value,
                "source_jd_profile_id": profile.source_jd_profile_id,
                "source_jd_profile_version": profile.source_jd_profile_version,
                "rule_set_version": profile.rule_set_version,
                "policy_version": profile.policy_version,
                "requirements": [item.model_dump(mode="json") for item in profile.requirements],
                "semantic_core_version": (
                    profile.semantic_policy.core_version
                    if profile.semantic_policy is not None
                    else None
                ),
                "semantic_pack_refs": (
                    [
                        {"pack_id": item.pack_id, "version": item.version}
                        for item in profile.semantic_policy.pack_refs
                    ]
                    if profile.semantic_policy is not None
                    else None
                ),
                "semantic_policy_id": (
                    profile.semantic_policy_ref.policy_id
                    if profile.semantic_policy_ref is not None
                    else None
                ),
                "semantic_policy_version": (
                    profile.semantic_policy_ref.policy_version
                    if profile.semantic_policy_ref is not None
                    else None
                ),
                "role_id": profile.role_id,
                "role_jd_version_id": profile.role_jd_version_id,
                "governance_version": profile.governance_version,
            }
            session.add(
                RoleCompetencyProfileRecord(record_id=str(uuid4()), id=profile.id, **values)
            )
        return profile

    async def get_active(self, role_profile_id: str) -> RoleCompetencyProfile | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(RoleCompetencyProfileRecord).where(
                    RoleCompetencyProfileRecord.id == role_profile_id,
                    RoleCompetencyProfileRecord.status == RoleProfileStatus.ACTIVE.value,
                )
            )
            if record is None:
                return None
            return RoleCompetencyProfile.model_validate(
                {
                    "id": record.id,
                    "version": record.version,
                    "status": record.status,
                    "source_jd_profile_id": record.source_jd_profile_id,
                    "source_jd_profile_version": record.source_jd_profile_version,
                    "rule_set_version": record.rule_set_version,
                    "policy_version": record.policy_version,
                    "requirements": record.requirements,
                    "role_id": record.role_id,
                    "role_jd_version_id": record.role_jd_version_id,
                    "governance_version": record.governance_version,
                    **self._semantic_policy_fields(record),
                },
                strict=False,
            )

    async def get_active_for_role(self, role_id: UUID) -> RoleCompetencyProfile | None:
        async with self._session_factory() as session:
            role = await session.get(RoleRecord, role_id)
            if role is None or role.active_role_profile_id is None:
                return None
            record = await session.scalar(
                select(RoleCompetencyProfileRecord).where(
                    RoleCompetencyProfileRecord.id == role.active_role_profile_id,
                    RoleCompetencyProfileRecord.role_id == role_id,
                )
            )
            return _profile_schema(record) if record is not None else None

    async def list_for_role(self, role_id: UUID) -> list[RoleCompetencyProfile]:
        async with self._session_factory() as session:
            records = list(
                (
                    await session.scalars(
                        select(RoleCompetencyProfileRecord)
                        .where(RoleCompetencyProfileRecord.role_id == role_id)
                        .order_by(
                            RoleCompetencyProfileRecord.governance_version.asc().nulls_last(),
                            RoleCompetencyProfileRecord.id,
                            RoleCompetencyProfileRecord.version,
                        )
                    )
                ).all()
            )
            return [_profile_schema(record) for record in records]

    async def activate_for_role(
        self, role_id: UUID, *, profile_id: str, governance_version: int
    ) -> RoleCompetencyProfile:
        async with self._session_factory() as session, session.begin():
            role = await session.get(RoleRecord, role_id, with_for_update=True)
            if role is None:
                raise KeyError(role_id)
            target = await session.scalar(
                select(RoleCompetencyProfileRecord)
                .where(
                    RoleCompetencyProfileRecord.id == profile_id,
                    RoleCompetencyProfileRecord.role_id == role_id,
                    RoleCompetencyProfileRecord.governance_version == governance_version,
                )
                .with_for_update()
            )
            if target is None:
                raise KeyError("role profile governance version")
            if role.active_role_profile_id == target.id:
                if target.status != RoleProfileStatus.ACTIVE.value:
                    raise ValueError("only active-eligible profiles can be activated")
                return _profile_schema(target)
            if role.active_role_profile_id is not None:
                current = await session.scalar(
                    select(RoleCompetencyProfileRecord).where(
                        RoleCompetencyProfileRecord.id == role.active_role_profile_id,
                        RoleCompetencyProfileRecord.role_id == role_id,
                    ).with_for_update()
                )
                if current is None:
                    raise ValueError("active role profile pointer is invalid")
                if (current.governance_version or 0) >= governance_version:
                    raise ValueError("older governance version cannot become active")
                current.status = RoleProfileStatus.RETIRED.value
            if target.status != RoleProfileStatus.ACTIVE.value:
                raise ValueError("only active-eligible profiles can be activated")
            role.active_role_profile_id = target.id
            return _profile_schema(target)

    async def get_version(self, role_profile_id: str, version: str) -> RoleCompetencyProfile | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(RoleCompetencyProfileRecord).where(
                    RoleCompetencyProfileRecord.id == role_profile_id,
                    RoleCompetencyProfileRecord.version == version,
                )
            )
            if record is None:
                return None
            return RoleCompetencyProfile.model_validate(
                {
                    "id": record.id,
                    "version": record.version,
                    "status": record.status,
                    "source_jd_profile_id": record.source_jd_profile_id,
                    "source_jd_profile_version": record.source_jd_profile_version,
                    "rule_set_version": record.rule_set_version,
                    "policy_version": record.policy_version,
                    "requirements": record.requirements,
                    "role_id": record.role_id,
                    "role_jd_version_id": record.role_jd_version_id,
                    "governance_version": record.governance_version,
                    **self._semantic_policy_fields(record),
                },
                strict=False,
            )

    async def get_preferred_target(self, role_profile_id: str) -> RoleCompetencyProfile | None:
        async with self._session_factory() as session:
            for status in (RoleProfileStatus.ACTIVE, RoleProfileStatus.PROVISIONAL):
                record = await session.scalar(
                    select(RoleCompetencyProfileRecord).where(
                        RoleCompetencyProfileRecord.id == role_profile_id,
                        RoleCompetencyProfileRecord.status == status.value,
                    )
                )
                if record is not None:
                    return RoleCompetencyProfile.model_validate(
                        {
                            "id": record.id,
                            "version": record.version,
                            "status": record.status,
                            "source_jd_profile_id": record.source_jd_profile_id,
                            "source_jd_profile_version": record.source_jd_profile_version,
                            "rule_set_version": record.rule_set_version,
                            "policy_version": record.policy_version,
                            "requirements": record.requirements,
                            "role_id": record.role_id,
                            "role_jd_version_id": record.role_jd_version_id,
                            "governance_version": record.governance_version,
                            **self._semantic_policy_fields(record),
                        },
                        strict=False,
                    )
        return None

    async def get_latest(self, role_profile_id: str) -> RoleCompetencyProfile | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(RoleCompetencyProfileRecord)
                .where(RoleCompetencyProfileRecord.id == role_profile_id)
                .order_by(RoleCompetencyProfileRecord.record_id.desc())
                .limit(1)
            )
            if record is None:
                return None
            return RoleCompetencyProfile.model_validate(
                {
                    "id": record.id,
                    "version": record.version,
                    "status": record.status,
                    "source_jd_profile_id": record.source_jd_profile_id,
                    "source_jd_profile_version": record.source_jd_profile_version,
                    "rule_set_version": record.rule_set_version,
                    "policy_version": record.policy_version,
                    "requirements": record.requirements,
                    "role_id": record.role_id,
                    "role_jd_version_id": record.role_jd_version_id,
                    "governance_version": record.governance_version,
                    **self._semantic_policy_fields(record),
                },
                strict=False,
            )

    async def save_semantic_policy_mapping(
        self, mapping: RoleProfileSemanticPolicyMapping
    ) -> None:
        async with self._session_factory() as session, session.begin():
            existing = await session.get(
                RoleProfileSemanticPolicyMappingRecord,
                (mapping.role_profile_id, mapping.role_profile_version),
            )
            if existing is not None:
                raise ValueError("Role profile semantic policy mappings are immutable")
            session.add(
                RoleProfileSemanticPolicyMappingRecord(
                    role_profile_id=mapping.role_profile_id,
                    role_profile_version=mapping.role_profile_version,
                    core_version=mapping.core_version,
                    pack_refs=[
                        {"pack_id": item.pack_id, "version": item.version}
                        for item in mapping.pack_refs
                    ],
                    selection_source=mapping.selection_source.value,
                )
            )

    async def get_semantic_policy_mapping(
        self, role_profile_id: str, role_profile_version: str
    ) -> RoleProfileSemanticPolicyMapping | None:
        async with self._session_factory() as session:
            record = await session.get(
                RoleProfileSemanticPolicyMappingRecord,
                (role_profile_id, role_profile_version),
            )
        if record is None:
            return None
        return RoleProfileSemanticPolicyMapping.model_validate(
            {
                "role_profile_id": record.role_profile_id,
                "role_profile_version": record.role_profile_version,
                "core_version": record.core_version,
                "pack_refs": record.pack_refs,
                "selection_source": record.selection_source,
            },
            strict=False,
        )

    async def bind_semantic_policy(
        self, role_profile_id: str, role_profile_version: str, reference: SemanticPolicyRef
    ) -> None:
        async with self._session_factory() as session, session.begin():
            record = await session.scalar(
                select(RoleCompetencyProfileRecord).where(
                    RoleCompetencyProfileRecord.id == role_profile_id,
                    RoleCompetencyProfileRecord.version == role_profile_version,
                ).with_for_update()
            )
            if record is None:
                raise KeyError((role_profile_id, role_profile_version))
            if record.status == RoleProfileStatus.ACTIVE.value:
                raise ValueError("active role profile semantic policy is immutable")
            record.semantic_policy_id = reference.policy_id
            record.semantic_policy_version = reference.policy_version

    @staticmethod
    def _semantic_policy_payload(
        record: RoleCompetencyProfileRecord,
    ) -> dict[str, object] | None:
        if record.semantic_core_version is None or record.semantic_pack_refs is None:
            return None
        return {
            "core_version": record.semantic_core_version,
            "pack_refs": record.semantic_pack_refs,
        }

    @classmethod
    def _semantic_policy_fields(cls, record: RoleCompetencyProfileRecord) -> dict[str, object]:
        return {
            "semantic_policy": cls._semantic_policy_payload(record),
            "semantic_policy_ref": (
                {
                    "policy_id": record.semantic_policy_id,
                    "policy_version": record.semantic_policy_version,
                }
                if record.semantic_policy_id is not None
                and record.semantic_policy_version is not None
                else None
            ),
        }


def _profile_schema(record: RoleCompetencyProfileRecord) -> RoleCompetencyProfile:
    return RoleCompetencyProfile.model_validate(
        {
            "id": record.id,
            "version": record.version,
            "status": record.status,
            "source_jd_profile_id": record.source_jd_profile_id,
            "source_jd_profile_version": record.source_jd_profile_version,
            "rule_set_version": record.rule_set_version,
            "policy_version": record.policy_version,
            "requirements": record.requirements,
            "role_id": record.role_id,
            "role_jd_version_id": record.role_jd_version_id,
            "governance_version": record.governance_version,
            "semantic_policy": SqlAlchemyRoleProfileRepository._semantic_policy_payload(record),
            "semantic_policy_ref": (
                {
                    "policy_id": record.semantic_policy_id,
                    "policy_version": record.semantic_policy_version,
                }
                if record.semantic_policy_id is not None
                and record.semantic_policy_version is not None
                else None
            ),
        },
        strict=False,
    )


class SqlAlchemyPreliminaryMatchRepository:
    """Persistence adapter for preliminary results and append-only safe audit."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, match: PreliminaryMatch) -> PreliminaryMatch:
        evidence_ids = [allocation.evidence_id for allocation in match.evidence_allocations]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("A decisive evidence claim can only be allocated once")
        async with self._session_factory() as session, session.begin():
            audit_metadata = self._safe_audit_metadata(match)
            session.add(
                PreliminaryMatchRecord(
                    id=match.id,
                    cv_profile_id=match.cv_profile_id,
                    cv_profile_version=match.cv_profile_version,
                    jd_profile_id=match.jd_profile_id,
                    jd_profile_version=match.jd_profile_version,
                    role_profile_id=match.role_profile_id,
                    role_profile_version=match.role_profile_version,
                    rule_set_version=match.rule_set_version,
                    policy_version=match.policy_version,
                    actor_id=match.actor_id,
                    correlation_id=match.correlation_id,
                    status=match.status.value,
                    criterion_results=[
                        item.model_dump(mode="json") for item in match.criterion_results
                    ],
                    preliminary_skill_gaps=[
                        item.model_dump(mode="json") for item in match.preliminary_skill_gaps
                    ],
                    version=match.version,
                    approved_gap_ids=match.approved_gap_ids,
                    reviewed_by=match.reviewed_by,
                    reviewed_at=match.reviewed_at,
                )
            )
            for allocation in match.evidence_allocations:
                session.add(
                    MatchEvidenceAllocationRecord(
                        id=str(uuid4()),
                        match_id=match.id,
                        evidence_id=allocation.evidence_id,
                        requirement_id=allocation.requirement_id,
                    )
                )
            session.add(
                MatchingAuditEventRecord(
                    id=str(uuid4()),
                    match_id=match.id,
                    actor_id=match.actor_id,
                    action="MATCHING_STARTED",
                    audit_metadata=audit_metadata,
                )
            )
            session.add(
                MatchingAuditEventRecord(
                    id=str(uuid4()),
                    match_id=match.id,
                    actor_id=match.actor_id,
                    action="MATCHING_COMPLETED",
                    audit_metadata=audit_metadata,
                )
            )
        return match.model_copy(deep=True)

    async def get(self, match_id: str) -> PreliminaryMatch | None:
        async with self._session_factory() as session:
            record = await session.get(PreliminaryMatchRecord, match_id)
            if record is None:
                return None
            allocations = list(
                (
                    await session.scalars(
                        select(MatchEvidenceAllocationRecord).where(
                            MatchEvidenceAllocationRecord.match_id == match_id
                        )
                    )
                ).all()
            )
            return PreliminaryMatch.model_validate(
                {
                    "id": record.id,
                    "cv_profile_id": record.cv_profile_id,
                    "cv_profile_version": record.cv_profile_version,
                    "jd_profile_id": record.jd_profile_id,
                    "jd_profile_version": record.jd_profile_version,
                    "role_profile_id": record.role_profile_id,
                    "role_profile_version": record.role_profile_version,
                    "rule_set_version": record.rule_set_version,
                    "policy_version": record.policy_version,
                    "actor_id": record.actor_id,
                    "correlation_id": record.correlation_id,
                    "status": record.status,
                    "criterion_results": record.criterion_results,
                    "preliminary_skill_gaps": record.preliminary_skill_gaps,
                    "evidence_allocations": [
                        {"evidence_id": item.evidence_id, "requirement_id": item.requirement_id}
                        for item in allocations
                    ],
                    "version": record.version,
                    "approved_gap_ids": record.approved_gap_ids,
                    "reviewed_by": record.reviewed_by,
                    "reviewed_at": record.reviewed_at,
                },
                strict=False,
            )

    async def review(
        self,
        match_id: str,
        *,
        reviewer_id: UUID,
        approved_gap_ids: list[str],
        expected_version: int,
        reviewed_at: datetime,
    ) -> PreliminaryMatch:
        async with self._session_factory() as session, session.begin():
            record = await session.scalar(
                select(PreliminaryMatchRecord)
                .where(PreliminaryMatchRecord.id == match_id)
                .with_for_update()
            )
            if record is None:
                raise KeyError(match_id)
            if record.version != expected_version:
                raise ValueError("version_conflict")
            if record.status != PreliminaryMatchStatus.COMPLETED.value:
                raise ValueError("invalid_review_transition")
            gap_ids = {str(item["requirement_id"]) for item in record.preliminary_skill_gaps}
            if any(gap_id not in gap_ids for gap_id in approved_gap_ids):
                raise ValueError("unknown_gap")
            record.status = PreliminaryMatchStatus.REVIEWED.value
            record.version += 1
            record.approved_gap_ids = list(dict.fromkeys(approved_gap_ids))
            record.reviewed_by = reviewer_id
            record.reviewed_at = reviewed_at
            session.add(
                MatchingAuditEventRecord(
                    id=str(uuid4()),
                    match_id=match_id,
                    actor_id=reviewer_id,
                    action="MATCHING_REVIEWED",
                    audit_metadata={
                        "match_version": record.version,
                        "approved_gap_count": len(record.approved_gap_ids),
                    },
                )
            )
            await session.flush()
        reviewed = await self.get(match_id)
        if reviewed is None:
            raise RuntimeError("reviewed_match_missing")
        return reviewed

    async def record_rejected_input(
        self,
        *,
        actor_id: UUID,
        correlation_id: str,
        cv_profile_id: str,
        role_profile_id: str,
        action: str,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                MatchingAuditEventRecord(
                    id=str(uuid4()),
                    match_id=None,
                    actor_id=actor_id,
                    action=action,
                    audit_metadata={
                        "cv_profile_id": cv_profile_id,
                        "role_profile_id": role_profile_id,
                        "correlation_id": correlation_id,
                    },
                )
            )

    @staticmethod
    def _safe_audit_metadata(match: PreliminaryMatch) -> dict[str, object]:
        return {
            "cv_profile_id": match.cv_profile_id,
            "cv_profile_version": match.cv_profile_version,
            "role_profile_id": match.role_profile_id,
            "role_profile_version": match.role_profile_version,
            "rule_set_version": match.rule_set_version,
            "policy_version": match.policy_version,
            "correlation_id": match.correlation_id,
        }
