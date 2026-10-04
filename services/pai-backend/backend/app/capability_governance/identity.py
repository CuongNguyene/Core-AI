"""Distinct source and canonical capability identity value objects.

These contracts describe identity only. A CapabilityIdentityPair does not
represent a reviewed or approved semantic mapping.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


class CanonicalCapabilityRef(RootModel[str]):
    """Version-independent canonical identity serialized as one string."""

    model_config = ConfigDict(strict=True, frozen=True)

    root: str = Field(pattern=r"^capability:[a-z][a-z0-9_]{1,63}:[a-z][a-z0-9_]{1,127}$")

    @classmethod
    def parse(cls, value: str) -> "CanonicalCapabilityRef":
        """Parse a canonical ref without normalizing its input."""
        return cls(value)

    @property
    def namespace_key(self) -> str:
        return self.root.split(":", maxsplit=2)[1]

    @property
    def semantic_key(self) -> str:
        return self.root.split(":", maxsplit=2)[2]

    def __str__(self) -> str:
        return self.root


class SourceSemanticKind(StrEnum):
    """Source-owned semantic entity kinds supported by the identity layer."""

    ROLE_REQUIREMENT = "role_requirement"
    LEARNING_NEED_COMPETENCY = "learning_need_competency"
    LEARNING_PATH_TARGET = "learning_path_target"
    COURSE_LEARNING_OUTCOME = "course_learning_outcome"
    COURSE_DIRECT_CLAIM = "course_direct_claim"
    CANDIDATE_CONCEPT = "candidate_concept"
    PROVIDER_CLASSIFICATION = "provider_classification"


class SourceSemanticRef(BaseModel):
    """Stable identity owned by a source domain or provider."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_namespace: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_.-]{0,63}$",
    )
    entity_kind: SourceSemanticKind
    source_id: str = Field(min_length=1, max_length=512)
    source_version: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("source_id", "source_version")
    @classmethod
    def reject_surrounding_whitespace(cls, value: str | None) -> str | None:
        if value is not None and value != value.strip():
            raise ValueError("source identity values must not have surrounding whitespace")
        return value


class CapabilityIdentityPair(BaseModel):
    """A source identity and optional canonical identity, without approval."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_ref: SourceSemanticRef
    canonical_capability_ref: CanonicalCapabilityRef | None = None
