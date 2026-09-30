from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.semantic_policy.models import SemanticPolicyAuditEventRecord, SemanticPolicyRecord
from app.semantic_policy.schemas import SemanticPolicy, SemanticPolicyStatus


class SemanticPolicyRepository(Protocol):
    async def save(self, policy: SemanticPolicy) -> SemanticPolicy: ...

    async def get(self, policy_id: str, version: str) -> SemanticPolicy | None: ...

    async def has_policy_id(self, policy_id: str) -> bool: ...

    async def transition(
        self, policy_id: str, version: str, status: SemanticPolicyStatus
    ) -> SemanticPolicy: ...

    async def append_audit(
        self, *, action: str, policy_id: str, policy_version: str, actor_id: str
    ) -> None: ...


class InMemorySemanticPolicyRepository:
    def __init__(self, policies: list[SemanticPolicy] | None = None) -> None:
        self._policies = {
            (policy.policy_id, policy.version): policy.model_copy(deep=True)
            for policy in policies or []
        }
        self.audit_events: list[dict[str, str]] = []

    async def append_audit(
        self, *, action: str, policy_id: str, policy_version: str, actor_id: str
    ) -> None:
        self.audit_events.append(
            {
                "action": action,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "actor_id": actor_id,
            }
        )

    async def save(self, policy: SemanticPolicy) -> SemanticPolicy:
        key = (policy.policy_id, policy.version)
        if key in self._policies:
            raise ValueError("Semantic policy versions are immutable")
        self._policies[key] = policy.model_copy(deep=True)
        return policy.model_copy(deep=True)

    async def get(self, policy_id: str, version: str) -> SemanticPolicy | None:
        policy = self._policies.get((policy_id, version))
        return policy.model_copy(deep=True) if policy is not None else None

    async def has_policy_id(self, policy_id: str) -> bool:
        return any(item_id == policy_id for item_id, _ in self._policies)

    async def transition(
        self, policy_id: str, version: str, status: SemanticPolicyStatus
    ) -> SemanticPolicy:
        current = self._policies.get((policy_id, version))
        if current is None:
            raise KeyError((policy_id, version))
        if current.status is SemanticPolicyStatus.DRAFT and status is SemanticPolicyStatus.ACTIVE:
            updated = current.model_copy(
                update={"status": status, "activated_at": datetime.now(UTC)}
            )
        elif (
            current.status is SemanticPolicyStatus.ACTIVE
            and status is SemanticPolicyStatus.DEPRECATED
        ):
            updated = current.model_copy(
                update={"status": status, "deprecated_at": datetime.now(UTC)}
            )
        else:
            raise ValueError("Invalid semantic policy lifecycle transition")
        self._policies[(policy_id, version)] = updated
        return updated.model_copy(deep=True)


class SqlAlchemySemanticPolicyRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_audit(
        self, *, action: str, policy_id: str, policy_version: str, actor_id: str
    ) -> None:
        from datetime import datetime

        async with self._session_factory() as session, session.begin():
            session.add(
                SemanticPolicyAuditEventRecord(
                    id=uuid4().hex,
                    action=action,
                    policy_id=policy_id,
                    policy_version=policy_version,
                    actor_id=actor_id,
                    audit_metadata={
                        "policy_id": policy_id,
                        "policy_version": policy_version,
                        "actor_id": actor_id,
                    },
                    created_at=datetime.now(UTC),
                )
            )

    async def save(self, policy: SemanticPolicy) -> SemanticPolicy:
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(SemanticPolicyRecord).where(
                    SemanticPolicyRecord.policy_id == policy.policy_id,
                    SemanticPolicyRecord.version == policy.version,
                )
            )
            if existing is not None:
                raise ValueError("Semantic policy versions are immutable")
            session.add(
                SemanticPolicyRecord(
                    record_id=f"{policy.policy_id}:{policy.version}:{uuid4().hex}",
                    policy_id=policy.policy_id,
                    version=policy.version,
                    core_version=policy.core_version,
                    status=policy.status.value,
                    domain_pack_id=policy.domain_pack_id,
                    domain_pack_version=policy.domain_pack_version,
                    domain_pack_checksum=policy.domain_pack_checksum,
                    description=policy.description,
                    created_by=policy.created_by,
                    reviewed_by=policy.reviewed_by,
                    created_at=policy.created_at,
                    activated_at=policy.activated_at,
                    deprecated_at=policy.deprecated_at,
                )
            )
        return policy.model_copy(deep=True)

    async def get(self, policy_id: str, version: str) -> SemanticPolicy | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(SemanticPolicyRecord).where(
                    SemanticPolicyRecord.policy_id == policy_id,
                    SemanticPolicyRecord.version == version,
                )
            )
        return self._to_schema(record) if record is not None else None

    async def has_policy_id(self, policy_id: str) -> bool:
        async with self._session_factory() as session:
            return (
                await session.scalar(
                    select(SemanticPolicyRecord.policy_id)
                    .where(SemanticPolicyRecord.policy_id == policy_id)
                    .limit(1)
                )
                is not None
            )

    async def transition(
        self, policy_id: str, version: str, status: SemanticPolicyStatus
    ) -> SemanticPolicy:
        async with self._session_factory() as session, session.begin():
            record = await session.scalar(
                select(SemanticPolicyRecord).where(
                    SemanticPolicyRecord.policy_id == policy_id,
                    SemanticPolicyRecord.version == version,
                ).with_for_update()
            )
            if record is None:
                raise KeyError((policy_id, version))
            current = self._to_schema(record)
            if current.status is SemanticPolicyStatus.DRAFT and status is SemanticPolicyStatus.ACTIVE:
                record.status = status.value
                record.activated_at = datetime.now(UTC)
            elif (
                current.status is SemanticPolicyStatus.ACTIVE
                and status is SemanticPolicyStatus.DEPRECATED
            ):
                record.status = status.value
                record.deprecated_at = datetime.now(UTC)
            else:
                raise ValueError("Invalid semantic policy lifecycle transition")
            return self._to_schema(record)

    @staticmethod
    def _to_schema(record: SemanticPolicyRecord) -> SemanticPolicy:
        return SemanticPolicy(
            policy_id=record.policy_id,
            version=record.version,
            core_version=record.core_version,
            status=SemanticPolicyStatus(record.status),
            domain_pack_id=record.domain_pack_id,
            domain_pack_version=record.domain_pack_version,
            domain_pack_checksum=record.domain_pack_checksum,
            description=record.description,
            created_by=record.created_by,
            reviewed_by=record.reviewed_by,
            created_at=record.created_at,
            activated_at=record.activated_at,
            deprecated_at=record.deprecated_at,
        )
