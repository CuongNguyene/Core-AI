from collections.abc import Iterable, Mapping

from .brief_revision_schemas import BriefRevisionPayload
from .conversation_schemas import AuthoringReadiness

MAX_RECENT_TURNS = 6


def _is_missing(value: object) -> bool:
    return value is None or value == "" or value == () or value == []


def determine_readiness(
    payload: BriefRevisionPayload, required_fields: Iterable[str]
) -> AuthoringReadiness:
    missing = any(
        _is_missing(getattr(payload, field, None))
        for field in required_fields
    )
    return (
        AuthoringReadiness.NEEDS_CLARIFICATION
        if missing
        else AuthoringReadiness.READY_FOR_CONFIRMATION
    )


def build_authoring_conversation_context(
    payload: BriefRevisionPayload,
    recent_turns: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    turns = list(recent_turns)[-MAX_RECENT_TURNS:]
    return {
        "structured_state": payload.model_dump(mode="json"),
        "recent_turns": turns,
    }
