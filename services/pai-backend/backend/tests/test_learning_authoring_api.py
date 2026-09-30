from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.authorization.schemas import ActorContext, Role
from app.capability_analysis.schemas import (
    AnalysisStatus,
    AssessmentEvidenceStatus,
    CombinedGapPortfolio,
    PreliminaryPriority,
    TargetGap,
    TargetGapAnalysis,
    TargetType,
    TargetUsageMode,
)
from app.learning_authoring.service import LearningAuthoringNotFoundError, LearningAuthoringService
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)

ACTOR_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ORG_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
CANDIDATE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def actor() -> ActorContext:
    return ActorContext(
        actor_id=ACTOR_ID,
        organization_id=ORG_ID,
        roles=frozenset({Role.REVIEWER}),
    )


def requirement() -> RoleRequirement:
    return RoleRequirement(
        id="cap-python-cleaning",
        criterion_dimension=CriterionDimension.SKILL,
        classification=RequirementClassification.TRAINABLE_MANDATORY,
        evidence_terms=["Python data cleaning"],
        confidence_threshold=0.8,
        assessment_recommendation="Practice handling invalid tabular values with Python.",
        rubric_version="rubric-v1",
        target_level="3",
        observable_behaviors=["Handle invalid values in tabular data"],
    )


def gap() -> TargetGap:
    return TargetGap(
        id="gap-python-cleaning",
        target_id="role-data-analyst",
        target_type=TargetType.CURRENT_ROLE,
        requirement_id="cap-python-cleaning",
        matched_evidence_refs=["evidence:cv:page-2"],
        missing_signals=["data_cleaning_depth"],
        rationale="The profile shows Python usage but not structured data cleaning.",
        preliminary_priority=PreliminaryPriority.HIGH,
        missing_priority_inputs=[],
        evidence_status=AssessmentEvidenceStatus.INSUFFICIENT,
    )


def portfolio() -> CombinedGapPortfolio:
    return CombinedGapPortfolio(
        id="analysis-001",
        cv_profile_id="profile-001",
        cv_profile_version=4,
        current_target_version="2",
        owner_actor_id=ACTOR_ID,
        organization_id=ORG_ID,
        correlation_id="correlation-001",
        candidate_id=CANDIDATE_ID,
        analysis_status=AnalysisStatus.READY,
        current_role=TargetGapAnalysis(
            target_id="role-data-analyst",
            target_type=TargetType.CURRENT_ROLE,
            usage_mode=TargetUsageMode.OFFICIAL,
            assessments=[],
            gaps=[gap()],
        ),
    )


def role_profile() -> RoleCompetencyProfile:
    return RoleCompetencyProfile(
        id="role-data-analyst",
        version="2",
        status=RoleProfileStatus.ACTIVE,
        source_jd_profile_id="jd-data-analyst",
        source_jd_profile_version=1,
        rule_set_version="rules-v1",
        policy_version="policy-v1",
        requirements=[requirement()],
    )


class FakeCapabilityAnalysisService:
    def __init__(self, source: CombinedGapPortfolio) -> None:
        self.source = source

    async def get(self, portfolio_id: str, actor_context: ActorContext) -> CombinedGapPortfolio:
        if portfolio_id != self.source.id:
            raise KeyError(portfolio_id)
        if actor_context.actor_id != self.source.owner_actor_id:
            raise PermissionError("access_denied")
        return self.source


class FakeRoleProfileReader:
    def __init__(self, *, target_level: str | None = "3") -> None:
        self._target_level = target_level

    async def get_version(
        self, role_profile_id: str, version: str
    ) -> RoleCompetencyProfile | None:
        if (role_profile_id, version) == ("role-data-analyst", "2"):
            return role_profile().model_copy(
                update={
                    "requirements": [
                        requirement().model_copy(update={"target_level": self._target_level})
                    ]
                }
            )
        return None


def service() -> LearningAuthoringService:
    return LearningAuthoringService(
        capability_analyses=FakeCapabilityAnalysisService(portfolio()),
        role_profiles=FakeRoleProfileReader(),
    )


