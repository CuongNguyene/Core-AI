from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.extraction.evidence import EvidenceEntity


class RelationType(StrEnum):
    USED_IN = "used_in"
    WORKED_ON = "worked_on"
    PUBLISHED = "published"
    STUDIED = "studied"
    DEPLOYED = "deployed"
    LED = "led"
    OWNED = "owned"


class EntityRelation(BaseModel):
    """A source-backed relationship found in full-document context."""

    model_config = ConfigDict(extra="forbid", strict=True)

    subject: str = Field(min_length=1)
    relation: RelationType
    object: str = Field(min_length=1)
    evidence_excerpt: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class EntityRelationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    relations: list[EntityRelation] = Field(default_factory=list)


class SectionEvidenceOutput(BaseModel):
    """Evidence-only output bounded to one section of a document."""

    model_config = ConfigDict(extra="forbid", strict=True)

    entities: list[EvidenceEntity] = Field(default_factory=list)
