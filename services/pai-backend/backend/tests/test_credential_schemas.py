from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.credential.schemas import (
    CredentialPolicy,
    CredentialPolicyStatus,
    CredentialType,
    EligibilityStatus,
)


def test_policy_rejects_unknown_credential_type() -> None:
    with pytest.raises(ValidationError):
        CredentialPolicy(
            policy_id="python-credential",
            version="v1",
            credential_type="unverified-course",
            status=CredentialPolicyStatus.ACTIVE,
            organization_id=uuid4(),
            valid_for_days=365,
            allow_duplicate_active=False,
            requires_distinct_approver_and_issuer=True,
        )


def test_policy_requires_positive_validity_window() -> None:
    with pytest.raises(ValidationError):
        CredentialPolicy(
            policy_id="python-credential",
            version="v1",
            credential_type=CredentialType.COMPETENCY,
            status=CredentialPolicyStatus.ACTIVE,
            organization_id=uuid4(),
            valid_for_days=0,
            allow_duplicate_active=False,
            requires_distinct_approver_and_issuer=True,
        )


def test_eligibility_status_keeps_not_evaluable_distinct_from_ineligible() -> None:
    assert EligibilityStatus.NOT_EVALUABLE != EligibilityStatus.INELIGIBLE
