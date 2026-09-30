from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.authorization.schemas import ActorContext, Role
from app.integration.actor_context import (
    SignedActorContextVerifier,
    actor_context_headers,
)
from app.integration.learning_path_api import _error, _projection
from app.learning.errors import LearningPathValidationError
from app.learning.repository import InMemoryLearningPathRepository
from app.learning.service import LearningPathService
from tests.test_learning_capability_analysis import AnalysisRepository, analysis
from tests.test_learning_eligibility import ORG_ID, SUBJECT_ID, target_profile


def test_signed_actor_context_resolves_actor_and_rejects_expired_context() -> None:
    private_key = Ed25519PrivateKey.generate()
    now = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
    headers = actor_context_headers(
        private_key=private_key,
        key_id="lms-key-1",
        actor_id=SUBJECT_ID,
        organization_id=ORG_ID,
        issued_at=now,
        expires_at=now + timedelta(seconds=30),
        nonce="nonce-1",
    )

    verifier = SignedActorContextVerifier(
        public_keys={"lms-key-1": private_key.public_key()},
        actor_resolver=lambda actor_id, organization_id: _actor(actor_id, organization_id),
        now=lambda: now,
    )

    resolved = verifier.verify(headers)
    assert resolved.actor_id == SUBJECT_ID
    assert resolved.organization_id == ORG_ID
    assert resolved.authentication_method == "signed_actor_context"

    expired = actor_context_headers(
        private_key=private_key,
        key_id="lms-key-1",
        actor_id=SUBJECT_ID,
        organization_id=ORG_ID,
        issued_at=now - timedelta(seconds=30),
        expires_at=now - timedelta(seconds=1),
        nonce="nonce-expired",
    )
    with pytest.raises(ValueError, match="ACTOR_CONTEXT_EXPIRED"):
        verifier.verify(expired)


def _actor(actor_id: UUID, organization_id: UUID) -> ActorContext:
    return ActorContext(
        actor_id=actor_id,
        organization_id=organization_id,
        roles=frozenset({Role.LEARNER}),
    )


def test_learning_path_target_level_error_is_publicly_stable() -> None:
    error = _error(LearningPathValidationError("capability_analysis_target_level_required"))

    assert error.status_code == 409
    assert error.code == "learning_path_target_level_required"


@pytest.mark.asyncio
async def test_learning_path_integration_resolves_candidate_and_is_idempotent() -> None:
    paths = InMemoryLearningPathRepository()
    profile = target_profile().model_copy(
        update={"requirements": [target_profile().requirements[0].model_copy(update={"target_level": "1"})]}
    )

    class Roles:
        async def get_version(self, *_args):
            return profile

    service = LearningPathService(
        competency_records=None,  # type: ignore[arg-type]
        role_profiles=Roles(),  # type: ignore[arg-type]
        matches=None,  # type: ignore[arg-type]
        paths=paths,
        capability_analyses=AnalysisRepository(analysis()),
    )
    first = await service.create_for_candidate(
        actor=_actor(SUBJECT_ID, ORG_ID),
        candidate_id=analysis().candidate_id,
        development_goal="Become job-ready",
        target_completion_date=date(2026, 12, 1),
        idempotency_key="lp-key-1",
    )
    second = await service.create_for_candidate(
        actor=_actor(SUBJECT_ID, ORG_ID),
        candidate_id=analysis().candidate_id,
        development_goal="Become job-ready",
        target_completion_date=date(2026, 12, 1),
        idempotency_key="lp-key-1",
    )
    assert second.id == first.id
    assert len(paths.paths) == 1
    public = _projection(first).model_dump()
    assert "cv_profile_id" not in str(public)
    assert "organization_id" not in public
    assert public["candidate_reference"] == analysis().candidate_id
