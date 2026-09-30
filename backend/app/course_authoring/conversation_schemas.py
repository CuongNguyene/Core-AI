from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuthoringReadiness(StrEnum):
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"


class ConversationState(StrEnum):
    BRIEF_NEEDS_CLARIFICATION = "BRIEF_NEEDS_CLARIFICATION"
    BRIEF_READY = "BRIEF_READY"


class ConversationInteractionType(StrEnum):
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTI_CHOICE = "MULTI_CHOICE"
    NUMERIC_INPUT = "NUMERIC_INPUT"
    TEXT_INPUT = "TEXT_INPUT"


class AuthoringConversationOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    value: str = Field(min_length=1)
    label: str = Field(min_length=1)


class AuthoringConversationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    field: str = Field(min_length=1)
    type: ConversationInteractionType
    prompt: str = Field(min_length=1)
    options: tuple[AuthoringConversationOption, ...] = Field(default_factory=tuple)
    required: bool = True


class AuthoringProposedChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    field: Literal[
        "training_goal",
        "desired_outcomes",
        "prerequisites",
        "constraints",
        "learning_horizon",
        "expected_learning_effort",
        "excluded_scope",
        "emphasis",
    ]
    old_value: object | None = None
    proposed_value: object
    reason: str = Field(min_length=1)


class AuthoringConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    assistant_message: str = Field(min_length=1)
    conversation_state: ConversationState
    questions: tuple[AuthoringConversationQuestion, ...] = Field(default_factory=tuple)
    proposed_changes: tuple[AuthoringProposedChange, ...] = Field(default_factory=tuple)
    unresolved_items: tuple[str, ...] = Field(default_factory=tuple)
    readiness: AuthoringReadiness

    @model_validator(mode="after")
    def validate_readiness_shape(self) -> "AuthoringConversationResponse":
        if self.readiness is AuthoringReadiness.NEEDS_CLARIFICATION and self.conversation_state is ConversationState.BRIEF_READY:
            raise ValueError("conversation_state_readiness_mismatch")
        if self.readiness is AuthoringReadiness.READY_FOR_CONFIRMATION and self.conversation_state is ConversationState.BRIEF_NEEDS_CLARIFICATION:
            raise ValueError("conversation_state_readiness_mismatch")
        return self
