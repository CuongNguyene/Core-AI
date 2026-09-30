from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.credential.models import (
    CredentialAuditEventRecord,
    CredentialPolicyRecord,
    CredentialRecord,
    CredentialRequestRecord,
)
from app.credential.schemas import (
    Credential,
    CredentialPolicy,
    CredentialRequest,
    CredentialRequestStatus,
    CredentialStatus,
    EligibilityDecision,
    EligibilityStatus,
)


class InMemoryCredentialRepository:
    def __init__(self, policies: list[CredentialPolicy] | None = None) -> None:
        self.policies = {(item.policy_id, item.version): item for item in policies or []}
        self.requests: dict[UUID, CredentialRequest] = {}
        self.credentials: dict[UUID, Credential] = {}
        self.audit_events: list[dict[str, object]] = []

    async def get_active_policy(self, policy_id: str, version: str) -> CredentialPolicy | None:
        item = self.policies.get((policy_id, version))
        return item if item and item.status.value == "active" else None

    async def create_request(
        self,
        *,
        policy: CredentialPolicy,
        subject_id: UUID,
        source_reference_id: str | None,
        evaluation: EligibilityDecision,
        requested_by: UUID,
        correlation_id: UUID,
    ) -> CredentialRequest:
        if evaluation.status is not EligibilityStatus.ELIGIBLE:
            raise ValueError("credential_not_eligible")
        request = CredentialRequest(
            id=uuid4(),
            policy_id=policy.policy_id,
            policy_version=policy.version,
            credential_type=policy.credential_type,
            subject_id=subject_id,
            organization_id=policy.organization_id,
            source_reference_id=source_reference_id,
            eligibility=evaluation,
            status=CredentialRequestStatus.PENDING_APPROVAL,
            requested_by=requested_by,
            version=1,
            correlation_id=correlation_id,
        )
        self.requests[request.id] = request
        self.audit_events.append(
            {"action": "CREDENTIAL_EVALUATION_ELIGIBLE", "request_id": request.id}
        )
        return request

    async def get_request(self, request_id: UUID) -> CredentialRequest | None:
        return self.requests.get(request_id)

    async def transition_request(
        self,
        request_id: UUID,
        *,
        expected_version: int,
        target: CredentialRequestStatus,
        actor_id: UUID,
    ) -> CredentialRequest:
        current = self.requests.get(request_id)
        if current is None:
            raise KeyError(request_id)
        if current.version != expected_version:
            raise ValueError("version_conflict")
        allowed = {
            CredentialRequestStatus.PENDING_APPROVAL: {
                CredentialRequestStatus.APPROVED,
                CredentialRequestStatus.REJECTED,
            },
            CredentialRequestStatus.APPROVED: {CredentialRequestStatus.ISSUED},
        }
        if target not in allowed.get(current.status, set()):
            raise ValueError("invalid_transition")
        update: dict[str, object] = {"status": target, "version": current.version + 1}
        if target is CredentialRequestStatus.APPROVED:
            update["approver_id"] = actor_id
        if target is CredentialRequestStatus.ISSUED:
            update["issuer_id"] = actor_id
        updated = current.model_copy(update=update)
        self.requests[request_id] = updated
        self.audit_events.append(
            {"action": f"CREDENTIAL_{target.value.upper()}", "request_id": request_id}
        )
        return updated

    async def find_active_duplicate(self, *, subject_id: UUID, policy_id: str) -> bool:
        return any(
            item.subject_id == subject_id
            and item.policy_id == policy_id
            and item.status is CredentialStatus.ISSUED
            for item in self.credentials.values()
        )

    async def issue(
        self, request: CredentialRequest, *, actor_id: UUID, valid_for_days: int
    ) -> Credential:
        credential = Credential(
            id=uuid4(),
            request_id=request.id,
            policy_id=request.policy_id,
            policy_version=request.policy_version,
            credential_type=request.credential_type,
            subject_id=request.subject_id,
            organization_id=request.organization_id,
            status=CredentialStatus.ISSUED,
            issued_at=datetime.now(UTC),
            valid_until=datetime.now(UTC) + timedelta(days=valid_for_days),
            issued_by=actor_id,
            version=1,
        )
        self.credentials[credential.id] = credential
        self.audit_events.append({"action": "CREDENTIAL_ISSUED", "credential_id": credential.id})
        return credential

    async def issue_approved(
        self,
        request_id: UUID,
        *,
        expected_version: int,
        actor_id: UUID,
        valid_for_days: int,
        allow_duplicate_active: bool,
    ) -> Credential:
        request = self.requests.get(request_id)
        if request is None:
            raise KeyError(request_id)
        if request.version != expected_version:
            raise ValueError("version_conflict")
        if request.status is not CredentialRequestStatus.APPROVED:
            raise ValueError("credential_approval_required")
        if not allow_duplicate_active and await self.find_active_duplicate(
            subject_id=request.subject_id, policy_id=request.policy_id
        ):
            raise ValueError("active_credential_duplicate")
        issued_at = datetime.now(UTC)
        credential = Credential(
            id=uuid4(),
            request_id=request.id,
            policy_id=request.policy_id,
            policy_version=request.policy_version,
            credential_type=request.credential_type,
            subject_id=request.subject_id,
            organization_id=request.organization_id,
            status=CredentialStatus.ISSUED,
            issued_at=issued_at,
            valid_until=issued_at + timedelta(days=valid_for_days),
            issued_by=actor_id,
            version=1,
        )
        self.credentials[credential.id] = credential
        self.requests[request_id] = request.model_copy(
            update={
                "status": CredentialRequestStatus.ISSUED,
                "version": request.version + 1,
                "issuer_id": actor_id,
            }
        )
        self.audit_events.extend(
            [
                {
                    "action": "CREDENTIAL_ISSUED",
                    "request_id": request.id,
                    "credential_id": credential.id,
                },
                {
                    "action": "CREDENTIAL_REQUEST_ISSUED",
                    "request_id": request.id,
                    "new_version": request.version + 1,
                },
            ]
        )
        return credential

    async def get_credential(self, credential_id: UUID) -> Credential | None:
        return self.credentials.get(credential_id)

    async def revoke_or_expire(
        self, credential_id: UUID, *, target: CredentialStatus, actor_id: UUID
    ) -> Credential:
        current = self.credentials.get(credential_id)
        if current is None:
            raise KeyError(credential_id)
        if target is CredentialStatus.EXPIRED and current.valid_until > datetime.now(UTC):
            raise ValueError("credential_not_expired")
        if current.status is not CredentialStatus.ISSUED:
            raise ValueError("credential_transition_invalid")
        updated = current.model_copy(update={"status": target, "version": current.version + 1})
        self.credentials[credential_id] = updated
        self.audit_events.append(
            {"action": f"CREDENTIAL_{target.value.upper()}", "credential_id": credential_id}
        )
        return updated


class SqlAlchemyCredentialRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_active_policy(self, policy_id: str, version: str) -> CredentialPolicy | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CredentialPolicyRecord).where(
                    CredentialPolicyRecord.policy_id == policy_id,
                    CredentialPolicyRecord.version == version,
                    CredentialPolicyRecord.status == "active",
                )
            )
            if record is None:
                return None
            return CredentialPolicy(
                policy_id=record.policy_id,
                version=record.version,
                credential_type=record.credential_type,
                status=record.status,
                organization_id=record.organization_id,
                valid_for_days=record.valid_for_days,
                allow_duplicate_active=record.allow_duplicate_active,
                requires_distinct_approver_and_issuer=record.requires_distinct_approver_and_issuer,
                competency_id=record.competency_id,
                minimum_level=record.minimum_level,
            )

    async def create_request(
        self,
        *,
        policy: CredentialPolicy,
        subject_id: UUID,
        source_reference_id: str | None,
        evaluation: EligibilityDecision,
        requested_by: UUID,
        correlation_id: UUID,
    ) -> CredentialRequest:
        if evaluation.status is not EligibilityStatus.ELIGIBLE:
            raise ValueError("credential_not_eligible")
        request = CredentialRequest(
            id=uuid4(),
            policy_id=policy.policy_id,
            policy_version=policy.version,
            credential_type=policy.credential_type,
            subject_id=subject_id,
            organization_id=policy.organization_id,
            source_reference_id=source_reference_id,
            eligibility=evaluation,
            status=CredentialRequestStatus.PENDING_APPROVAL,
            requested_by=requested_by,
            version=1,
            correlation_id=correlation_id,
        )
        async with self._session_factory() as session, session.begin():
            session.add(
                CredentialRequestRecord(
                    id=request.id,
                    policy_id=request.policy_id,
                    policy_version=request.policy_version,
                    credential_type=request.credential_type.value,
                    subject_id=request.subject_id,
                    organization_id=request.organization_id,
                    source_reference_id=request.source_reference_id,
                    eligibility=request.eligibility.model_dump(mode="json"),
                    status=request.status.value,
                    requested_by=request.requested_by,
                    version=request.version,
                    correlation_id=request.correlation_id,
                )
            )
        return request

    async def get_request(self, request_id: UUID) -> CredentialRequest | None:
        async with self._session_factory() as session:
            record = await session.get(CredentialRequestRecord, request_id)
            if record is None:
                return None
            return CredentialRequest(
                id=record.id,
                policy_id=record.policy_id,
                policy_version=record.policy_version,
                credential_type=record.credential_type,
                subject_id=record.subject_id,
                organization_id=record.organization_id,
                source_reference_id=record.source_reference_id,
                eligibility=EligibilityDecision.model_validate(record.eligibility),
                status=record.status,
                requested_by=record.requested_by,
                version=record.version,
                correlation_id=record.correlation_id,
                approver_id=record.approver_id,
                issuer_id=record.issuer_id,
            )

    async def transition_request(
        self,
        request_id: UUID,
        *,
        expected_version: int,
        target: CredentialRequestStatus,
        actor_id: UUID,
    ) -> CredentialRequest:
        async with self._session_factory() as session, session.begin():
            record = await session.scalar(
                select(CredentialRequestRecord)
                .where(CredentialRequestRecord.id == request_id)
                .with_for_update()
            )
            if record is None:
                raise KeyError(request_id)
            if record.version != expected_version:
                raise ValueError("version_conflict")
            current = CredentialRequestStatus(record.status)
            allowed = {
                CredentialRequestStatus.PENDING_APPROVAL: {
                    CredentialRequestStatus.APPROVED,
                    CredentialRequestStatus.REJECTED,
                },
                CredentialRequestStatus.APPROVED: {CredentialRequestStatus.ISSUED},
            }
            if target not in allowed.get(current, set()):
                raise ValueError("invalid_transition")
            record.status = target.value
            record.version += 1
            if target is CredentialRequestStatus.APPROVED:
                record.approver_id = actor_id
            if target is CredentialRequestStatus.ISSUED:
                record.issuer_id = actor_id
            session.add(
                CredentialAuditEventRecord(
                    id=uuid4(),
                    request_id=request_id,
                    actor_id=actor_id,
                    action=f"CREDENTIAL_{target.value.upper()}",
                    audit_metadata={
                        "previous_status": current.value,
                        "new_status": target.value,
                        "expected_version": expected_version,
                        "new_version": record.version,
                    },
                )
            )
            await session.flush()
            updated = await self.get_request(request_id)
            if updated is None:
                raise RuntimeError("credential_request_missing_after_transition")
            return updated

    async def find_active_duplicate(self, *, subject_id: UUID, policy_id: str) -> bool:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(CredentialRecord).where(
                    CredentialRecord.subject_id == subject_id,
                    CredentialRecord.policy_id == policy_id,
                    CredentialRecord.status == "issued",
                )
            )
            return record is not None

    async def issue(
        self, request: CredentialRequest, *, actor_id: UUID, valid_for_days: int
    ) -> Credential:
        from datetime import UTC, datetime, timedelta

        issued_at = datetime.now(UTC)
        credential = Credential(
            id=uuid4(),
            request_id=request.id,
            policy_id=request.policy_id,
            policy_version=request.policy_version,
            credential_type=request.credential_type,
            subject_id=request.subject_id,
            organization_id=request.organization_id,
            status=CredentialStatus.ISSUED,
            issued_at=issued_at,
            valid_until=issued_at + timedelta(days=valid_for_days),
            issued_by=actor_id,
            version=1,
        )
        async with self._session_factory() as session, session.begin():
            session.add(
                CredentialRecord(
                    id=credential.id,
                    request_id=credential.request_id,
                    policy_id=credential.policy_id,
                    policy_version=credential.policy_version,
                    credential_type=credential.credential_type.value,
                    subject_id=credential.subject_id,
                    organization_id=credential.organization_id,
                    status=credential.status.value,
                    issued_at=credential.issued_at,
                    valid_until=credential.valid_until,
                    issued_by=credential.issued_by,
                    version=credential.version,
                )
            )
            session.add(
                CredentialAuditEventRecord(
                    id=uuid4(),
                    request_id=request.id,
                    credential_id=credential.id,
                    actor_id=actor_id,
                    action="CREDENTIAL_ISSUED",
                    audit_metadata={
                        "policy_id": request.policy_id,
                        "policy_version": request.policy_version,
                    },
                )
            )
        return credential

    async def issue_approved(
        self,
        request_id: UUID,
        *,
        expected_version: int,
        actor_id: UUID,
        valid_for_days: int,
        allow_duplicate_active: bool,
    ) -> Credential:
        from datetime import UTC, datetime, timedelta

        async with self._session_factory() as session, session.begin():
            request = await session.scalar(
                select(CredentialRequestRecord)
                .where(CredentialRequestRecord.id == request_id)
                .with_for_update()
            )
            if request is None:
                raise KeyError(request_id)
            if request.version != expected_version:
                raise ValueError("version_conflict")
            if request.status != CredentialRequestStatus.APPROVED.value:
                raise ValueError("credential_approval_required")
            if not allow_duplicate_active:
                duplicate = await session.scalar(
                    select(CredentialRecord).where(
                        CredentialRecord.subject_id == request.subject_id,
                        CredentialRecord.policy_id == request.policy_id,
                        CredentialRecord.status == CredentialStatus.ISSUED.value,
                    )
                )
                if duplicate is not None:
                    raise ValueError("active_credential_duplicate")
            issued_at = datetime.now(UTC)
            credential = Credential(
                id=uuid4(),
                request_id=request.id,
                policy_id=request.policy_id,
                policy_version=request.policy_version,
                credential_type=request.credential_type,
                subject_id=request.subject_id,
                organization_id=request.organization_id,
                status=CredentialStatus.ISSUED,
                issued_at=issued_at,
                valid_until=issued_at + timedelta(days=valid_for_days),
                issued_by=actor_id,
                version=1,
            )
            request.status = CredentialRequestStatus.ISSUED.value
            request.version += 1
            request.issuer_id = actor_id
            session.add(
                CredentialRecord(
                    id=credential.id,
                    request_id=credential.request_id,
                    policy_id=credential.policy_id,
                    policy_version=credential.policy_version,
                    credential_type=credential.credential_type.value,
                    subject_id=credential.subject_id,
                    organization_id=credential.organization_id,
                    status=credential.status.value,
                    issued_at=credential.issued_at,
                    valid_until=credential.valid_until,
                    issued_by=credential.issued_by,
                    version=credential.version,
                )
            )
            session.add_all(
                [
                    CredentialAuditEventRecord(
                        id=uuid4(),
                        request_id=request.id,
                        credential_id=credential.id,
                        actor_id=actor_id,
                        action="CREDENTIAL_ISSUED",
                        audit_metadata={
                            "policy_id": request.policy_id,
                            "policy_version": request.policy_version,
                        },
                    ),
                    CredentialAuditEventRecord(
                        id=uuid4(),
                        request_id=request.id,
                        actor_id=actor_id,
                        action="CREDENTIAL_REQUEST_ISSUED",
                        audit_metadata={
                            "expected_version": expected_version,
                            "new_version": request.version,
                        },
                    ),
                ]
            )
            await session.flush()
            return credential

    async def get_credential(self, credential_id: UUID) -> Credential | None:
        async with self._session_factory() as session:
            record = await session.get(CredentialRecord, credential_id)
            if record is None:
                return None
            return Credential(
                id=record.id,
                request_id=record.request_id,
                policy_id=record.policy_id,
                policy_version=record.policy_version,
                credential_type=record.credential_type,
                subject_id=record.subject_id,
                organization_id=record.organization_id,
                status=record.status,
                issued_at=record.issued_at,
                valid_until=record.valid_until,
                issued_by=record.issued_by,
                version=record.version,
            )

    async def revoke_or_expire(
        self, credential_id: UUID, *, target: CredentialStatus, actor_id: UUID
    ) -> Credential:
        from datetime import UTC, datetime

        async with self._session_factory() as session, session.begin():
            record = await session.scalar(
                select(CredentialRecord)
                .where(CredentialRecord.id == credential_id)
                .with_for_update()
            )
            if record is None:
                raise KeyError(credential_id)
            if record.status != CredentialStatus.ISSUED.value:
                raise ValueError("credential_transition_invalid")
            if target is CredentialStatus.EXPIRED and record.valid_until > datetime.now(UTC):
                raise ValueError("credential_not_expired")
            expected_version = record.version
            record.status = target.value
            record.version += 1
            session.add(
                CredentialAuditEventRecord(
                    id=uuid4(),
                    credential_id=credential_id,
                    actor_id=actor_id,
                    action=f"CREDENTIAL_{target.value.upper()}",
                    audit_metadata={
                        "previous_status": CredentialStatus.ISSUED.value,
                        "new_status": target.value,
                        "expected_version": expected_version,
                        "new_version": record.version,
                    },
                )
            )
            await session.flush()
            return Credential(
                id=record.id,
                request_id=record.request_id,
                policy_id=record.policy_id,
                policy_version=record.policy_version,
                credential_type=record.credential_type,
                subject_id=record.subject_id,
                organization_id=record.organization_id,
                status=record.status,
                issued_at=record.issued_at,
                valid_until=record.valid_until,
                issued_by=record.issued_by,
                version=record.version,
            )
