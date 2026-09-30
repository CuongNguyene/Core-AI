import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.authorization.fixtures import ADMIN_ID, LEARNER_ID, REVIEWER_ID
from app.extraction.repository import InMemoryExtractionRepository
from app.extraction.schemas import (
    DocumentKind,
    ExtractionJob,
    ExtractionProfile,
    JDExtractionOutput,
    JobStatus,
    ReviewState,
)
from app.matching.errors import (
    ExtractionProfileNotAcceptedError,
    RoleProfileNotActiveError,
    SupersededInputError,
)
from app.matching.repository import (
    InMemoryPreliminaryMatchRepository,
    InMemoryRoleProfileRepository,
)
from app.matching.rules import evaluate_requirements
from app.matching.schemas import RequirementClassification, RoleProfileStatus
from app.matching.service import PreliminaryMatchService
from tests.test_matching_rules import accepted_cv, active_role, claim, requirement


async def _golden_service(
    cv_state: ReviewState, *, role_active: bool, supersede_cv: bool
) -> PreliminaryMatchService:
    extraction = InMemoryExtractionRepository()
    cv_profile = accepted_cv(claim("Python")).model_copy(
        update={
            "review_state": cv_state,
            "accepted_by": REVIEWER_ID if cv_state is ReviewState.ACCEPTED else None,
            "accepted_at": accepted_cv(claim("Python")).accepted_at
            if cv_state is ReviewState.ACCEPTED
            else None,
        }
    )
    await extraction.enqueue(
        ExtractionJob(
            id=cv_profile.job_id,
            document_id=cv_profile.document_id,
            document_kind=DocumentKind.CV,
            owner_actor_id=cv_profile.owner_actor_id,
            correlation_id="golden-correlation",
            status=JobStatus.QUEUED,
        )
    )
    await extraction.mark_succeeded(cv_profile.job_id, cv_profile)
    jd_profile = ExtractionProfile(
        id="jd-profile-1",
        job_id="jd-job-1",
        document_id="fixture-jd-basic",
        document_kind=DocumentKind.JD,
        owner_actor_id=ADMIN_ID,
        version=1,
        review_state=ReviewState.ACCEPTED,
        accepted_by=REVIEWER_ID,
        accepted_at=datetime.now(UTC),
        output=JDExtractionOutput(required_skills=[], responsibilities=[], qualifications=[]),
        audit={},
    )
    await extraction.enqueue(
        ExtractionJob(
            id=jd_profile.job_id,
            document_id=jd_profile.document_id,
            document_kind=DocumentKind.JD,
            owner_actor_id=jd_profile.owner_actor_id,
            correlation_id="golden-correlation",
            status=JobStatus.QUEUED,
        )
    )
    await extraction.mark_succeeded(jd_profile.job_id, jd_profile)
    if supersede_cv:
        await extraction.create_correction(cv_profile.id, "reviewer-2", cv_profile.output)
    role = active_role(
        requirement("critical-python", RequirementClassification.ROLE_CRITICAL)
    ).model_copy(
        update={
            "status": RoleProfileStatus.ACTIVE if role_active else RoleProfileStatus.RETIRED,
            "source_jd_profile_id": jd_profile.id,
        }
    )
    return PreliminaryMatchService(
        extraction,
        InMemoryRoleProfileRepository([role]),
        InMemoryPreliminaryMatchRepository(),
    )


def test_preliminary_matching_golden_cases_are_deterministic() -> None:
    golden_path = Path("tests/golden/preliminary_match_ai_engineer.json")
    cases = json.loads(golden_path.read_text())["rule_cases"]

    for case in cases:
        requirements = [
            requirement(
                item["id"],
                RequirementClassification(item["classification"]),
                confidence_threshold=item.get("confidence_threshold", 0.8),
                conflicting_terms=item.get("conflicting_terms"),
            )
            for item in case["requirements"]
        ]
        evaluation = evaluate_requirements(
            accepted_cv(
                *[
                    claim(item["value"], item.get("confidence", 0.9), item.get("offset", 16))
                    for item in case["claims"]
                ]
            ),
            active_role(*requirements),
        )

        assert [item.status.value for item in evaluation.criterion_results] == case["statuses"]
        assert len(evaluation.allocations) == case["allocation_count"]
        assert evaluation.model_dump(mode="json") == evaluate_requirements(
            accepted_cv(
                *[
                    claim(item["value"], item.get("confidence", 0.9), item.get("offset", 16))
                    for item in case["claims"]
                ]
            ),
            active_role(*requirements),
        ).model_dump(mode="json")


def test_golden_harness_covers_required_rule_outcomes() -> None:
    cases = json.loads(Path("tests/golden/preliminary_match_ai_engineer.json").read_text())[
        "rule_cases"
    ]

    names = {case["name"] for case in cases}
    assert {
        "happy_path",
        "evidence_reuse",
        "low_confidence",
        "mandatory_gap",
        "conflicting",
    } <= names


@pytest.mark.asyncio
async def test_preliminary_matching_golden_eligibility_cases() -> None:
    cases = json.loads(Path("tests/golden/preliminary_match_ai_engineer.json").read_text())[
        "eligibility_cases"
    ]
    errors = {
        "ExtractionProfileNotAcceptedError": ExtractionProfileNotAcceptedError,
        "RoleProfileNotActiveError": RoleProfileNotActiveError,
        "SupersededInputError": SupersededInputError,
    }

    for case in cases:
        service = await _golden_service(
            ReviewState(case["cv_state"]),
            role_active=case["role_active"],
            supersede_cv=case["supersede_cv"],
        )
        with pytest.raises(errors[case["error"]]):
            await service.create("cv-profile-1", "role-ai-engineer", LEARNER_ID, "golden")
