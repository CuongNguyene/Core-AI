from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.assessment.schemas import (
    AssessmentTask,
    AssessmentTaskType,
    AssessmentTemplate,
    Rubric,
    RubricCriterion,
)
from app.authorization.fixtures import ADMIN_ID, LEARNER_ID, ORG_PAI_ID, SME_ID
from app.authorization.repository import InMemoryDelegationRepository, InMemorySubjectRepository
from app.main import create_app


async def client_with_overrides() -> AsyncIterator[tuple[AsyncClient, FastAPI]]:
    app = create_app()
    app.state.subject_repository = InMemorySubjectRepository.fixture()
    app.state.delegation_repository = InMemoryDelegationRepository([])
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver"), app


def template() -> AssessmentTemplate:
    return AssessmentTemplate(
        id=uuid4(),
        version="1.0",
        competency_id="python",
        rubric=Rubric(
            id=uuid4(),
            version="1.0",
            criteria=[RubricCriterion(id="c", description="Correctness", max_score=5)],
        ),
        policy_version="assessment-v1",
        risk_classification="low_risk",
        validity_days=365,
        reassessment_lead_days=30,
        tasks=[
            AssessmentTask(
                id="task-1", task_type=AssessmentTaskType.QUIZ, prompt_reference="fixture:task-1"
            )
        ],
    )


@pytest.mark.asyncio
async def test_client_role_header_cannot_make_learner_an_sme() -> None:
    async for client, _app in client_with_overrides():
        async with client:
            response = await client.post(
                "/assessment-templates",
                headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
                json=template().model_dump(mode="json"),
            )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "assessment_template_forbidden"


@pytest.mark.asyncio
async def test_admin_can_create_delegation_without_client_role_header() -> None:
    async for client, _app in client_with_overrides():
        async with client:
            response = await client.post(
                "/delegations",
                headers={"X-PAI-Actor-ID": str(ADMIN_ID)},
                json={
                    "user_id": str(LEARNER_ID),
                    "organization_id": str(ORG_PAI_ID),
                    "competency_scope": ["python"],
                    "valid_from": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
                    "valid_until": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                    "reason": "fixture",
                },
            )
    assert response.status_code == 201, response.text
    assert response.json()["granted_by"] == str(ADMIN_ID)
    assert "role" not in response.json()


@pytest.mark.asyncio
async def test_admin_can_delegate_credential_issue_for_a_policy_scope() -> None:
    async for client, _app in client_with_overrides():
        async with client:
            response = await client.post(
                "/delegations",
                headers={"X-PAI-Actor-ID": str(ADMIN_ID)},
                json={
                    "user_id": str(SME_ID),
                    "organization_id": str(ORG_PAI_ID),
                    "permission": "credential.issue",
                    "competency_scope": ["python-credential-v1"],
                    "valid_from": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
                    "valid_until": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                    "reason": "fixture",
                },
            )
    assert response.status_code == 201, response.text
    assert response.json()["permission"] == "credential.issue"
