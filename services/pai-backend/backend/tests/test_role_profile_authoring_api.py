from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.authorization.fixtures import LEARNER_ID, ORG_PAI_ID, REVIEWER_ID
from app.authorization.repository import InMemorySubjectRepository
from app.main import create_app
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleProfileSemanticPolicy,
    RoleRequirement,
)
from app.role_profile_authoring.schemas import (
    ApprovalEligibility,
    QualityFindingSeverity,
    QualityGateResult,
    RequirementFinding,
    RoleProfileDraft,
    RoleProfileDraftStatus,
    SummaryFinding,
)
from app.role_profile_authoring.service import RoleProfileAuthoringService


def draft() -> RoleProfileDraft:
    return RoleProfileDraft(
        id="draft-api-1",
        source_jd_profile_id="jd-accepted",
        source_jd_profile_version=1,
        owner_actor_id=REVIEWER_ID,
        organization_id=ORG_PAI_ID,
        version=1,
        status=RoleProfileDraftStatus.DRAFT,
        requirements=[],
        quality_gate=QualityGateResult(
            passed=False,
            summary_findings=[
                SummaryFinding(
                    code="legacy_missing_modality",
                    severity=QualityFindingSeverity.WARNING,
                    affected_requirement_count=1,
                    message="Modality requires reviewer authoring.",
                )
            ],
        ),
        approval_eligibility=ApprovalEligibility(
            can_create_draft=True,
            can_approve_provisional=True,
            can_approve_active=False,
        ),
        authoring_findings=[
            RequirementFinding(
                requirement_id="jd-skill-1-python",
                code="legacy_missing_modality",
                severity=QualityFindingSeverity.WARNING,
                field="modality",
                message="Modality requires reviewer authoring.",
            )
        ],
        correlation_id="api-run-1",
    )


class FakeRepository:
    def __init__(self) -> None:
        self.item = draft()

    async def create_from_jd(
        self,
        source_jd_profile_id: str,
        actor_id: UUID,
        organization_id: UUID,
        correlation_id: str,
        role_id: UUID | None = None,
        role_jd_version_id: UUID | None = None,
    ) -> RoleProfileDraft:
        return self.item.model_copy(
            update={"role_id": role_id, "role_jd_version_id": role_jd_version_id}
        )

    async def get(self, draft_id: str) -> RoleProfileDraft | None:
        return self.item if draft_id == self.item.id else None

    async def list_for_organization(self, organization_id: UUID) -> list[RoleProfileDraft]:
        return [self.item] if organization_id == self.item.organization_id else []

    async def author(
        self,
        draft_id: str,
        *,
        expected_version: int,
        actor_id: UUID,
        title: str | None,
        requirements: list[RoleRequirement],
    ) -> RoleProfileDraft:
        self.item = self.item.model_copy(
            update={"version": 2, "title": title, "requirements": requirements}
        )
        return self.item

    async def validate(
        self, draft_id: str, *, expected_version: int, actor_id: UUID
    ) -> RoleProfileDraft:
        return self.item

    async def approve(
        self,
        draft_id: str,
        *,
        expected_version: int,
        actor_id: UUID,
        requested_status: object,
        semantic_policy: RoleProfileSemanticPolicy,
    ) -> RoleProfileDraft:
        return self.item


@pytest.fixture
def app() -> FastAPI:
    application = create_app()
    application.state.subject_repository = InMemorySubjectRepository.fixture()
    application.state.role_profile_authoring_service = RoleProfileAuthoringService(FakeRepository())
    return application


