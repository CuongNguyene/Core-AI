"""Deterministic course-supply contracts.

These schemas describe course facts and manually governed capability coverage.
They deliberately do not select, rank, score, or generate recommendations.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CourseSourceType(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class CourseProfileStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class CourseAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class CoverageType(StrEnum):
    DIRECT = "direct"
    SUPPORTING = "supporting"


class CourseProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    kind: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_field: str | None = Field(default=None, min_length=1)
    source_locator: str | None = Field(default=None, min_length=1)
    evidence_text: str | None = Field(default=None, min_length=1)
    method: str = Field(min_length=1)


class CourseCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    capability_ref: str = Field(min_length=1)
    coverage_type: CoverageType
    target_level: str | None = Field(default=None, min_length=1)
    provenance: list[CourseProvenance] = Field(min_length=1)


class CoursePrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    kind: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    minimum_level: str | None = Field(default=None, min_length=1)
    provenance: list[CourseProvenance] = Field(default_factory=list)


class ExternalCourse(BaseModel):
    """Provider-owned catalog facts, without Core-AI capability decisions."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    provider_ref: str = Field(min_length=1)
    provider_course_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    delivery_mode: str | None = Field(default=None, min_length=1)
    language: str | None = Field(default=None, min_length=1)
    availability: CourseAvailability = CourseAvailability.UNKNOWN
    course_url: str | None = Field(default=None, min_length=1)
    provenance: list[CourseProvenance] = Field(min_length=1)


class NormalizedCourseCandidate(BaseModel):
    """Unified course-supply view consumed by COURSE-REC-01B."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    course_ref: str = Field(min_length=1)
    source_type: CourseSourceType
    source_system: str = Field(min_length=1)
    provider_ref: str | None = Field(default=None, min_length=1)
    provider_course_id: str | None = Field(default=None, min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    capabilities: list[CourseCapability] = Field(default_factory=list)
    prerequisites: list[CoursePrerequisite] = Field(default_factory=list)
    target_level: str | None = Field(default=None, min_length=1)
    duration_minutes: int | None = Field(default=None, ge=0)
    delivery_mode: str | None = Field(default=None, min_length=1)
    language: str | None = Field(default=None, min_length=1)
    availability: CourseAvailability = CourseAvailability.UNKNOWN
    provenance: list[CourseProvenance] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity(self) -> "NormalizedCourseCandidate":
        if self.source_type is CourseSourceType.INTERNAL:
            if self.provider_ref is not None or self.provider_course_id is not None:
                raise ValueError("internal normalized candidates cannot contain provider identity")
        elif not self.provider_ref or not self.provider_course_id:
            raise ValueError("external normalized candidates require provider identity")
        return self


class CourseCapabilityProfile(BaseModel):
    """Core semantic profile describing what a course develops."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=1)
    course_ref: str = Field(min_length=1)
    source_type: CourseSourceType
    source_system: str = Field(min_length=1)
    provider_ref: str | None = Field(default=None, min_length=1)
    provider_course_id: str | None = Field(default=None, min_length=1)
    title_snapshot: str = Field(min_length=1)
    description_snapshot: str | None = None
    capabilities: list[CourseCapability] = Field(min_length=1)
    prerequisites: list[CoursePrerequisite] = Field(default_factory=list)
    target_level: str | None = Field(default=None, min_length=1)
    duration_minutes: int | None = Field(default=None, ge=0)
    delivery_mode: str | None = Field(default=None, min_length=1)
    language: str | None = Field(default=None, min_length=1)
    availability: CourseAvailability = CourseAvailability.UNKNOWN
    status: CourseProfileStatus
    provenance: list[CourseProvenance] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity(self) -> "CourseCapabilityProfile":
        if self.source_type is CourseSourceType.INTERNAL:
            if self.provider_ref is not None or self.provider_course_id is not None:
                raise ValueError("internal course profiles cannot contain provider identity")
        elif not self.provider_ref or not self.provider_course_id:
            raise ValueError("external course profiles require provider identity")

        capability_refs = [item.capability_ref for item in self.capabilities]
        if len(capability_refs) != len(set(capability_refs)):
            raise ValueError("duplicate capability entries are not allowed")
        return self

    def to_normalized_candidate(self) -> NormalizedCourseCandidate:
        return NormalizedCourseCandidate(
            course_ref=self.course_ref,
            source_type=self.source_type,
            source_system=self.source_system,
            provider_ref=self.provider_ref,
            provider_course_id=self.provider_course_id,
            title=self.title_snapshot,
            description=self.description_snapshot,
            capabilities=list(self.capabilities),
            prerequisites=list(self.prerequisites),
            target_level=self.target_level,
            duration_minutes=self.duration_minutes,
            delivery_mode=self.delivery_mode,
            language=self.language,
            availability=self.availability,
            provenance=list(self.provenance),
        )
