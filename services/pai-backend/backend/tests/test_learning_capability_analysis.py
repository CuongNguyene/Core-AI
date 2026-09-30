from datetime import date
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.authorization.schemas import ActorContext, Role
from app.capability_analysis.schemas import (
    AnalysisStatus,
    CombinedGapPortfolio,
    PreliminaryPriority,
    TargetGap,
    TargetGapAnalysis,
    TargetType,
    TargetUsageMode,
)
from app.learning.repository import InMemoryLearningPathRepository
from app.learning.schemas import LearningPathSourceType, LearningPathStatus
from app.learning.service import (
    CapabilityAnalysisLearningPathRequest,
    LearningPathService,
)
from tests.test_learning_eligibility import ORG_ID, SUBJECT_ID, target_profile


class AnalysisRepository:
    def __init__(self, analysis: CombinedGapPortfolio | None) -> None:
        self.analysis = analysis

    async def get(self, analysis_id: str) -> CombinedGapPortfolio | None:
        if self.analysis and self.analysis.id == analysis_id:
            return self.analysis
        return None

    async def get_for_candidate(self, candidate_id: UUID, *, actor_id: UUID, organization_id: UUID) -> CombinedGapPortfolio | None:
        item = self.analysis
        if item is None or item.candidate_id != candidate_id or item.owner_actor_id != actor_id or item.organization_id != organization_id:
            return None
        return item


class ProfileRepository:
    async def get_profile(self, _profile_id: str):
        return SimpleNamespace(version=2)


def actor() -> ActorContext:
    return ActorContext(
        actor_id=SUBJECT_ID,
        organization_id=ORG_ID,
        roles=frozenset({Role.LEARNER}),
    )


def analysis() -> CombinedGapPortfolio:
    gap = TargetGap(
        id="gap-python",
        target_id="role-1",
        target_type=TargetType.CURRENT_ROLE,
        requirement_id="python",
        matched_evidence_refs=["evidence:python:1"],
        missing_signals=[],
        rationale="Requires Python practice.",
        preliminary_priority=PreliminaryPriority.HIGH,
        missing_priority_inputs=[],
        recommendation="practice-python",
    )
    return CombinedGapPortfolio(
        id="analysis-1",
        cv_profile_id="profile-1",
        cv_profile_version=2,
        current_target_version="1.0",
        owner_actor_id=SUBJECT_ID,
        organization_id=ORG_ID,
        correlation_id="analysis-1",
        candidate_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        analysis_status=AnalysisStatus.READY,
        current_role=TargetGapAnalysis(
            target_id="role-1",
            target_type=TargetType.CURRENT_ROLE,
            usage_mode=TargetUsageMode.OFFICIAL,
            assessments=[],
            gaps=[gap],
        ),
    )


@pytest.mark.asyncio
async def test_capability_analysis_generation_creates_draft_with_source_snapshot() -> None:
    paths = InMemoryLearningPathRepository()
    profile = target_profile()
    profile = profile.model_copy(update={
        "requirements": [profile.requirements[0].model_copy(update={"target_level": "1"})]
    })

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

    result = await service.create_from_capability_analysis(
        actor=actor(),
        request=CapabilityAnalysisLearningPathRequest(
            capability_analysis_id="analysis-1",
            development_goal="Become job-ready",
            target_completion_date=date(2026, 12, 1),
        ),
    )

    assert result.source_type is LearningPathSourceType.CAPABILITY_ANALYSIS
    assert result.status is LearningPathStatus.DRAFT
    assert result.capability_analysis_id == "analysis-1"
    assert result.capability_analysis_version == 1
    assert result.validation.ready_for_review is True
    assert result.verified_competency_record_ids == []


@pytest.mark.asyncio
async def test_capability_analysis_generation_rejects_non_numeric_target_level_with_stable_code() -> None:
    paths = InMemoryLearningPathRepository()
    profile = target_profile().model_copy(update={
        "requirements": [target_profile().requirements[0].model_copy(update={"target_level": "production"})]
    })

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

    with pytest.raises(Exception, match="capability_analysis_target_level_required"):
        await service.create_from_capability_analysis(
            actor=actor(),
            request=CapabilityAnalysisLearningPathRequest(
                capability_analysis_id="analysis-1",
                development_goal="Become job-ready",
                target_completion_date=date(2026, 12, 1),
            ),
        )


@pytest.mark.asyncio
async def test_missing_capability_analysis_fails_closed() -> None:
    service = LearningPathService(
        competency_records=None,  # type: ignore[arg-type]
        role_profiles=None,  # type: ignore[arg-type]
        matches=None,  # type: ignore[arg-type]
        paths=InMemoryLearningPathRepository(),
        capability_analyses=AnalysisRepository(None),
    )

    with pytest.raises(Exception, match="capability_analysis_not_found"):
        await service.create_from_capability_analysis(
            actor=actor(),
            request=CapabilityAnalysisLearningPathRequest(
                capability_analysis_id="missing",
                development_goal="Become job-ready",
                target_completion_date=date(2026, 12, 1),
            ),
        )


