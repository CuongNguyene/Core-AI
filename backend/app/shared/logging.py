import logging
import sys
from collections.abc import Mapping

import structlog
from structlog.typing import EventDict, WrappedLogger

SENSITIVE_FIELD_MARKERS = (
    "api_key",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "document_content",
    "raw_content",
    "prompt",
)
REDACTED_VALUE = "[REDACTED]"


def redact_sensitive_values(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Remove values whose field names may contain credentials or raw content."""

    return {
        key: REDACTED_VALUE if _is_sensitive_key(key) else _redact_nested(value)
        for key, value in event_dict.items()
    }


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format="%(message)s", level=log_level.upper(), stream=sys.stdout, force=True
    )
    structlog.configure(
        processors=[
            redact_sensitive_values,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _is_sensitive_key(key: str) -> bool:
    normalized_key = key.lower()
    return any(marker in normalized_key for marker in SENSITIVE_FIELD_MARKERS)


def _redact_nested(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED_VALUE
            if _is_sensitive_key(str(key))
            else _redact_nested(nested_value)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_nested(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_nested(item) for item in value)
    return value