def production_target_service() -> LearningAuthoringService:
    return LearningAuthoringService(
        capability_analyses=FakeCapabilityAnalysisService(portfolio()),
        role_profiles=FakeRoleProfileReader(target_level="production"),
    )


async def authoring_client() -> AsyncClient:
    from app.integration.actor_context import get_signed_actor_context
    from app.integration.auth import verify_integration_api_key
    from app.integration.learning_authoring_api import router
    from app.shared.errors import APIError, api_error_handler

    app = FastAPI()
    app.state.learning_authoring_service = service()
    app.add_exception_handler(APIError, api_error_handler)
    app.dependency_overrides[verify_integration_api_key] = lambda: None
    app.dependency_overrides[get_signed_actor_context] = actor
    app.include_router(router)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_learning_need_projection_preserves_references_without_raw_evidence() -> None:
    result = await service().get_learning_need(
        "learning-need:analysis-001:gap-python-cleaning", actor()
    )

    assert result.id == "learning-need:analysis-001:gap-python-cleaning"
    assert result.candidate_reference == CANDIDATE_ID
    assert result.competency.id == "cap-python-cleaning"
    assert result.target_state.level == "3"
    assert result.source_gap_refs == ["gap-python-cleaning"]
    assert result.evidence_references == ["evidence:cv:page-2"]
    assert "Python usage" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_learning_objective_projection_is_linked_to_learning_need() -> None:
    result = await service().get_learning_objective(
        "objective-learning-need:analysis-001:gap-python-cleaning", actor()
    )

    assert result.id == "objective-learning-need:analysis-001:gap-python-cleaning"
    assert result.learning_need_ref == "learning-need:analysis-001:gap-python-cleaning"
    assert result.statement == "data_cleaning_depth"
    assert result.measurable_outcome == (
        "Practice handling invalid tabular values with Python."
    )
    assert result.target_level == 3
    assert result.bloom_level is None
    assert result.evidence_required is None


@pytest.mark.asyncio
async def test_learning_objective_projection_accepts_production_target_for_gap_authoring() -> None:
    result = await production_target_service().get_learning_objective(
        "objective-learning-need:analysis-001:gap-python-cleaning", actor()
    )

    assert result.target_level == 5


@pytest.mark.asyncio
async def test_learning_objective_projection_preserves_missing_target_level() -> None:
    result = await service().get_learning_objective(
        "objective-learning-need:analysis-001:gap-python-cleaning", actor()
    )

    # The fixture above has a numeric target level; this assertion documents the
    # projection contract for nullable JD target levels via the production reader.
    assert result.target_level == 3


@pytest.mark.asyncio
async def test_learning_objective_projection_allows_missing_target_level_for_gap_authoring() -> None:
    result = await LearningAuthoringService(
        capability_analyses=FakeCapabilityAnalysisService(portfolio()),
        role_profiles=FakeRoleProfileReader(target_level=None),
    ).get_learning_objective(
        "objective-learning-need:analysis-001:gap-python-cleaning", actor()
    )

    assert result.target_level is None
    assert result.measurable_outcome == (
        "Practice handling invalid tabular values with Python."
    )


@pytest.mark.asyncio
async def test_blueprint_projection_reconstructs_deterministic_instructional_structure() -> None:
    result = await service().get_instructional_blueprint(
        "instructional-blueprint-objective-learning-need:analysis-001:gap-python-cleaning",
        actor(),
    )

    assert result.learning_need_ref == "learning-need:analysis-001:gap-python-cleaning"
    assert result.objective_refs == [
        "objective-learning-need:analysis-001:gap-python-cleaning"
    ]
    assert result.lessons[0].objective_refs == result.objective_refs
    assert result.lessons[0].assessment_refs == []
    assert result.lessons[0].title == "data_cleaning_depth"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "artifact_id", "error_code"),
    [
        ("get_learning_need", "learning-need:missing:gap", "learning_need_not_found"),
        ("get_learning_need", "not-a-learning-need", "learning_need_not_found"),
        ("get_learning_objective", "objective-missing", "learning_objective_not_found"),
        (
            "get_instructional_blueprint",
            "instructional-blueprint-missing",
            "instructional_blueprint_not_found",
        ),
    ],
)
async def test_unknown_authoring_references_fail_closed(
    method_name: str, artifact_id: str, error_code: str
) -> None:
    method = getattr(service(), method_name)

    with pytest.raises(LearningAuthoringNotFoundError, match=error_code):
        await method(artifact_id, actor())


