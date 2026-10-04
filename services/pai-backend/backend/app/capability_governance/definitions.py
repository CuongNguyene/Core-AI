"""Immutable canonical capability definitions and definition lifecycle."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.capability_governance.errors import InvalidLifecycleTransitionError
from app.capability_governance.identity import CanonicalCapabilityRef


class CapabilityDefinitionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class CapabilityDeprecationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    actor_ref: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("actor_ref", "reason")
    @classmethod
    def reject_blank_or_trimmed_values(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("deprecation values must be non-blank and exact")
        return value


class CapabilityDefinition(BaseModel):
    """A versioned human-authored definition for one stable capability ref."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    canonical_ref: CanonicalCapabilityRef
    label: str = Field(min_length=1, max_length=160)
    definition: str = Field(min_length=1, max_length=4000)
    status: CapabilityDefinitionStatus = CapabilityDefinitionStatus.DRAFT
    replacement_ref: CanonicalCapabilityRef | None = None
    deprecation: CapabilityDeprecationRecord | None = None

    @property
    def identity_key(self) -> CanonicalCapabilityRef:
        """Return identity separately from this release's descriptive content."""
        return self.canonical_ref

    @field_validator("label", "definition")
    @classmethod
    def reject_blank_or_trimmed_values(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("definition text must be non-blank and exact")
        return value

    @model_validator(mode="after")
    def validate_lifecycle_metadata(self) -> "CapabilityDefinition":
        if self.status is CapabilityDefinitionStatus.DEPRECATED:
            if self.deprecation is None:
                raise ValueError("deprecated definitions require a deprecation record")
        elif self.deprecation is not None or self.replacement_ref is not None:
            raise ValueError("replacement and deprecation metadata require deprecated status")

        if self.replacement_ref == self.canonical_ref:
            raise ValueError("a capability cannot replace itself")
        return self


def deprecate_capability_definition(
    definition: CapabilityDefinition,
    *,
    actor_ref: str,
    reason: str,
    replacement_ref: CanonicalCapabilityRef | None = None,
) -> CapabilityDefinition:
    if definition.status is not CapabilityDefinitionStatus.ACTIVE:
        raise InvalidLifecycleTransitionError("invalid_definition_transition")

    return CapabilityDefinition.model_validate(
        {
            **definition.model_dump(mode="python"),
            "status": CapabilityDefinitionStatus.DEPRECATED,
            "replacement_ref": replacement_ref,
            "deprecation": CapabilityDeprecationRecord(actor_ref=actor_ref, reason=reason),
        }
    )
