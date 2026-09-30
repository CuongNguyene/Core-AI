from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from app.capability_analysis.domain_packs.contracts import DomainPackReference
from app.capability_analysis.semantic_core.contracts import EvidenceSemantics
from app.extraction.locators import SourceLocator
from app.matching.schemas import SemanticPolicySelectionSource


class CapabilityEvidenceStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    NOT_FOUND_IN_EVIDENCE = "not_found_in_evidence"
    INSUFFICIENT = "insufficient"
    CONFLICTING = "conflicting"


class VerificationStatus(StrEnum):
    PROVISIONAL = "provisional"


class AnalysisStatus(StrEnum):
    READY = "ready"


class TargetType(StrEnum):
    CURRENT_ROLE = "current_role"
    FUTURE_ROLE = "future_role"


class TargetUsageMode(StrEnum):
    OFFICIAL = "official"
    PROVISIONAL = "provisional"
    PREVIEW = "preview"


class AssessmentEvidenceStatus(StrEnum):
    SUPPORTED = "supported"
    REQUIRES_VERIFICATION = "requires_verification"
    CONTEXT_MISMATCH = "context_mismatch"
    NOT_FOUND_IN_EVIDENCE = "not_found_in_evidence"
    INSUFFICIENT = "insufficient"
    CONFLICTING = "conflicting"


class EvidenceStrength(StrEnum):
    MENTION = "mention"
    PROJECT = "project"
    WORK = "work"
    PRODUCTION = "production"


class AssessmentDecisionDetails(BaseModel):
    """Additive, deterministic explanation of one assessment projection."""

    model_config = ConfigDict(extra="forbid", strict=True)

    reason_codes: list[str] = Field(default_factory=list)
    supported_signals: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    observed_confidence: float | None = Field(default=None, ge=0, le=1)
    required_confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_directness: str | None = None
    verification_required: bool = False
    threshold_source: str = "unknown"
    threshold_policy_id: str | None = None
    threshold_policy_version: str | None = None


class VerificationQueueStatus(StrEnum):
    PENDING = "pending"
    RECOMMENDED = "recommended"


class PreliminaryPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CapabilitySourceLocator(SourceLocator):
    """Frozen copy of source location retained by a capability snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class CapabilityObservation(BaseModel):
    """A source-backed observation retained in a provisional capability."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    evidence_ref: str = Field(min_length=1)
    source_locator: CapabilitySourceLocator
    environment: str = Field(min_length=1)
    context: str = Field(min_length=1)
    participation: str | None
    confidence: float = Field(ge=0, le=1)
    explicit_production_claim: bool = False
    original_value: str | None = None
    source_excerpt: str | None = None
    original_evidence_type: str | None = None

    @model_validator(mode="before")
    @classmethod
    def freeze_source_locator_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        source_locator = value.get("source_locator")
        if not isinstance(source_locator, SourceLocator):
            return value
        return {**value, "source_locator": source_locator.model_dump()}


class ProvisionalCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    capability_id: str = Field(min_length=1)
    status: CapabilityEvidenceStatus
    verification_status: Literal[VerificationStatus.PROVISIONAL]
    observations: tuple[CapabilityObservation, ...] = Field(default_factory=tuple)

    @model_validator(mode="before")
    @classmethod
    def preserve_list_observation_inputs(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        observations = value.get("observations")
        if not isinstance(observations, list):
            return value
        return {**value, "observations": tuple(observations)}

    @model_validator(mode="after")
    def require_observations_for_supported_capability(self) -> "ProvisionalCapability":
        if self.status is CapabilityEvidenceStatus.SUPPORTED and not self.observations:
            raise ValueError("Supported capability requires source-backed observations")
        return self


class ProvisionalCurrentCapabilityProfile(BaseModel):
    """Immutable analysis snapshot derived from one CandidateProfile extraction."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_profile_id: str = Field(min_length=1)
    source_profile_version: int = Field(ge=1)
    capabilities: tuple[ProvisionalCapability, ...] = Field(min_length=1)
    semantic_evidence: tuple[EvidenceSemantics, ...] = Field(
        default_factory=tuple,
        exclude=True,
        repr=False,
    )

    @model_validator(mode="before")
    @classmethod
    def preserve_list_capability_inputs(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        capabilities = value.get("capabilities")
        if not isinstance(capabilities, list):
            return value
        return {**value, "capabilities": tuple(capabilities)}


class RequirementAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    target_id: str = Field(min_length=1)
    target_type: TargetType
    requirement_id: str = Field(min_length=1)
    matched_evidence_refs: list[str]
    missing_signals: list[str]
    rationale: str = Field(min_length=1)
    preliminary_priority: PreliminaryPriority
    missing_priority_inputs: list[str]
    evidence_status: AssessmentEvidenceStatus = AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE
    evidence_strength: EvidenceStrength | None = None
    production_required: bool = False
    retrieved_candidate_count: int = Field(default=0, ge=0)
    eligible_candidate_count: int = Field(default=0, ge=0)
    decision_details: AssessmentDecisionDetails = Field(default_factory=AssessmentDecisionDetails)
    recommendation: str | None = None


class TargetGap(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    target_type: TargetType
    requirement_id: str = Field(min_length=1)
    matched_evidence_refs: list[str]
    missing_signals: list[str]
    rationale: str = Field(min_length=1)
    preliminary_priority: PreliminaryPriority
    missing_priority_inputs: list[str]
    evidence_status: AssessmentEvidenceStatus = AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE
    evidence_strength: EvidenceStrength | None = None
    production_required: bool = False
    retrieved_candidate_count: int = Field(default=0, ge=0)
    eligible_candidate_count: int = Field(default=0, ge=0)
    overlap_keys: list[str] = Field(default_factory=list)
    decision_details: AssessmentDecisionDetails = Field(default_factory=AssessmentDecisionDetails)
    recommendation: str | None = None


class TargetGapAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    target_id: str = Field(min_length=1)
    target_type: TargetType
    usage_mode: TargetUsageMode
    assessments: list[RequirementAssessment]
    gaps: list[TargetGap]
    warning_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_target_local_assessments_and_gaps(self) -> "TargetGapAnalysis":
        for assessment in self.assessments:
            if assessment.target_id != self.target_id or assessment.target_type != self.target_type:
                raise ValueError("Requirement assessments must match the analysis target")
        for gap in self.gaps:
            if gap.target_id != self.target_id or gap.target_type != self.target_type:
                raise ValueError("Target gaps must match the analysis target")
        return self


class CapabilityGapProfileEntry(BaseModel):
    """One canonical requirement evaluation and its optional gap projection."""

    model_config = ConfigDict(extra="forbid", strict=True)

    requirement_id: str = Field(min_length=1)
    matched_evidence_refs: list[str]
    missing_signals: list[str]
    rationale: str = Field(min_length=1)
    preliminary_priority: PreliminaryPriority
    missing_priority_inputs: list[str]
    evidence_status: AssessmentEvidenceStatus = AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE
    evidence_strength: EvidenceStrength | None = None
    production_required: bool = False
    retrieved_candidate_count: int = Field(default=0, ge=0)
    eligible_candidate_count: int = Field(default=0, ge=0)
    decision_details: AssessmentDecisionDetails = Field(default_factory=AssessmentDecisionDetails)
    recommendation: str | None = None
    gap_id: str | None = Field(default=None, min_length=1)
    overlap_keys: list[str] = Field(default_factory=list)

    @classmethod
    def from_assessment(
        cls, assessment: RequirementAssessment, gap: TargetGap | None
    ) -> "CapabilityGapProfileEntry":
        values = assessment.model_dump()
        if gap is not None:
            values.update(
                gap_id=gap.id,
                overlap_keys=gap.overlap_keys,
                matched_evidence_refs=gap.matched_evidence_refs,
                missing_signals=gap.missing_signals,
                rationale=gap.rationale,
                preliminary_priority=gap.preliminary_priority,
                missing_priority_inputs=gap.missing_priority_inputs,
                evidence_status=gap.evidence_status,
                evidence_strength=gap.evidence_strength,
                production_required=gap.production_required,
                retrieved_candidate_count=gap.retrieved_candidate_count,
                eligible_candidate_count=gap.eligible_candidate_count,
                decision_details=gap.decision_details,
                recommendation=gap.recommendation,
            )
        values.pop("target_id", None)
        values.pop("target_type", None)
        return cls(**values)

    def to_requirement_assessment(
        self, *, target_id: str, target_type: TargetType
    ) -> RequirementAssessment:
        return RequirementAssessment(
            target_id=target_id,
            target_type=target_type,
            requirement_id=self.requirement_id,
            matched_evidence_refs=self.matched_evidence_refs,
            missing_signals=self.missing_signals,
            rationale=self.rationale,
            preliminary_priority=self.preliminary_priority,
            missing_priority_inputs=self.missing_priority_inputs,
            evidence_status=self.evidence_status,
            evidence_strength=self.evidence_strength,
            production_required=self.production_required,
            retrieved_candidate_count=self.retrieved_candidate_count,
            eligible_candidate_count=self.eligible_candidate_count,
            decision_details=self.decision_details,
            recommendation=self.recommendation,
        )

    def to_target_gap(self, *, target_id: str, target_type: TargetType) -> TargetGap | None:
        if self.gap_id is None:
            return None
        return TargetGap(
            id=self.gap_id,
            target_id=target_id,
            target_type=target_type,
            requirement_id=self.requirement_id,
            matched_evidence_refs=self.matched_evidence_refs,
            missing_signals=self.missing_signals,
            rationale=self.rationale,
            preliminary_priority=self.preliminary_priority,
            missing_priority_inputs=self.missing_priority_inputs,
            evidence_status=self.evidence_status,
            evidence_strength=self.evidence_strength,
            production_required=self.production_required,
            retrieved_candidate_count=self.retrieved_candidate_count,
            eligible_candidate_count=self.eligible_candidate_count,
            overlap_keys=self.overlap_keys,
            decision_details=self.decision_details,
            recommendation=self.recommendation,
        )


class CapabilityGapProfileTrack(BaseModel):
    """Canonical target track from which legacy rows are projected."""

    model_config = ConfigDict(extra="forbid", strict=True)

    target_id: str = Field(min_length=1)
    target_type: TargetType
    usage_mode: TargetUsageMode
    entries: list[CapabilityGapProfileEntry]
    warning_codes: list[str] = Field(default_factory=list)

    @classmethod
    def from_target_gap_analysis(cls, analysis: TargetGapAnalysis) -> "CapabilityGapProfileTrack":
        gaps_by_requirement = {gap.requirement_id: gap for gap in analysis.gaps}
        assessment_requirement_ids = {assessment.requirement_id for assessment in analysis.assessments}
        if set(gaps_by_requirement) - assessment_requirement_ids:
            raise ValueError("Capability gap without requirement assessment cannot be projected")
        return cls(
            target_id=analysis.target_id,
            target_type=analysis.target_type,
            usage_mode=analysis.usage_mode,
            entries=[
                CapabilityGapProfileEntry.from_assessment(
                    assessment, gaps_by_requirement.get(assessment.requirement_id)
                )
                for assessment in analysis.assessments
            ],
            warning_codes=analysis.warning_codes,
        )

    def to_target_gap_analysis(self) -> TargetGapAnalysis:
        assessments = [
            entry.to_requirement_assessment(
                target_id=self.target_id, target_type=self.target_type
            )
            for entry in self.entries
        ]
        gaps = [
            gap
            for entry in self.entries
            if (gap := entry.to_target_gap(target_id=self.target_id, target_type=self.target_type))
            is not None
        ]
        return TargetGapAnalysis(
            target_id=self.target_id,
            target_type=self.target_type,
            usage_mode=self.usage_mode,
            assessments=assessments,
            gaps=gaps,
            warning_codes=self.warning_codes,
        )


class PreviewReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["capability-preview-v1"] = "capability-preview-v1"
    analysis_mode: Literal[TargetUsageMode.PREVIEW] = TargetUsageMode.PREVIEW
    capability_verification_status: Literal[VerificationStatus.PROVISIONAL] = (
        VerificationStatus.PROVISIONAL
    )
    final_competency_decision_prohibited: Literal[True] = True


class VerificationQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    requirement_id: str = Field(min_length=1)
    target_type: TargetType
    evidence_status: AssessmentEvidenceStatus
    status: VerificationQueueStatus
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)


class GapOverlapLink(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_gap_id: str = Field(min_length=1)
    target_gap_id: str = Field(min_length=1)
    shared_theme: str = Field(min_length=1)


class SemanticPolicySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    core_version: str = Field(min_length=1)
    pack_refs: tuple[DomainPackReference, ...] = Field(min_length=1)
    selection_source: SemanticPolicySelectionSource


class TargetSemanticPolicySnapshot(SemanticPolicySnapshot):
    target_id: str = Field(min_length=1)
    target_version: str = Field(min_length=1)
    target_type: TargetType
    policy_id: str | None = None
    policy_version: str | None = None
    pack_checksum: str | None = None

    @model_serializer(mode="wrap")
    def serialize_without_optional_governance_nulls(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, object]:
        return {key: value for key, value in handler(self).items() if value is not None}


class CombinedGapPortfolio(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    cv_profile_id: str = Field(min_length=1)
    cv_profile_version: int = Field(ge=1)
    current_target_version: str = Field(min_length=1)
    future_target_version: str | None = Field(default=None, min_length=1)
    owner_actor_id: UUID
    organization_id: UUID
    correlation_id: str = Field(min_length=1)
    candidate_id: UUID | None = None
    analysis_status: AnalysisStatus = AnalysisStatus.READY
    analysis_version: int = Field(default=1, ge=1)
    idempotency_key: str | None = None
    current_role: TargetGapAnalysis
    future_role: TargetGapAnalysis | None = None
    overlap_links: list[GapOverlapLink] = Field(default_factory=list)
    snapshot_schema_version: str = "capability-gap-v1"
    preview_readiness: PreviewReadiness | None = None
    verification_queue: list[VerificationQueueItem] = Field(default_factory=list)
    semantic_policies: tuple[TargetSemanticPolicySnapshot, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def require_fixed_target_types_for_portfolio_tracks(self) -> "CombinedGapPortfolio":
        if self.current_role.target_type != TargetType.CURRENT_ROLE:
            raise ValueError("Current role analysis must use the current_role target type")
        if self.future_role is not None and self.future_role.target_type != TargetType.FUTURE_ROLE:
            raise ValueError("Future role analysis must use the future_role target type")
        if self.future_role is None and self.future_target_version is not None:
            raise ValueError("Future target version requires a future role analysis")
        if not self.semantic_policies:
            return self
        current_policies = [
            item
            for item in self.semantic_policies
            if item.target_type is TargetType.CURRENT_ROLE
        ]
        future_policies = [
            item
            for item in self.semantic_policies
            if item.target_type is TargetType.FUTURE_ROLE
        ]
        if len(current_policies) != 1:
            raise ValueError("Portfolio requires exactly one current semantic policy")
        current_policy = current_policies[0]
        if (
            current_policy.target_id != self.current_role.target_id
            or current_policy.target_version != self.current_target_version
        ):
            raise ValueError("Current semantic policy must match its target id and version")
        if self.future_role is None:
            if future_policies:
                raise ValueError("Future semantic policy requires a future target")
        else:
            if len(future_policies) != 1:
                raise ValueError("Portfolio requires exactly one future semantic policy")
            future_policy = future_policies[0]
            if (
                future_policy.target_id != self.future_role.target_id
                or future_policy.target_version != self.future_target_version
            ):
                raise ValueError("Future semantic policy must match its target id and version")
        if len(self.semantic_policies) != len(current_policies) + len(future_policies):
            raise ValueError("Portfolio semantic policies contain an unknown target track")
        return self


class CapabilityGapProfile(BaseModel):
    """Canonical capability-gap aggregate backed by existing portfolio persistence."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    cv_profile_id: str = Field(min_length=1)
    cv_profile_version: int = Field(ge=1)
    current_target_version: str = Field(min_length=1)
    future_target_version: str | None = Field(default=None, min_length=1)
    owner_actor_id: UUID
    organization_id: UUID
    correlation_id: str = Field(min_length=1)
    candidate_id: UUID | None = None
    analysis_status: AnalysisStatus = AnalysisStatus.READY
    analysis_version: int = Field(default=1, ge=1)
    idempotency_key: str | None = None
    current_role: CapabilityGapProfileTrack
    future_role: CapabilityGapProfileTrack | None = None
    overlap_links: list[GapOverlapLink] = Field(default_factory=list)
    snapshot_schema_version: str = "capability-gap-v1"
    preview_readiness: PreviewReadiness | None = None
    verification_queue: list[VerificationQueueItem] = Field(default_factory=list)
    semantic_policies: tuple[TargetSemanticPolicySnapshot, ...] = Field(default_factory=tuple)

    @classmethod
    def from_combined_gap_portfolio(cls, portfolio: CombinedGapPortfolio) -> "CapabilityGapProfile":
        return cls(
            id=portfolio.id,
            cv_profile_id=portfolio.cv_profile_id,
            cv_profile_version=portfolio.cv_profile_version,
            current_target_version=portfolio.current_target_version,
            future_target_version=portfolio.future_target_version,
            owner_actor_id=portfolio.owner_actor_id,
            organization_id=portfolio.organization_id,
            correlation_id=portfolio.correlation_id,
            candidate_id=portfolio.candidate_id,
            analysis_status=portfolio.analysis_status,
            analysis_version=portfolio.analysis_version,
            idempotency_key=portfolio.idempotency_key,
            current_role=CapabilityGapProfileTrack.from_target_gap_analysis(portfolio.current_role),
            future_role=(
                CapabilityGapProfileTrack.from_target_gap_analysis(portfolio.future_role)
                if portfolio.future_role is not None
                else None
            ),
            overlap_links=portfolio.overlap_links,
            snapshot_schema_version=portfolio.snapshot_schema_version,
            preview_readiness=portfolio.preview_readiness,
            verification_queue=portfolio.verification_queue,
            semantic_policies=portfolio.semantic_policies,
        )

    def to_combined_gap_portfolio(self) -> CombinedGapPortfolio:
        return CombinedGapPortfolio(
            id=self.id,
            cv_profile_id=self.cv_profile_id,
            cv_profile_version=self.cv_profile_version,
            current_target_version=self.current_target_version,
            future_target_version=self.future_target_version,
            owner_actor_id=self.owner_actor_id,
            organization_id=self.organization_id,
            correlation_id=self.correlation_id,
            candidate_id=self.candidate_id,
            analysis_status=self.analysis_status,
            analysis_version=self.analysis_version,
            idempotency_key=self.idempotency_key,
            current_role=self.current_role.to_target_gap_analysis(),
            future_role=(
                self.future_role.to_target_gap_analysis() if self.future_role is not None else None
            ),
            overlap_links=self.overlap_links,
            snapshot_schema_version=self.snapshot_schema_version,
            preview_readiness=self.preview_readiness,
            verification_queue=self.verification_queue,
            semantic_policies=self.semantic_policies,
        )


class HumanAssistedEvidenceSelection(BaseModel):
    """Requirement-scoped references to existing canonical candidate evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    requirement_id: str = Field(min_length=1, max_length=128)
    selected_evidence_refs: list[str] = Field(min_length=1, max_length=20)

    @field_validator("selected_evidence_refs")
    @classmethod
    def deduplicate_refs_stably(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for ref in value:
            if not ref or len(ref) > 256:
                raise ValueError("Evidence references must be non-empty and bounded")
            if ref not in seen:
                seen.add(ref)
                result.append(ref)
        if not result:
            raise ValueError("At least one evidence reference is required")
        return result


class HumanAssistedReanalysisContext(BaseModel):
    """Transient, typed context for one human-assisted capability reanalysis."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_analysis_id: str = Field(min_length=1, max_length=128)
    evidence_selections: list[HumanAssistedEvidenceSelection] = Field(
        min_length=1, max_length=20
    )

    @field_validator("evidence_selections")
    @classmethod
    def require_unique_requirements(
        cls, value: list[HumanAssistedEvidenceSelection]
    ) -> list[HumanAssistedEvidenceSelection]:
        requirement_ids = [item.requirement_id for item in value]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("Each requirement may have only one assisted selection")
        return value


class HumanAssistedReanalysisProvenance(BaseModel):
    """Safe typed provenance returned for a newly-created assisted analysis."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    origin: Literal["HUMAN_ASSISTED_EVIDENCE"] = "HUMAN_ASSISTED_EVIDENCE"
    source_analysis_id: str = Field(min_length=1, max_length=128)
    evidence_selections: list[HumanAssistedEvidenceSelection] = Field(
        min_length=1, max_length=20
    )
    reviewer_actor_id: UUID


class HumanAssistedReanalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    analysis: CombinedGapPortfolio
    provenance: HumanAssistedReanalysisProvenance


class HumanAssistedReanalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_selections: list[HumanAssistedEvidenceSelection] = Field(
        min_length=1, max_length=20
    )


class CreateCapabilityGapAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    cv_profile_id: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    )
    current_target_profile_id: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    )
    future_target_profile_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    )
    correlation_id: str = Field(
        min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    )
