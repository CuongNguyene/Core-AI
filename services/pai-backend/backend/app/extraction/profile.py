from pydantic import BaseModel, ConfigDict, Field

from app.extraction.evidence import EvidenceItem, RelationClaim


class _ProfileEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    entity_id: str | None = Field(default=None, min_length=1)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ExperienceEntity(_ProfileEntity):
    name: str = Field(min_length=1)
    role: str | None = Field(default=None, min_length=1)
    organization: str | None = Field(default=None, min_length=1)


class ProjectEntity(_ProfileEntity):
    name: str = Field(min_length=1)


class ResearchEntity(_ProfileEntity):
    name: str = Field(min_length=1)


class EducationEntity(_ProfileEntity):
    institution: str = Field(min_length=1)
    degree: str | None = Field(default=None, min_length=1)
    field: str | None = Field(default=None, min_length=1)


class PublicationEntity(_ProfileEntity):
    title: str = Field(min_length=1)
    venue: str | None = Field(default=None, min_length=1)


class SkillEntity(_ProfileEntity):
    entity: str = Field(min_length=1)


class CredentialEntity(_ProfileEntity):
    name: str = Field(min_length=1)


class CapabilityActivity(_ProfileEntity):
    statement: str = Field(min_length=1)
    related_entities: list[str] = Field(default_factory=list)


class ProfileFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    code: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    source_claim_ref: str | None = None


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: str = "2.0"
    employment_history: list[ExperienceEntity] = Field(default_factory=list)
    projects: list[ProjectEntity] = Field(default_factory=list)
    research_work: list[ResearchEntity] = Field(default_factory=list)
    education: list[EducationEntity] = Field(default_factory=list)
    publications: list[PublicationEntity] = Field(default_factory=list)
    skills: list[SkillEntity] = Field(default_factory=list)
    credentials: list[CredentialEntity] = Field(default_factory=list)
    activities: list[CapabilityActivity] = Field(default_factory=list)
    findings: list[ProfileFinding] = Field(default_factory=list)


class RelationExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    relations: list[RelationClaim] = Field(default_factory=list)
