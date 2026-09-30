from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.extraction.locators import SourceLocator


class EvidenceContext(StrEnum):
    MENTIONED = "mentioned"
    USED_IN_EMPLOYMENT = "used_in_employment"
    STUDIED = "studied"
    USED_IN_PROJECT = "used_in_project"
    USED_IN_RESEARCH = "used_in_research"
    USED_IN_PRODUCTION = "used_in_production"
    OWNED_SYSTEM = "owned_system"
    LED_TEAM = "led_team"
    CREDENTIALED = "credentialed"
    UNKNOWN = "unknown"


class RelationEntityType(StrEnum):
    SKILL = "skill"
    EMPLOYMENT = "employment"
    PROJECT = "project"
    RESEARCH = "research"
    EDUCATION = "education"
    PUBLICATION = "publication"


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    context: EvidenceContext
    usage: str | None = Field(default=None, min_length=1)
    source_excerpt: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)
    source_type: str = Field(default="section", min_length=1)
    source_locator: SourceLocator | None = None
    original_evidence_type: str | None = Field(default=None, min_length=1)


class EvidenceEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    original_value: str | None = None
    canonical_value: str | None = None


class EvidenceExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    entities: list[EvidenceEntity] = Field(default_factory=list)


class RelationClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    entity: str = Field(min_length=1)
    entity_type: RelationEntityType
    context: EvidenceContext
    usage: str | None = Field(default=None, min_length=1)
    confidence: float = Field(ge=0, le=1)
    source_excerpt: str = Field(min_length=1, max_length=500)
    source_locator: SourceLocator | None = None
