import json

import pytest
from pydantic import ValidationError

from app.course_authoring.conversation_schemas import (
    AuthoringConversationResponse,
    AuthoringReadiness,
)
from app.course_authoring.conversation_service import (
    AUTHORING_CONVERSATION_PROMPT_ID,
    AUTHORING_CONVERSATION_PROMPT_VERSION,
    register_authoring_conversation_contracts,
)
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry


def test_conversation_prompt_requires_structured_proposals_for_suggestions() -> None:
    prompts = PromptTemplateRegistry()
    schemas = OutputSchemaRegistry()
    register_authoring_conversation_contracts(prompts, schemas)
    prompt = prompts.resolve(AUTHORING_CONVERSATION_PROMPT_ID, AUTHORING_CONVERSATION_PROMPT_VERSION)
    instructions = f'{prompt.system_instruction}\n{prompt.user_instruction}'

    assert 'proposed_changes' in instructions
    assert 'concrete' in instructions.lower()
    assert 'do not claim' in instructions.lower()


def test_conversation_response_accepts_bounded_question_and_semantic_options() -> None:
    response = AuthoringConversationResponse.model_validate_json(json.dumps({
        "assistant_message": "What level of depth should the program target?",
        "conversation_state": "BRIEF_NEEDS_CLARIFICATION",
        "questions": [{
            "id": "target-depth",
            "field": "target_depth",
            "type": "SINGLE_CHOICE",
            "prompt": "What depth do you need?",
            "options": [{"value": "APPLIED_PROFICIENCY", "label": "Applied proficiency"}],
            "required": True,
        }],
        "proposed_changes": [],
        "unresolved_items": ["target_depth"],
        "readiness": "NEEDS_CLARIFICATION",
    }))

    assert response.questions[0].options[0].value == "APPLIED_PROFICIENCY"
    assert response.readiness is AuthoringReadiness.NEEDS_CLARIFICATION


def test_unknown_proposed_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AuthoringConversationResponse.model_validate({
            "assistant_message": "proposal",
            "conversation_state": "BRIEF_NEEDS_CLARIFICATION",
            "questions": [],
            "proposed_changes": [{
                "field": "invented.path",
                "proposed_value": "x",
                "reason": "x",
            }],
            "unresolved_items": [],
            "readiness": "READY_FOR_CONFIRMATION",
        })


def test_unknown_response_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AuthoringConversationResponse.model_validate({
            "assistant_message": "proposal",
            "conversation_state": "BRIEF_NEEDS_CLARIFICATION",
            "questions": [],
            "proposed_changes": [],
            "unresolved_items": [],
            "readiness": "NEEDS_CLARIFICATION",
            "hidden_reasoning": "must not be accepted",
        })
