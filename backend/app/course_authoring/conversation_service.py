from __future__ import annotations

import json
import logging
from time import perf_counter

from app.course_authoring.brief_revision_schemas import BriefRevisionPayload
from app.course_authoring.brief_revision_service import AuthoringBriefRevisionService
from app.model_gateway.contracts import (
    DataClassification,
    InferencePurpose,
    InferenceRequest,
    ModelGateway,
    OutputContract,
)
from app.model_gateway.prompts import PromptTemplate, PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry

from .conversation_context import build_authoring_conversation_context, determine_readiness
from .conversation_schemas import (
    AuthoringConversationResponse,
    AuthoringReadiness,
    ConversationState,
)

AUTHORING_CONVERSATION_PROMPT_ID = "authoring_conversation"
AUTHORING_CONVERSATION_PROMPT_VERSION = "sep-08a.1-v1"
logger = logging.getLogger(__name__)


def register_authoring_conversation_contracts(
    prompts: PromptTemplateRegistry, schemas: OutputSchemaRegistry
) -> None:
    schemas.register(
        AUTHORING_CONVERSATION_PROMPT_ID,
        AUTHORING_CONVERSATION_PROMPT_VERSION,
        AuthoringConversationResponse,
    )
    prompts.register(PromptTemplate(
        template_id=AUTHORING_CONVERSATION_PROMPT_ID,
        version=AUTHORING_CONVERSATION_PROMPT_VERSION,
        system_instruction=(
            "Help an author clarify a training brief. Return only the registered "
            "conversation response schema. Treat readiness as a suggestion; never "
            "confirm or mutate an artifact. Use only supported brief fields. "
            "When you suggest a change, include a concrete proposed_changes entry "
            "for each suggested field; do not claim to have proposed a change in "
            "assistant_message unless the matching structured entry is present."
        ),
        user_instruction=(
            "Summarize the current structured brief, ask only high-value unresolved "
            "questions, and propose bounded changes concretely when useful. If "
            "desired outcomes or prerequisites are missing and the author asks for "
            "suggestions, return concrete structured proposed_changes values rather "
            "than prose-only suggestions. Quick-option values must be semantic "
            "values with human-readable labels."
        ),
    ))


class AuthoringConversationService:
    def __init__(
        self,
        *,
        gateway: ModelGateway,
        requested_provider: str = "configured",
        output_token_budget: int | None = None,
    ) -> None:
        self._gateway = gateway
        self._requested_provider = requested_provider
        self._output_token_budget = output_token_budget

    async def respond(
        self,
        payload: BriefRevisionPayload,
        user_message: str,
        recent_turns: tuple[dict[str, object], ...] = (),
        request_id: str | None = None,
    ) -> AuthoringConversationResponse:
        started_at = perf_counter()
        context_started_at = perf_counter()
        context = build_authoring_conversation_context(payload, recent_turns)
        context["user_message"] = user_message
        context_build_ms = int((perf_counter() - context_started_at) * 1000)
        request = InferenceRequest(
            purpose=InferencePurpose.AUTHORING_CONVERSATION,
            data_classification=DataClassification.PUBLIC,
            prompt_template_id=AUTHORING_CONVERSATION_PROMPT_ID,
            prompt_template_version=AUTHORING_CONVERSATION_PROMPT_VERSION,
            payload=context,
            output_contract=OutputContract(
                schema_id=AUTHORING_CONVERSATION_PROMPT_ID,
                schema_version=AUTHORING_CONVERSATION_PROMPT_VERSION,
            ),
            requested_provider=self._requested_provider,
            output_token_budget=self._output_token_budget,
            correlation_id="course-authoring-conversation",
        )
        model_started_at = perf_counter()
        try:
            inference = await self._gateway.infer_structured(
                request, AuthoringConversationResponse
            )
            candidate = inference.parsed
            response = candidate if isinstance(candidate, AuthoringConversationResponse) else AuthoringConversationResponse.model_validate_json(json.dumps(candidate))
        except Exception as exc:
            if isinstance(exc, ValueError) and str(exc) == "conversation_response_invalid":
                raise
            raise ValueError("conversation_response_invalid") from exc
        model_ms = int((perf_counter() - model_started_at) * 1000)

        post_model_started_at = perf_counter()
        clarification = AuthoringBriefRevisionService._deterministic_clarification(payload)
        required_fields = {item.field for item in clarification.questions}
        readiness = determine_readiness(payload, required_fields)
        result = response.model_copy(update={
            "readiness": readiness,
            "conversation_state": (
                ConversationState.BRIEF_READY
                if readiness is AuthoringReadiness.READY_FOR_CONFIRMATION
                else ConversationState.BRIEF_NEEDS_CLARIFICATION
            ),
        })
        post_model_ms = int((perf_counter() - post_model_started_at) * 1000)
        audit = getattr(inference, "audit", None)
        logger.info(
            "authoring_conversation_timing operation=authoring_conversation "
            "request_id=%s provider=%s model=%s context_build_ms=%s model_ms=%s "
            "post_model_ms=%s total_ms=%s provider_attempt_count=%s input_tokens=%s output_tokens=%s",
            request_id or "unknown",
            getattr(audit, "provider", "unknown"),
            getattr(audit, "model", "unknown"),
            context_build_ms,
            model_ms,
            post_model_ms,
            int((perf_counter() - started_at) * 1000),
            getattr(audit, "attempt_count", "unknown"),
            getattr(getattr(audit, "usage", None), "input_tokens", "unknown"),
            getattr(getattr(audit, "usage", None), "output_tokens", "unknown"),
        )
        return result
