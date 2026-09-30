"""Typed, research-only contracts for instructional design before content generation."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class ResearchProvenanceType(StrEnum):
    RESEARCH_FIXTURE = "research_fixture"


class ArtifactSource(StrEnum):
    RESEARCHER_AUTHORED = "researcher_authored"
    MODEL_PROPOSED = "model_proposed"


class CognitiveProcess(StrEnum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class KnowledgeDimension(StrEnum):
    FACTUAL = "factual"
    CONCEPTUAL = "conceptual"
    PROCEDURAL = "procedural"
    METACOGNITIVE = "metacognitive"


class PrerequisiteStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    UNKNOWN = "unknown"


class PrerequisiteBasis(StrEnum):
    RESEARCHER_AUTHORED = "researcher_authored"
    APPROVED_FRAMEWORK = "approved_framework"
    SOURCE_BACKED = "source_backed"
    MODEL_PROPOSED = "model_proposed"


class PrerequisiteClassification(StrEnum):
    REQUIRED_PREREQUISITE = "required_prerequisite"
    HELPFUL_BACKGROUND = "helpful_background"
    NOT_REQUIRED = "not_required"


class PrerequisiteDisposition(StrEnum):
    """Planning disposition, distinct from verification status."""

    ENTRY_PREREQUISITE = "entry_prerequisite"
    IN_COURSE_SUPPORT = "in_course_support"
    NOT_REQUIRED = "not_required"


class InstructionalPattern(StrEnum):
    EXPLANATION = "explanation"
    DEMONSTRATION = "demonstration"
    WORKED_EXAMPLE = "worked_example"
    GUIDED_PRACTICE = "guided_practice"
    SCENARIO = "scenario"
    INDEPENDENT_PRACTICE = "independent_practice"
    REFLECTION = "reflection"


class DesignFindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class AssessmentRole(StrEnum):
    """Instructional purpose of an assessment artifact."""

    FORMATIVE = "formative"
    SUMMATIVE = "summative"


class AssessmentDependencyRole(StrEnum):
    REQUIRED_CAPABILITY = "required_capability"
    SUPPORTING_DEPENDENCY = "supporting_dependency"


class AssessmentDependencyStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"


class DependencySourceType(StrEnum):
    TYPED_REQUIRED_CAPABILITY = "typed_required_capability"
    LEGACY_COMPATIBILITY = "legacy_compatibility"
    DEPENDENCY_CANDIDATE = "dependency_candidate"


class PlanningWarningType(StrEnum):
    SCOPE_TIME_CONFLICT = "scope_time_conflict"


class PlanningWarningDecision(StrEnum):
    PRIORITIZED_CORE_OBJECTIVES = "prioritized_core_objectives"


class PrerequisiteStructuralReviewStatus(StrEnum):
    STRUCTURALLY_SUPPORTED = "structurally_supported"
    INSUFFICIENT_RATIONALE = "insufficient_rationale"
    UNRESOLVED_REFERENCE = "unresolved_reference"
    NOT_APPLICABLE = "not_applicable"


class ResearchCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str | None = None
    name: str = Field(min_length=1)
    target_context: str | None = None


class LearnerState(BaseModel):
    """Observed/declared research input; `unknown` never asserts a deficiency."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    known: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class ResearchConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    estimated_total_minutes: int | None = Field(default=None, gt=0)
    language: str | None = None
    audience_notes: list[str] = Field(default_factory=list)


class ResearchBriefProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    type: Literal[ResearchProvenanceType.RESEARCH_FIXTURE] = ResearchProvenanceType.RESEARCH_FIXTURE
    authored_by: str | None = None
    created_at: datetime | None = None


class ArtifactProvenance(BaseModel):
    """Records whether a research artifact is authored or only a model candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source: ArtifactSource
    provisional: bool = False
    assumption_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def model_proposals_remain_provisional(self) -> "ArtifactProvenance":
        if self.source is ArtifactSource.MODEL_PROPOSED and not self.provisional:
            raise ValueError("model_proposed artifacts must remain provisional")
        return self


class ResearchLearningBrief(BaseModel):
    """Controlled research fixture, deliberately separate from production role profiles."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    capability: ResearchCapability
    learner_state: LearnerState
    desired_performances: list[str] = Field(min_length=1)
    constraints: ResearchConstraints
    provenance: ResearchBriefProvenance


class LearningObjectiveSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    brief_id: str = Field(min_length=1)
    performance: str = Field(min_length=1)
    cognitive_process: CognitiveProcess
    knowledge_dimension: KnowledgeDimension
    conditions: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    prerequisite_refs: list[str] = Field(default_factory=list)
    capability_refs: list[str] = Field(default_factory=list)
    provenance: ArtifactProvenance


class EvidenceCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    criterion: str = Field(min_length=1)
    rationale: str | None = None


class AssessmentTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    task_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    conditions: list[str] = Field(default_factory=list)


class RubricDimension(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    criterion: str = Field(min_length=1)
    performance_levels: list[str] = Field(default_factory=list)


class ScoringSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    rubric_dimensions: list[RubricDimension] = Field(default_factory=list)
    mastery_rule: str | None = None


class AssessmentCapabilityRequirement(BaseModel):
    """A capability/dependency required by an assessment, never an artifact ID."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(
        min_length=1,
        validation_alias=AliasChoices("name", "capability"),
    )
    objective_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None

    @property
    def capability(self) -> str:
        """Compatibility accessor for pre-0.3.1 in-process callers."""

        return self.name


class AssessmentDependencyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    capability: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    required_for_refs: list[str] = Field(default_factory=list)


class DependencySource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    type: DependencySourceType
    source_ref: str = Field(min_length=1)
    original_value: str = Field(min_length=1)


class DependencyProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    sources: list[DependencySource] = Field(min_length=1)


class CanonicalAssessmentDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    capability_ref: str = Field(min_length=1)
    dependency_role: AssessmentDependencyRole
    provenance: DependencyProvenance
    objective_ids: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: AssessmentDependencyStatus


class AssessmentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    objective_ids: list[str] = Field(default_factory=list)
    capability_claim: str = Field(min_length=1)
    required_evidence: list[EvidenceCriterion] = Field(default_factory=list)
    task: AssessmentTaskSpec
    cognitive_process: CognitiveProcess
    scoring: ScoringSpec | None = None
    role: AssessmentRole | None = None
    required_capabilities: list[AssessmentCapabilityRequirement] = Field(default_factory=list)
    # Kept for artifacts emitted before ID-02D. New contracts use ``role`` and
    # ``required_capabilities``; this field remains wire-compatible until the
    # experiment corpus is migrated deliberately.
    is_summative: bool = True
    required_capability_refs: list[str] = Field(default_factory=list)
    # Planning estimate only; it is part of the declared course budget when set.
    estimated_minutes: int | None = Field(default=None, gt=0)
    provenance: ArtifactProvenance

    @property
    def effective_role(self) -> AssessmentRole:
        if self.role is not None:
            return self.role
        return AssessmentRole.SUMMATIVE if self.is_summative else AssessmentRole.FORMATIVE

    @model_validator(mode="after")
    def typed_role_must_not_conflict_with_explicit_legacy_role(self) -> "AssessmentSpec":
        if self.role is None or "is_summative" not in self.model_fields_set:
            return self

        legacy_role = (
            AssessmentRole.SUMMATIVE if self.is_summative else AssessmentRole.FORMATIVE
        )
        if self.role is not legacy_role:
            raise ValueError("role conflicts with legacy is_summative")
        return self


class PrerequisiteSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    status: PrerequisiteStatus
    basis: PrerequisiteBasis
    classification: PrerequisiteClassification = PrerequisiteClassification.REQUIRED_PREREQUISITE
    rationale: str | None = None
    required_for_refs: list[str] = Field(default_factory=list)
    requires_prerequisite_refs: list[str] = Field(default_factory=list)
    teaching_objective_id: str | None = None
    disposition: PrerequisiteDisposition | None = None
    source_dependency_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def model_proposed_is_never_confirmed(self) -> "PrerequisiteSpec":
        if (
            self.basis is PrerequisiteBasis.MODEL_PROPOSED
            and self.status is not PrerequisiteStatus.CANDIDATE
        ):
            raise ValueError("model_proposed prerequisites must have status=candidate")
        return self


class ModuleOutline(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective_ids: list[str] = Field(default_factory=list)
    prerequisite_refs: list[str] = Field(default_factory=list)
    lesson_ids: list[str] = Field(default_factory=list)
    estimated_minutes: int | None = Field(default=None, gt=0)


class PlanningWarning(BaseModel):
    """A declared planning trade-off; it is not a claim that the plan fits."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    type: PlanningWarningType
    decision: PlanningWarningDecision
    rationale: str | None = None


class CourseOutline(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    brief_id: str = Field(min_length=1)
    objective_ids: list[str] = Field(default_factory=list)
    modules: list[ModuleOutline] = Field(default_factory=list)
    prerequisite_refs: list[str] = Field(default_factory=list)
    estimated_minutes: int | None = Field(default=None, gt=0)
    planning_warnings: list[PlanningWarning] = Field(default_factory=list)
    sequencing_rationale: list[str] = Field(default_factory=list)
    provenance: ArtifactProvenance


class LessonSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    module_id: str = Field(min_length=1)
    objective_ids: list[str] = Field(default_factory=list)
    prerequisite_refs: list[str] = Field(default_factory=list)
    lesson_goal: str = Field(min_length=1)
    instructional_pattern: InstructionalPattern
    expected_learner_activity: str = Field(min_length=1)
    formative_assessment_ids: list[str] = Field(default_factory=list)
    summative_assessment_ids: list[str] = Field(default_factory=list)
    estimated_minutes: int | None = Field(default=None, gt=0)
    provenance: ArtifactProvenance


class DesignFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    code: str = Field(min_length=1)
    severity: DesignFindingSeverity
    entity_type: str | None = None
    entity_id: str | None = None
    field: str | None = None
    message: str = Field(min_length=1)


class InstructionalDesignQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    passed: bool
    findings: list[DesignFinding] = Field(default_factory=list)
    objective_coverage: float = Field(ge=0, le=1)
    assessment_coverage: float = Field(ge=0, le=1)
    unresolved_prerequisites: list[str] = Field(default_factory=list)
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    practice_coverage: list[dict[str, object]] = Field(default_factory=list)


class GenerationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    research_brief_id: str = Field(min_length=1)
    instructional_design_policy_id: str = Field(min_length=1)
    instructional_design_policy_version: str = Field(min_length=1)
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    output_schema_versions: dict[str, str] = Field(default_factory=dict)
    provider: str | None = None
    model: str | None = None
    model_revision: str | None = None
    generated_at: datetime


class InstructionalDesignResearchSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    snapshot_version: str = Field(min_length=1)
    brief: ResearchLearningBrief
    objectives: list[LearningObjectiveSpec] = Field(default_factory=list)
    assessments: list[AssessmentSpec] = Field(default_factory=list)
    dependency_candidates: list[AssessmentDependencyCandidate] = Field(default_factory=list)
    prerequisites: list[PrerequisiteSpec] = Field(default_factory=list)
    canonical_dependencies: list[CanonicalAssessmentDependency] = Field(default_factory=list)
    course_outline: CourseOutline | None = None
    lessons: list[LessonSpec] = Field(default_factory=list)
    quality_report: InstructionalDesignQualityReport
    generation_provenance: GenerationProvenance

    @model_validator(mode="after")
    def snapshot_provenance_matches_brief(self) -> "InstructionalDesignResearchSnapshot":
        if self.generation_provenance.research_brief_id != self.brief.id:
            raise ValueError("generation provenance must reference the research brief")
        if (
            self.generation_provenance.instructional_design_policy_id
            != self.quality_report.policy_id
            or self.generation_provenance.instructional_design_policy_version
            != self.quality_report.policy_version
        ):
            raise ValueError("generation provenance policy must match the quality report")
        return self
