import json
import logging
from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.model_gateway.contracts import (
    DocumentInput,
    InferenceAuditMetadata,
    InferenceRequest,
    ModelUsage,
    StructuredInferenceResponse,
    TextInferenceResponse,
)
from app.model_gateway.diagnostics import (
    diagnostic_for_json_parse,
    diagnostic_for_root_type,
    diagnostic_for_validation,
)
from app.model_gateway.errors import (
    InvalidModelJsonError,
    InvalidModelOutputShapeError,
    ModelOutputValidationError,
    OutputSchemaMismatchError,
    StructuredOutputError,
    StructuredOutputFailedError,
)
from app.model_gateway.prompts import ChatMessage, PromptTemplateRegistry
from app.model_gateway.providers import (
    ModelProvider,
    ProviderRegistry,
    ProviderRequest,
    ProviderResponse,
)
from app.model_gateway.routing import ProviderRoute, RoutingPolicy
from app.model_gateway.schema_registry import OutputSchemaRegistry
from app.privacy.contracts import PrivacyGateway, PrivacyInspectionRequest, PrivacyInspectionResult

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class ModelGatewayService:
    def __init__(
        self,
        prompt_templates: PromptTemplateRegistry,
        output_schemas: OutputSchemaRegistry,
        privacy_gateway: PrivacyGateway,
        routing_policy: RoutingPolicy,
        providers: ProviderRegistry,
        model: str,
        max_structured_repair_retries: int = 1,
    ) -> None:
        self._prompt_templates = prompt_templates
        self._output_schemas = output_schemas
        self._privacy_gateway = privacy_gateway
        self._routing_policy = routing_policy
        self._providers = providers
        self._model = model
        self._max_structured_repair_retries = max_structured_repair_retries

    async def infer_text(self, request: InferenceRequest) -> TextInferenceResponse:
        provider, route, privacy_result = await self._prepare(request)
        template = self._prompt_templates.resolve(
            request.prompt_template_id, request.prompt_template_version
        )
        response = await provider.complete(
            self._provider_request(
                template.render(request.payload),
                require_json_object=False,
                output_token_budget=request.output_token_budget,
                temperature=request.temperature,
                document=request.document,
            )
        )
        return TextInferenceResponse(
            content=response.content,
            audit=self._audit_metadata(request, response, route, privacy_result, 1, "succeeded"),
        )

    async def infer_structured(
        self, request: InferenceRequest, output_schema: type[T]
    ) -> StructuredInferenceResponse[T]:
        output_contract = request.output_contract
        if output_contract is None:
            raise OutputSchemaMismatchError("Structured inference requires an output contract")

        registered_schema = self._output_schemas.resolve(
            output_contract.schema_id, output_contract.schema_version
        )
        if registered_schema is not output_schema:
            raise OutputSchemaMismatchError(
                "Requested output schema does not match its registered contract"
            )

        provider, route, privacy_result = await self._prepare(request)
        template = self._prompt_templates.resolve(
            request.prompt_template_id, request.prompt_template_version
        )
        repair_reason: str | None = None

        for attempt in range(1, self._max_structured_repair_retries + 2):
            response = await provider.complete(
                self._provider_request(
                    template.render(request.payload, repair_reason=repair_reason),
                    require_json_object=True,
                    output_token_budget=request.output_token_budget,
                    temperature=request.temperature,
                    json_schema=output_schema.model_json_schema(),
                    document=request.document,
                    response_model=output_schema,
                )
            )
            try:
                if response.structured_output is not None:
                    if type(response.structured_output) is not output_schema:
                        raise StructuredOutputFailedError("provider_parsed_schema_mismatch")
                    parsed = response.structured_output
                else:
                    parsed = self._validate_structured_output(
                        response.content,
                        output_schema,
                        output_contract.strict,
                        provider_finish_reason=response.finish_reason,
                    )
            except StructuredOutputFailedError:
                raise
            except StructuredOutputError as exc:
                if attempt == self._max_structured_repair_retries + 1:
                    raise StructuredOutputFailedError(
                        exc.category, diagnostic=exc.diagnostic
                    ) from exc
                repair_reason = exc.category
                if exc.repair_hint:
                    repair_reason = f"{repair_reason}; {exc.repair_hint}"
                continue

            return StructuredInferenceResponse(
                parsed=parsed,
                audit=self._audit_metadata(
                    request, response, route, privacy_result, attempt, "succeeded"
                ),
            )

        raise AssertionError("Structured inference always returns or raises")

    async def _prepare(
        self, request: InferenceRequest
    ) -> tuple[ModelProvider, ProviderRoute, PrivacyInspectionResult]:
        privacy_result = await self._privacy_gateway.inspect(
            PrivacyInspectionRequest(
                purpose=request.purpose,
                data_classification=request.data_classification,
                payload=request.payload,
                requested_provider=request.requested_provider,
            )
        )
        route = self._routing_policy.route(request, privacy_result)
        return self._providers.resolve(route.provider_id), route, privacy_result

    def _provider_request(
        self,
        messages: Sequence[ChatMessage],
        require_json_object: bool,
        output_token_budget: int | None = None,
        temperature: float | None = None,
        json_schema: dict[str, object] | None = None,
        document: DocumentInput | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> ProviderRequest:
        request = ProviderRequest(
            model=self._model,
            messages=list(messages),
            require_json_object=require_json_object,
            document=document,
            response_model=response_model,
        )
        if output_token_budget is not None:
            request = request.model_copy(update={"max_tokens": output_token_budget})
        if temperature is not None:
            request = request.model_copy(update={"temperature": temperature})
        if json_schema is not None:
            request = request.model_copy(update={"json_schema": json_schema})
        return request

    def _validate_structured_output(
        self,
        raw_content: str,
        output_schema: type[T],
        strict: bool,
        provider_finish_reason: str | None = None,
    ) -> T:
        try:
            payload, normalized_content = self._parse_json_object(raw_content)
        except json.JSONDecodeError as exc:
            logger.warning(
                "model_output_invalid_json schema=%s content_length=%s leading_kind=%s",
                output_schema.__name__,
                len(raw_content),
                self._leading_kind(raw_content),
            )
            raise InvalidModelJsonError(
                "Model response is not valid JSON",
                repair_hint="escape control characters inside JSON strings",
                diagnostic=diagnostic_for_json_parse(
                    content_length=len(raw_content),
                    provider_finish_reason=provider_finish_reason,
                ),
            ) from exc

        if not isinstance(payload, dict):
            raise InvalidModelOutputShapeError(
                "Model response must be a JSON object",
                diagnostic=diagnostic_for_root_type(
                    content_length=len(raw_content),
                    provider_finish_reason=provider_finish_reason,
                ),
            )

        try:
            return output_schema.model_validate_json(normalized_content, strict=strict)
        except ValidationError as exc:
            logger.warning(
                "model_output_validation_failed schema=%s error_types=%s error_paths=%s",
                output_schema.__name__,
                [error.get("type") for error in exc.errors()],
                [".".join(str(part) for part in error.get("loc", ())) for error in exc.errors()],
            )
            paths = [".".join(str(part) for part in error.get("loc", ())) for error in exc.errors()]
            types = [str(error.get("type")) for error in exc.errors()]
            evidence_hint = ""
            if output_schema.__name__.startswith("JDRequirementExtractionOutputV2"):
                evidence_hint = (
                    "; every JD requirement needs requirement_id, statement, evidence_status=supported, "
                    "source_excerpt and source_locator; do not emit unknown or insufficient rows"
                )
            elif all(error_type == "value_error" for error_type in types):
                evidence_hint = (
                    "; supported claims need non-null value and non-empty source_excerpt; "
                    "unknown/insufficient claims need null value and null source_excerpt"
                )
            raise ModelOutputValidationError(
                "Model response does not match output schema",
                repair_hint=f"paths={','.join(paths)}; types={','.join(types)}{evidence_hint}",
                diagnostic=diagnostic_for_validation(
                    exc.errors(),
                    content_length=len(raw_content),
                    provider_finish_reason=provider_finish_reason,
                ),
            ) from exc

    @staticmethod
    def _parse_json_object(raw_content: str) -> tuple[object, str]:
        try:
            return json.loads(raw_content), raw_content
        except json.JSONDecodeError as original_error:
            repaired = ModelGatewayService._repair_common_json_errors(raw_content)
            if repaired == raw_content:
                raise original_error
            return json.loads(repaired), repaired

    @staticmethod
    def _repair_common_json_errors(content: str) -> str:
        """Apply only syntax-preserving repairs commonly emitted by LLMs."""
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(lines[1:-1]).strip()

        escaped_controls: list[str] = []
        in_string = False
        escaping = False
        for character in stripped:
            if in_string and not escaping and character in {"\n", "\r", "\t"}:
                escaped_controls.append({"\n": "\\n", "\r": "\\r", "\t": "\\t"}[character])
                continue
            escaped_controls.append(character)
            if escaping:
                escaping = False
            elif character == "\\":
                escaping = True
            elif character == '"':
                in_string = not in_string

        without_trailing_commas: list[str] = []
        in_string = False
        escaping = False
        index = 0
        repaired = "".join(escaped_controls)
        while index < len(repaired):
            character = repaired[index]
            if not in_string and character == ",":
                next_index = index + 1
                while next_index < len(repaired) and repaired[next_index].isspace():
                    next_index += 1
                if next_index < len(repaired) and repaired[next_index] in "}]":
                    index += 1
                    continue
            without_trailing_commas.append(character)
            if escaping:
                escaping = False
            elif character == "\\":
                escaping = True
            elif character == '"':
                in_string = not in_string
            index += 1

        return "".join(without_trailing_commas)

    @staticmethod
    def _leading_kind(content: str) -> str:
        first = content.lstrip()[:1]
        if not first:
            return "empty"
        if first == "{":
            return "object"
        if first == "[":
            return "array"
        if first == "`":
            return "fence"
        if first == "<":
            return "tag"
        return "text"

    def _audit_metadata(
        self,
        request: InferenceRequest,
        response: ProviderResponse,
        route: ProviderRoute,
        privacy_result: PrivacyInspectionResult,
        attempt_count: int,
        outcome: str,
    ) -> InferenceAuditMetadata:
        output_contract = request.output_contract
        return InferenceAuditMetadata(
            provider=response.provider,
            model=response.model,
            requested_model=response.requested_model or self._model,
            provider_response_id=response.provider_response_id,
            model_revision=response.model_revision,
            protocol=response.protocol,
            deployment_type=response.deployment_type,
            endpoint_origin=response.endpoint_origin,
            data_boundary=response.data_boundary,
            prompt_template_id=request.prompt_template_id,
            prompt_template_version=request.prompt_template_version,
            output_schema_id=output_contract.schema_id if output_contract else None,
            output_schema_version=output_contract.schema_version if output_contract else None,
            policy_version=privacy_result.policy_version,
            correlation_id=request.correlation_id,
            routing_decision=route.decision,
            attempt_count=attempt_count,
            provider_attempt_count=response.provider_attempt_count,
            latency_ms=response.latency_ms,
            usage=ModelUsage(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                cached_tokens=response.cached_tokens,
            ),
            outcome=outcome,
            finish_reason=response.finish_reason,
        )
