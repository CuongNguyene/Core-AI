from uuid import UUID

from app.credential.schemas import CredentialPolicy, CredentialPolicyStatus, CredentialType


def competency_policy_fixture(organization_id: UUID) -> CredentialPolicy:
    return CredentialPolicy(
        policy_id="competency-default",
        version="v1",
        credential_type=CredentialType.COMPETENCY,
        status=CredentialPolicyStatus.ACTIVE,
        organization_id=organization_id,
        valid_for_days=365,
        allow_duplicate_active=False,
        requires_distinct_approver_and_issuer=True,
    )
