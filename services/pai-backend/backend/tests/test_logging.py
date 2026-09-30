from app.shared.logging import redact_sensitive_values


def test_sensitive_logging_fields_are_redacted() -> None:
    event = {
        "event": "request_failed",
        "api_key": "secret-value",
        "nested": {"authorization": "Bearer secret-value", "attempt": 1},
        "path": "/health/ready",
    }

    redacted = redact_sensitive_values(None, "error", event)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["authorization"] == "[REDACTED]"
    assert redacted["nested"]["attempt"] == 1
    assert redacted["path"] == "/health/ready"