@pytest.mark.asyncio
async def test_role_profile_draft_create_requires_reviewer(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/role-profile-drafts",
            headers={"X-PAI-Actor-ID": str(LEARNER_ID)},
            json={"source_jd_profile_id": "jd-accepted", "correlation_id": "api-run-1"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "role_profile_draft_access_denied"


@pytest.mark.asyncio
async def test_reviewer_can_create_role_linked_draft_with_exact_lineage(app: FastAPI) -> None:
    role_id = UUID("3d69b8bf-8cde-438d-87a9-54f4a07ca5ea")
    role_jd_version_id = UUID("e4b7a0ca-2b4d-4939-afce-2a67930ad606")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/role-profile-drafts",
            headers={"X-PAI-Actor-ID": str(REVIEWER_ID)},
            json={
                "source_jd_profile_id": "jd-accepted",
                "correlation_id": "role-linked-api-1",
                "role_id": str(role_id),
                "role_jd_version_id": str(role_jd_version_id),
            },
        )

    assert response.status_code == 201
    assert response.json()["role_id"] == str(role_id)
    assert response.json()["role_jd_version_id"] == str(role_jd_version_id)


@pytest.mark.asyncio
async def test_reviewer_can_list_role_profile_drafts(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/role-profile-drafts",
            headers={"X-PAI-Actor-ID": str(REVIEWER_ID)},
        )

    assert response.status_code == 200
    assert response.json()[0]["id"] == "draft-api-1"


@pytest.mark.asyncio
async def test_reviewer_can_author_full_structured_requirement(app: FastAPI) -> None:
    requirement = {
        "id": "python",
        "criterion_dimension": CriterionDimension.SKILL.value,
        "classification": RequirementClassification.PREFERRED.value,
        "evidence_terms": ["python"],
        "conflicting_terms": [],
        "confidence_threshold": 0.7,
        "assessment_recommendation": "practical_task",
        "rubric_version": "rubric-v1",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.patch(
            "/role-profile-drafts/draft-api-1",
            headers={"X-PAI-Actor-ID": str(REVIEWER_ID)},
            json={"expected_version": 1, "title": "Python Engineer", "requirements": [requirement]},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Python Engineer"


@pytest.mark.asyncio
async def test_reviewer_can_validate_role_profile_draft(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/role-profile-drafts/draft-api-1/validate",
            headers={"X-PAI-Actor-ID": str(REVIEWER_ID)},
            json={"expected_version": 1},
        )

    assert response.status_code == 200
    assert response.json()["id"] == "draft-api-1"


@pytest.mark.asyncio
async def test_get_draft_returns_summary_by_default_and_detail_on_request(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        summary_response = await client.get(
            "/role-profile-drafts/draft-api-1",
            headers={"X-PAI-Actor-ID": str(REVIEWER_ID)},
        )
        detail_response = await client.get(
            "/role-profile-drafts/draft-api-1?include_requirement_findings=true",
            headers={"X-PAI-Actor-ID": str(REVIEWER_ID)},
        )

    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["quality_gate"] == {
        "passed": False,
        "summary_findings": [
            {
                "code": "legacy_missing_modality",
                "severity": "warning",
                "affected_requirement_count": 1,
                "message": "Modality requires reviewer authoring.",
            }
        ],
    }
    assert "authoring_findings" not in summary
    assert summary["approval_eligibility"] == {
        "can_create_draft": True,
        "can_approve_provisional": True,
        "can_approve_active": False,
    }
    assert detail_response.status_code == 200
    assert detail_response.json()["authoring_findings"][0]["requirement_id"] == "jd-skill-1-python"


@pytest.mark.asyncio
async def test_approval_requires_explicit_semantic_policy_without_default_it(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        missing = await client.post(
            "/role-profile-drafts/draft-api-1/approve",
            headers={"X-PAI-Actor-ID": str(REVIEWER_ID)},
            json={"expected_version": 1, "requested_status": "provisional"},
        )
        explicit = await client.post(
            "/role-profile-drafts/draft-api-1/approve",
            headers={"X-PAI-Actor-ID": str(REVIEWER_ID)},
            json={
                "expected_version": 1,
                "requested_status": "provisional",
                "semantic_policy": {
                    "core_version": "semantic-core-v1",
                    "pack_refs": [{"pack_id": "it_ai", "version": "1"}],
                },
            },
        )

    assert missing.status_code == 422
    assert explicit.status_code == 200