@pytest.mark.asyncio
async def test_capability_analysis_draft_requires_review_before_approval() -> None:
    paths = InMemoryLearningPathRepository()
    analysis_repository = AnalysisRepository(analysis())
    profile = target_profile().model_copy(update={
        "requirements": [target_profile().requirements[0].model_copy(update={"target_level": "1"})]
    })

    class Roles:
        async def get_version(self, *_args):
            return profile

        async def get_preferred_target(self, *_args):
            return profile

    service = LearningPathService(
        competency_records=None,  # type: ignore[arg-type]
        role_profiles=Roles(),  # type: ignore[arg-type]
        matches=None,  # type: ignore[arg-type]
        paths=paths,
        capability_analyses=analysis_repository,
        profiles=ProfileRepository(),  # type: ignore[arg-type]
    )
    created = await service.create_from_capability_analysis(
        actor=actor(),
        request=CapabilityAnalysisLearningPathRequest(
            capability_analysis_id="analysis-1",
            development_goal="Become job-ready",
            target_completion_date=date(2026, 12, 1),
        ),
    )

    with pytest.raises(Exception, match="review_required"):
        await service.approve(created.id, actor=actor(), expected_version=1)

    reviewed = await service.review(created.id, actor=actor(), expected_version=1)
    assert reviewed.status is LearningPathStatus.DRAFT
    assert reviewed.reviewed is True
    assert reviewed.reviewed_version == 1

    approved = await service.approve(created.id, actor=actor(), expected_version=1)
    assert approved.status is LearningPathStatus.ACTIVE
    assert approved.approved_version == 1


@pytest.mark.asyncio
async def test_stale_capability_analysis_cannot_be_reviewed() -> None:
    paths = InMemoryLearningPathRepository()
    analysis_repository = AnalysisRepository(analysis())
    profile = target_profile().model_copy(update={
        "requirements": [target_profile().requirements[0].model_copy(update={"target_level": "1"})]
    })

    class Roles:
        async def get_version(self, *_args):
            return profile

    service = LearningPathService(
        competency_records=None,  # type: ignore[arg-type]
        role_profiles=Roles(),  # type: ignore[arg-type]
        matches=None,  # type: ignore[arg-type]
        paths=paths,
        capability_analyses=analysis_repository,
        profiles=ProfileRepository(),  # type: ignore[arg-type]
    )
    created = await service.create_from_capability_analysis(
        actor=actor(),
        request=CapabilityAnalysisLearningPathRequest(
            capability_analysis_id="analysis-1",
            development_goal="Become job-ready",
            target_completion_date=date(2026, 12, 1),
        ),
    )
    analysis_repository.analysis = analysis().model_copy(update={"analysis_version": 2})

    with pytest.raises(Exception, match="CAPABILITY_ANALYSIS_VERSION_CHANGED"):
        await service.review(created.id, actor=actor(), expected_version=1)


@pytest.mark.asyncio
async def test_regeneration_creates_draft_v2_and_approval_supersedes_v1() -> None:
    paths = InMemoryLearningPathRepository()
    analysis_repository = AnalysisRepository(analysis())
    profile = target_profile().model_copy(update={
        "requirements": [target_profile().requirements[0].model_copy(update={"target_level": "1"})]
    })

    class Roles:
        async def get_version(self, *_args):
            return profile

        async def get_preferred_target(self, *_args):
            return profile

    service = LearningPathService(
        competency_records=None,  # type: ignore[arg-type]
        role_profiles=Roles(),  # type: ignore[arg-type]
        matches=None,  # type: ignore[arg-type]
        paths=paths,
        capability_analyses=analysis_repository,
        profiles=ProfileRepository(),  # type: ignore[arg-type]
    )
    request = CapabilityAnalysisLearningPathRequest(
        capability_analysis_id="analysis-1",
        development_goal="Become job-ready",
        target_completion_date=date(2026, 12, 1),
    )
    first = await service.create_from_capability_analysis(actor=actor(), request=request)
    first = await service.review(first.id, actor=actor(), expected_version=1)
    first = await service.approve(first.id, actor=actor(), expected_version=1)

    second = await service.regenerate_from_capability_analysis(
        first.id, actor=actor(), request=request
    )
    assert second.id == first.id
    assert second.version == 2
    assert second.status is LearningPathStatus.DRAFT
    assert (await paths.get(first.id, version=1)).status is LearningPathStatus.ACTIVE

    await service.review(second.id, actor=actor(), expected_version=2)
    approved = await service.approve(second.id, actor=actor(), expected_version=2)
    assert approved.status is LearningPathStatus.ACTIVE
    assert (await paths.get(first.id, version=1)).status is LearningPathStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_active_path_exposes_stale_metadata_without_changing_status() -> None:
    paths = InMemoryLearningPathRepository()
    analysis_repository = AnalysisRepository(analysis())
    profile = target_profile().model_copy(update={
        "requirements": [target_profile().requirements[0].model_copy(update={"target_level": "1"})]
    })

    class Roles:
        async def get_version(self, *_args):
            return profile

        async def get_preferred_target(self, *_args):
            return profile

    service = LearningPathService(
        competency_records=None,  # type: ignore[arg-type]
        role_profiles=Roles(),  # type: ignore[arg-type]
        matches=None,  # type: ignore[arg-type]
        paths=paths,
        capability_analyses=analysis_repository,
        profiles=ProfileRepository(),  # type: ignore[arg-type]
    )
    request = CapabilityAnalysisLearningPathRequest(
        capability_analysis_id="analysis-1",
        development_goal="Become job-ready",
        target_completion_date=date(2026, 12, 1),
    )
    path = await service.create_from_capability_analysis(actor=actor(), request=request)
    await service.review(path.id, actor=actor(), expected_version=1)
    await service.approve(path.id, actor=actor(), expected_version=1)
    analysis_repository.analysis = analysis().model_copy(update={"analysis_version": 2})

    loaded = await service.get(path.id, actor=actor())
    assert loaded.status is LearningPathStatus.ACTIVE
    assert loaded.is_stale is True
    assert "CAPABILITY_ANALYSIS_VERSION_CHANGED" in loaded.stale_reasons
