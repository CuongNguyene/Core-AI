"""Stable, non-sensitive structured-output validation diagnostics."""

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field


class StructuredOutputDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    failure_stage: str = "structured_output_validation"
    failure_code: str
    json_parse_status: str
    schema_validation_status: str
    validation_errors: list[dict[str, object]] = Field(default_factory=list)
    provider_finish_reason: str | None = None
    content_length: int = Field(ge=0)
    possible_truncation: bool = False


def _base(
    *,
    code: str,
    content_length: int,
    provider_finish_reason: str | None,
    json_status: str,
    schema_status: str,
    errors: list[dict[str, object]] | None = None,
) -> StructuredOutputDiagnostic:
    return StructuredOutputDiagnostic(
        failure_code=code,
        json_parse_status=json_status,
        schema_validation_status=schema_status,
        validation_errors=errors or [],
        provider_finish_reason=provider_finish_reason,
        content_length=content_length,
        possible_truncation=provider_finish_reason == "length",
    )


def diagnostic_for_json_parse(
    *, content_length: int, provider_finish_reason: str | None
) -> StructuredOutputDiagnostic:
    return _base(
        code=(
            "TRUNCATED_OUTPUT"
            if provider_finish_reason == "length"
            else "JSON_PARSE_FAILED"
        ),
        content_length=content_length,
        provider_finish_reason=provider_finish_reason,
        json_status="failed",
        schema_status="not_run",
    )


def diagnostic_for_root_type(
    *, content_length: int, provider_finish_reason: str | None
) -> StructuredOutputDiagnostic:
    return _base(
        code=(
            "TRUNCATED_OUTPUT"
            if provider_finish_reason == "length"
            else "ROOT_TYPE_INVALID"
        ),
        content_length=content_length,
        provider_finish_reason=provider_finish_reason,
        json_status="success",
        schema_status="failed",
    )


def _message_code(error_type: str) -> str:
    return {
        "missing": "field_required",
        "enum": "enum_value_invalid",
        "extra_forbidden": "extra_field",
        "value_error": "claim_invariant",
    }.get(error_type, "field_validation")


def _failure_code(error_types: set[str], finish_reason: str | None) -> str:
    if finish_reason == "length":
        return "TRUNCATED_OUTPUT"
    if "missing" in error_types:
        return "MISSING_REQUIRED_FIELD"
    if "enum" in error_types:
        return "INVALID_ENUM_VALUE"
    if "extra_forbidden" in error_types:
        return "EXTRA_FIELD"
    if "value_error" in error_types:
        return "CLAIM_INVARIANT_VIOLATION"
    if any(error_type.endswith(("_too_long", "_too_short")) for error_type in error_types):
        return "SCHEMA_CONSTRAINT_VIOLATION"
    if any(error_type.endswith("_type") for error_type in error_types):
        return "INVALID_FIELD_TYPE"
    return "UNKNOWN_SCHEMA_VALIDATION_FAILURE"


def diagnostic_for_validation(
    errors: Sequence[Mapping[str, object]],
    *,
    content_length: int,
    provider_finish_reason: str | None,
) -> StructuredOutputDiagnostic:
    safe_errors: list[dict[str, object]] = []
    error_types: set[str] = set()
    for error in errors:
        error_type = str(error.get("type", "unknown"))
        error_types.add(error_type)
        location = error.get("loc", ())
        path = list(location) if isinstance(location, (tuple, list)) else []
        safe_errors.append(
            {
                "path": path,
                "code": error_type,
                "message_code": _message_code(error_type),
            }
        )
    return _base(
        code=_failure_code(error_types, provider_finish_reason),
        content_length=content_length,
        provider_finish_reason=provider_finish_reason,
        json_status="success",
        schema_status="failed",
        errors=safe_errors,
    )