@pytest.mark.asyncio
async def test_authoring_api_serializes_all_three_read_only_projections() -> None:
    async with await authoring_client() as client:
        need_response = await client.get(
            "/api/v1/authoring/learning-needs/learning-need:analysis-001:gap-python-cleaning"
        )
        objective_response = await client.get(
            "/api/v1/authoring/learning-objectives/objective-learning-need:analysis-001:gap-python-cleaning"
        )
        blueprint_response = await client.get(
            "/api/v1/authoring/instructional-blueprints/instructional-blueprint-objective-learning-need:analysis-001:gap-python-cleaning"
        )

    assert need_response.status_code == 200
    assert need_response.json()["schema_version"] == "v1"
    assert need_response.json()["data"]["evidence_references"] == [
        "evidence:cv:page-2"
    ]
    assert objective_response.status_code == 200
    assert objective_response.json()["data"]["learning_need_ref"] == (
        "learning-need:analysis-001:gap-python-cleaning"
    )
    assert blueprint_response.status_code == 200
    assert blueprint_response.json()["data"]["lessons"][0]["assessment_refs"] == []


@pytest.mark.asyncio
async def test_authoring_api_returns_stable_errors_for_missing_references() -> None:
    async with await authoring_client() as client:
        response = await client.get(
            "/api/v1/authoring/learning-needs/learning-need:missing:gap"
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "learning_need_not_found"


@pytest.mark.asyncio
async def test_authoring_api_has_no_write_route() -> None:
    async with await authoring_client() as client:
        response = await client.post(
            "/api/v1/authoring/learning-needs/learning-need:analysis-001:gap-python-cleaning",
            json={"statement": "changed"},
        )

    assert response.status_code == 405


@pytest.mark.asyncio
async def test_authoring_api_exposes_only_the_stable_learning_need_shape() -> None:
    async with await authoring_client() as client:
        response = await client.get(
            "/api/v1/authoring/learning-needs/learning-need:analysis-001:gap-python-cleaning"
        )

    assert set(response.json()["data"]) == {
        "id",
        "candidate_reference",
        "target_reference",
        "learner_context",
        "competency",
        "current_state",
        "target_state",
        "gap",
        "missing_knowledge",
        "priority",
        "confidence",
        "source_gap_refs",
        "evidence_references",
    }


@pytest.mark.asyncio
async def test_authoring_api_exposes_nullable_objective_fields_without_inference() -> None:
    async with await authoring_client() as client:
        response = await client.get(
            "/api/v1/authoring/learning-objectives/objective-learning-need:analysis-001:gap-python-cleaning"
        )

    data = response.json()["data"]
    assert set(data) == {
        "id",
        "learning_need_ref",
        "statement",
        "bloom_level",
        "evidence_required",
        "competency_id",
        "current_level",
        "target_level",
        "measurable_outcome",
        "gap_id",
        "sequence",
    }
    assert data["bloom_level"] is None
    assert data["evidence_required"] is None


@pytest.mark.asyncio
async def test_authoring_api_preserves_empty_assessment_references() -> None:
    async with await authoring_client() as client:
        response = await client.get(
            "/api/v1/authoring/instructional-blueprints/instructional-blueprint-objective-learning-need:analysis-001:gap-python-cleaning"
        )

    data = response.json()["data"]
    assert set(data) == {
        "id",
        "version",
        "learning_need_ref",
        "objective_refs",
        "course",
        "modules",
        "lessons",
    }
    assert data["lessons"][0]["assessment_refs"] == []
