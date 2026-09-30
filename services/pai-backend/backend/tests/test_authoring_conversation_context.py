from app.course_authoring.brief_revision_schemas import BriefRevisionPayload
from app.course_authoring.conversation_context import (
    build_authoring_conversation_context,
    determine_readiness,
)
from app.course_authoring.conversation_schemas import AuthoringReadiness


def test_deterministic_readiness_overrides_model_ready_when_required_field_missing() -> None:
    payload = BriefRevisionPayload(training_goal="Build APIs")

    assert determine_readiness(payload, {"learning_horizon"}) is AuthoringReadiness.NEEDS_CLARIFICATION
    assert determine_readiness(payload, set()) is AuthoringReadiness.READY_FOR_CONFIRMATION


def test_context_uses_structured_state_and_bounds_recent_turns() -> None:
    payload = BriefRevisionPayload(
        training_goal="Build APIs",
        desired_outcomes=("Ship a service",),
        learning_horizon="12 months",
    )
    context = build_authoring_conversation_context(payload, [{"message": str(index)} for index in range(8)])

    assert context["structured_state"]["training_goal"] == "Build APIs"
    assert len(context["recent_turns"]) == 6
    assert context["recent_turns"][0]["message"] == "2"
    assert "authoring-brief-revision:" not in str(context)
