from app.model_gateway.diagnostics import (
    diagnostic_for_json_parse,
    diagnostic_for_root_type,
    diagnostic_for_validation,
)


def test_malformed_json_is_classified_without_content() -> None:
    diagnostic = diagnostic_for_json_parse(
        content_length=12, provider_finish_reason="stop"
    )

    assert diagnostic.failure_code == "JSON_PARSE_FAILED"
    assert diagnostic.json_parse_status == "failed"
    assert diagnostic.validation_errors == []
    assert "raw_content" not in diagnostic.model_dump()


def test_missing_field_is_classified_with_structured_path() -> None:
    diagnostic = diagnostic_for_validation(
        [{"type": "missing", "loc": ("education", 1), "msg": "Field required"}],
        content_length=20,
        provider_finish_reason="stop",
    )

    assert diagnostic.failure_code == "MISSING_REQUIRED_FIELD"
    assert diagnostic.validation_errors[0] == {
        "path": ["education", 1],
        "code": "missing",
        "message_code": "field_required",
    }


def test_enum_and_type_errors_are_distinguished() -> None:
    enum = diagnostic_for_validation(
        [{"type": "enum", "loc": ("skills", 0, "evidence_type"), "msg": "bad"}],
        content_length=4,
        provider_finish_reason="stop",
    )
    wrong_type = diagnostic_for_validation(
        [{"type": "string_type", "loc": ("skills",), "msg": "bad"}],
        content_length=4,
        provider_finish_reason="stop",
    )

    assert enum.failure_code == "INVALID_ENUM_VALUE"
    assert wrong_type.failure_code == "INVALID_FIELD_TYPE"


def test_schema_length_constraint_is_not_reported_as_a_business_invariant() -> None:
    diagnostic = diagnostic_for_validation(
        [{"type": "string_too_long", "loc": ("experience", 0, "source_excerpt")}],
        content_length=4,
        provider_finish_reason="stop",
    )

    assert diagnostic.failure_code == "SCHEMA_CONSTRAINT_VIOLATION"


def test_value_error_is_business_invariant_and_length_is_truncation() -> None:
    diagnostic = diagnostic_for_validation(
        [{"type": "value_error", "loc": ("skills", 0), "msg": "bad"}],
        content_length=99,
        provider_finish_reason="length",
    )

    assert diagnostic.failure_code == "TRUNCATED_OUTPUT"
    assert diagnostic.possible_truncation is True
    assert diagnostic.provider_finish_reason == "length"


def test_root_type_diagnostic_has_no_provider_output() -> None:
    diagnostic = diagnostic_for_root_type(content_length=3, provider_finish_reason=None)

    assert diagnostic.failure_code == "ROOT_TYPE_INVALID"
    assert diagnostic.schema_validation_status == "failed"
    assert diagnostic.content_length == 3
