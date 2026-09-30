from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.capability_analysis.schemas import PreliminaryPriority


class LearnerContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role: str | None
    experience_level: str | None


class LearningNeedCompetency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    name: str | None
    description: str | None


class LearningNeedCurrentState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    level: str | None
    evidence_refs: list[str]


class LearningNeedTargetState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    level: str | None
    expected_behaviors: list[str]


type LearningNeedGapType = Literal[
    "skill_gap",
    "experience_gap",
    "education_gap",
    "credential_gap",
    "qualification_gap",
    "unresolved_gap",
]


class LearningNeedGap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    type: LearningNeedGapType
    description: str = Field(min_length=1)


class LearningNeedEligibility(StrEnum):
    READY_FOR_LEARNING = "READY_FOR_LEARNING"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    NON_LEARNING_RESOLUTION = "NON_LEARNING_RESOLUTION"
    UNRESOLVED = "UNRESOLVED"


class LearningNeedResolution(StrEnum):
    LEARNING = "learning"
    VERIFICATION = "verification"
    CREDENTIAL = "credential"
    EXPERIENCE_EXPOSURE = "experience_exposure"
    ASSESSMENT = "assessment"
    NON_LEARNING = "non_learning"
    UNRESOLVED = "unresolved"


class LearningNeedProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    analysis_id: str = Field(min_length=1)
    analysis_version: int = Field(ge=1)
    target_id: str = Field(min_length=1)
    target_version: str = Field(min_length=1)
    source_profile_id: str = Field(min_length=1)
    source_profile_version: int = Field(ge=1)
    evidence_refs: list[str]
    transformation: Literal["learning-need-profile-v1"]
    policy_version: str = "learning_need_projection@0.1"


class LearningNeedProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    candidate_reference: UUID
    target_reference: str = Field(min_length=1)
    learner_context: LearnerContext
    competency: LearningNeedCompetency
    current_state: LearningNeedCurrentState
    target_state: LearningNeedTargetState
    gap: LearningNeedGap
    missing_knowledge: list[str]
    learning_constraints: dict[str, object]
    priority: PreliminaryPriority
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_gap_refs: list[str] = Field(min_length=1)
    provenance: LearningNeedProvenance
    assessment_status: str | None = None
    requirement_reference: str | None = None
    learning_eligibility: LearningNeedEligibility = LearningNeedEligibility.UNRESOLVED
    resolution_type: LearningNeedResolution = LearningNeedResolution.UNRESOLVED
    usage_mode: str = "official"
    warning_codes: list[str] = Field(default_factory=list)
    projection_reason_code: str = "legacy_learning_need_projection"
