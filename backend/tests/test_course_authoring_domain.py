from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.course_authoring.schemas import (
    AudienceSnapshot,
    AudienceSnapshotSource,
    CourseAuthoringMode,
    CourseAuthoringRequestCreate,
    TrainingBrief,
)


def snapshot(**overrides: object) -> AudienceSnapshot:
    values: dict[str, object] = {
        "id": "audience-snapshot-001",
        "learner_refs": ("lms-1",),
        "learner_count": 1,
        "captured_at": datetime(2026, 8, 24, tzinfo=UTC),
        "source": AudienceSnapshotSource.MANUAL_SELECTION,
        "metadata": {},
    }
    values.update(overrides)
    return AudienceSnapshot.model_validate(values)


def test_audience_snapshot_allows_empty_but_rejects_duplicate_opaque_refs() -> None:
    assert snapshot(learner_refs=[], learner_count=0).learner_refs == ()
    with pytest.raises(ValidationError):
        snapshot(learner_refs=["learner-1", "learner-1"], learner_count=2)


def test_audience_snapshot_preserves_order_and_count_without_resolving_lms_identity() -> None:
    audience = snapshot(learner_refs=("lms-b", "lms-a"), learner_count=2)

    assert audience.learner_refs == ("lms-b", "lms-a")
    assert audience.learner_count == 2
    with pytest.raises(ValidationError):
        audience.learner_count = 3


def test_goal_driven_request_allows_empty_learning_design_refs() -> None:
    request = CourseAuthoringRequestCreate(
        title="Python onboarding",
        training_brief=TrainingBrief(goal="Improve Python data cleaning"),
        learner_refs=["lms-1"],
        mode=CourseAuthoringMode.GOAL_DRIVEN,
    )

    assert request.learning_need_refs == ()
    assert request.objective_refs == ()
    assert request.instructional_blueprint_ref is None


def test_goal_driven_request_allows_no_selected_learners() -> None:
    request = CourseAuthoringRequestCreate(
        title="Python onboarding",
        training_brief=TrainingBrief(goal="Improve Python data cleaning"),
        learner_refs=[],
        mode=CourseAuthoringMode.GOAL_DRIVEN,
    )

    assert request.learner_refs == ()


def test_gap_driven_request_requires_explicit_learning_design_reference() -> None:
    with pytest.raises(ValidationError):
        CourseAuthoringRequestCreate(
            title="Gap course",
            training_brief=TrainingBrief(goal="Close a skill gap"),
            learner_refs=["lms-1"],
            mode=CourseAuthoringMode.GAP_DRIVEN,
        )


def test_training_brief_requires_goal() -> None:
    with pytest.raises(ValidationError):
        TrainingBrief(goal=" ")


def test_course_authoring_request_create_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        CourseAuthoringRequestCreate(
            title=" ",
            training_brief=TrainingBrief(goal="Close a skill gap"),
            learner_refs=["lms-1"],
            mode=CourseAuthoringMode.GOAL_DRIVEN,
        )


def test_domain_contract_does_not_require_lms_profile_data() -> None:
    request = CourseAuthoringRequestCreate(
        title="Opaque audience",
        training_brief=TrainingBrief(goal="Support onboarding"),
        learner_refs=["external-user-42"],
        mode=CourseAuthoringMode.GOAL_DRIVEN,
    )

    assert request.learner_refs == ("external-user-42",)
    assert request.model_dump().get("learner_profiles") is None
