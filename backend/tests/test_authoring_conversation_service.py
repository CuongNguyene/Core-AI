import asyncio
from types import SimpleNamespace

import pytest

from app.course_authoring.brief_revision_schemas import BriefRevisionPayload
from app.course_authoring.conversation_schemas import AuthoringReadiness
from app.course_authoring.conversation_service import AuthoringConversationService


class FakeGateway:
    def __init__(self, parsed: object | None = None, error: Exception | None = None) -> None:
        self.parsed = parsed
        self.error = error
        self.calls: list[object] = []

    async def infer_structured(self, request: object, output_schema: object) -> object:
        self.calls.append(request)
        if self.error:
            raise self.error
        return SimpleNamespace(parsed=self.parsed)


def test_model_ready_is_recomputed_when_required_field_is_missing() -> None:
    gateway = FakeGateway(parsed={
        "assistant_message": "Your brief is ready.",
        "conversation_state": "BRIEF_READY",
        "questions": [],
        "proposed_changes": [],
        "unresolved_items": ["learning_horizon"],
        "readiness": "READY_FOR_CONFIRMATION",
    })
    service = AuthoringConversationService(gateway=gateway)

    response = asyncio.run(service.respond(BriefRevisionPayload(training_goal="Build APIs"), "Proceed"))

    assert response.readiness is AuthoringReadiness.NEEDS_CLARIFICATION
    assert response.conversation_state.value == "BRIEF_NEEDS_CLARIFICATION"


def test_provider_response_is_validated_without_mutating_structured_state() -> None:
    gateway = FakeGateway(parsed={
        "assistant_message": "Choose a target.",
        "conversation_state": "BRIEF_NEEDS_CLARIFICATION",
        "questions": [],
        "proposed_changes": [{"field": "invented.path", "proposed_value": "x", "reason": "x"}],
        "unresolved_items": ["desired_outcomes"],
        "readiness": "NEEDS_CLARIFICATION",
    })
    service = AuthoringConversationService(gateway=gateway)

    with pytest.raises(ValueError, match="conversation_response_invalid"):
        asyncio.run(service.respond(BriefRevisionPayload(training_goal="Build APIs"), "Proceed"))
