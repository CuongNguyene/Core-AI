"""Provider-neutral projection of current governed course semantics.

This adapter creates no mapping authority. It consumes source-owned outcomes or
direct claims and asks the 3D-3B resolver to validate each supplied mapping.
"""

from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.capability_governance.direct_claim_identity import make_direct_claim_source_id
from app.capability_governance.evidence import SemanticEvidence, canonicalize_semantic_evidence
from app.capability_governance.governed_mapping import GovernedCapabilityMapping
from app.capability_governance.identity import (
    CanonicalCapabilityRef,
    SourceSemanticKind,
    SourceSemanticRef,
)
from app.capability_governance.mapping import MappingScope
from app.capability_governance.mapping_activation import (
    SourceSemanticPin,
    build_source_semantic_pin,
)
from app.capability_governance.mapping_resolution import (
    BindingResolutionMode,
    resolve_governed_mapping_for_use,
)
from app.capability_governance.outcomes import CourseLearningOutcome
from app.capability_governance.packs import CapabilityPackRelease
from app.capability_governance.resolution import CapabilityDefinitionPin
from app.course_catalog.schemas import (
    CourseCapability,
    CourseCapabilityProfile,
    CourseProfileStatus,
    CourseProvenance,
    CoverageType,
    NormalizedCourseCandidate,
)


class CourseProjectionError(ValueError):
    """A source/profile cannot safely be used for current course projection."""


class CourseProjectionWarningCode(StrEnum):
    UNMAPPED_SEMANTIC = "unmapped_semantic"


class DirectCourseCapabilityClaim(BaseModel):
    """A direct course claim explicitly bound to a canonical course identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    course_ref: str = Field(min_length=1, max_length=512)
    claim_id: str = Field(min_length=1)
    source_ref: SourceSemanticRef
    evidence: tuple[SemanticEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_source_course_identity(self) -> DirectCourseCapabilityClaim:
        if self.source_ref.entity_kind is not SourceSemanticKind.COURSE_DIRECT_CLAIM:
            raise ValueError("course_direct_claim_ref_required")
        _validate_direct_claim_identity(self.course_ref, self.claim_id, self.source_ref)
        if any(item.source_ref != self.source_ref for item in self.evidence):
            raise ValueError("source_pin_mismatch")
        canonicalize_semantic_evidence(self.evidence)
        return self


class GovernedOutcomeMappingInput(BaseModel):
    """Outcome and its current evidence, optionally without a canonical mapping."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, arbitrary_types_allowed=True
    )

    outcome: CourseLearningOutcome
    evidence: tuple[SemanticEvidence, ...] = Field(min_length=1)
    mapping: GovernedCapabilityMapping | None

    @model_validator(mode="after")
    def validate_evidence_identity(self) -> GovernedOutcomeMappingInput:
        if any(item.source_ref != self.outcome.outcome_ref for item in self.evidence):
            raise ValueError("source_pin_mismatch")
        canonicalize_semantic_evidence(self.evidence)
        if (
            self.mapping is not None
            and self.mapping.source_pin.source_ref != self.outcome.outcome_ref
        ):
            raise ValueError("course_source_mismatch")
        return self


class GovernedDirectClaimMappingInput(BaseModel):
    """Direct claim plus optional approved mapping; no outcome wrapper is used."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, arbitrary_types_allowed=True
    )

    claim: DirectCourseCapabilityClaim
    mapping: GovernedCapabilityMapping | None

    @model_validator(mode="after")
    def validate_mapping_identity(self) -> GovernedDirectClaimMappingInput:
        if self.mapping is not None and self.mapping.source_pin.source_ref != self.claim.source_ref:
            raise ValueError("course_source_mismatch")
        return self


class GovernedCourseMappingTrace(BaseModel):
    """Compact, immutable provenance for one current course semantic binding."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_ref: SourceSemanticRef
    source_pin: SourceSemanticPin
    mapping_id: str = Field(min_length=1)
    mapping_fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    mapping_scope: MappingScope
    definition_pin: CapabilityDefinitionPin
    resolution_mode: BindingResolutionMode


class GovernedCourseCapabilityCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    course_ref: str = Field(min_length=1)
    capability_ref: CanonicalCapabilityRef
    sources: tuple[GovernedCourseMappingTrace, ...] = Field(min_length=1)


class CourseProjectionWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_ref: SourceSemanticRef
    code: CourseProjectionWarningCode


class GovernedCourseProjectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    course_ref: str = Field(min_length=1)
    coverage: tuple[GovernedCourseCapabilityCoverage, ...]
    warnings: tuple[CourseProjectionWarning, ...] = ()
    profile_candidate: CourseCapabilityProfile | None = None
    normalized_candidate: NormalizedCourseCandidate | None = None


def project_governed_course_capabilities(
    profile: CourseCapabilityProfile,
    *,
    outcomes: tuple[GovernedOutcomeMappingInput, ...] = (),
    direct_claims: tuple[GovernedDirectClaimMappingInput, ...] = (),
    active_release_context: tuple[CapabilityPackRelease, ...],
) -> GovernedCourseProjectionResult:
    """Project only current exact mappings while preserving profile lifecycle.

    A DRAFT input yields a DRAFT profile candidate. An ACTIVE profile yields a
    normalized candidate only when its existing capability refs exactly match
    the current governed projection. No profile is activated or rewritten.
    """
    semantic_inputs: list[
        tuple[
            SourceSemanticRef,
            tuple[SemanticEvidence, ...],
            GovernedCapabilityMapping | None,
            MappingScope,
        ]
    ] = []
    warnings: list[CourseProjectionWarning] = []

    for outcome_input in outcomes:
        if outcome_input.outcome.course_ref != profile.course_ref:
            raise CourseProjectionError("course_source_mismatch")
        semantic_inputs.append(
            (
                outcome_input.outcome.outcome_ref,
                outcome_input.evidence,
                outcome_input.mapping,
                MappingScope.OUTCOME_CAPABILITY_FACET,
            )
        )

    for direct_input in direct_claims:
        if direct_input.claim.course_ref != profile.course_ref:
            raise CourseProjectionError("course_source_mismatch")
        _validate_direct_claim_identity(
            direct_input.claim.course_ref,
            direct_input.claim.claim_id,
            direct_input.claim.source_ref,
        )
        semantic_inputs.append(
            (
                direct_input.claim.source_ref,
                direct_input.claim.evidence,
                direct_input.mapping,
                MappingScope.DIRECT_CAPABILITY_CLAIM,
            )
        )

    mapping_context = tuple(mapping for _, _, mapping, _ in semantic_inputs if mapping is not None)
    by_capability: dict[str, list[GovernedCourseMappingTrace]] = {}
    evidence_by_capability: dict[str, list[CourseProvenance]] = {}

    for source_ref, evidence, mapping, required_scope in semantic_inputs:
        if mapping is None:
            warnings.append(
                CourseProjectionWarning(
                    source_ref=source_ref,
                    code=CourseProjectionWarningCode.UNMAPPED_SEMANTIC,
                )
            )
            continue
        if (
            mapping.source_pin.source_ref != source_ref
            or mapping.mapping_scope is not required_scope
        ):
            raise CourseProjectionError("course_source_mismatch")
        source_pin = build_source_semantic_pin(source_ref, evidence)
        binding = resolve_governed_mapping_for_use(
            mapping,
            current_source_pin=source_pin,
            active_release_context=active_release_context,
            mapping_context=mapping_context,
        )
        if binding.resolution_mode is not BindingResolutionMode.CURRENT:
            raise CourseProjectionError("historical_mapping_not_eligible_for_current_projection")
        capability_ref = str(binding.target_definition_pin.capability_ref)
        trace = GovernedCourseMappingTrace(
            source_ref=source_ref,
            source_pin=source_pin,
            mapping_id=binding.mapping_id,
            mapping_fingerprint=binding.mapping_fingerprint,
            mapping_scope=binding.mapping_scope,
            definition_pin=binding.target_definition_pin,
            resolution_mode=binding.resolution_mode,
        )
        by_capability.setdefault(capability_ref, []).append(trace)
        evidence_by_capability.setdefault(capability_ref, []).extend(
            CourseProvenance(
                kind="governed_course_semantic_evidence",
                source_ref=source_ref.source_id,
                source_field=binding.mapping_scope.value,
                source_locator=item.source_locator,
                evidence_text=item.evidence_text,
                method="current_exact_governed_mapping",
            )
            for item in canonicalize_semantic_evidence(evidence)
        )

    coverage = tuple(
        GovernedCourseCapabilityCoverage(
            course_ref=profile.course_ref,
            capability_ref=CanonicalCapabilityRef.parse(capability_ref),
            sources=tuple(sorted(sources, key=_trace_sort_key)),
        )
        for capability_ref, sources in sorted(by_capability.items())
    )
    projected_claims = tuple(
        CourseCapability(
            capability_ref=item.capability_ref.root,
            coverage_type=CoverageType.DIRECT,
            target_level=None,
            provenance=_dedupe_provenance(evidence_by_capability[item.capability_ref.root]),
        )
        for item in coverage
    )

    profile_candidate: CourseCapabilityProfile | None = None
    normalized_candidate: NormalizedCourseCandidate | None = None
    if projected_claims and profile.status is CourseProfileStatus.DRAFT:
        existing_refs = {item.capability_ref for item in profile.capabilities}
        projected_refs = {item.capability_ref for item in projected_claims}
        if existing_refs == projected_refs:
            profile_candidate = CourseCapabilityProfile.model_validate(
                {
                    **profile.model_dump(),
                    "capabilities": [claim.model_dump() for claim in projected_claims],
                }
            )
    elif profile.status is CourseProfileStatus.ACTIVE and projected_claims:
        existing_refs = {item.capability_ref for item in profile.capabilities}
        projected_refs = {item.capability_ref for item in projected_claims}
        if existing_refs != projected_refs:
            raise CourseProjectionError("active_profile_projection_mismatch")
        normalized_candidate = profile.to_normalized_candidate()
    elif profile.status is CourseProfileStatus.DEPRECATED and projected_claims:
        raise CourseProjectionError("deprecated_profile_not_eligible")

    return GovernedCourseProjectionResult(
        course_ref=profile.course_ref,
        coverage=coverage,
        warnings=tuple(sorted(warnings, key=lambda item: _source_sort_key(item.source_ref))),
        profile_candidate=profile_candidate,
        normalized_candidate=normalized_candidate,
    )


def _validate_direct_claim_identity(
    course_ref: str, claim_id: str, source_ref: SourceSemanticRef
) -> None:
    if not claim_id.strip():
        raise ValueError("claim_id_required")
    namespace, separator, source_course_id = course_ref.partition(":")
    if not separator or namespace != source_ref.source_namespace:
        raise ValueError("course_source_mismatch")
    if source_ref.source_id != make_direct_claim_source_id(
        course_ref=course_ref, claim_id=claim_id
    ):
        raise ValueError("direct_claim_source_id_mismatch")


def _source_sort_key(source_ref: SourceSemanticRef) -> str:
    return json.dumps(source_ref.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _trace_sort_key(trace: GovernedCourseMappingTrace) -> tuple[str, str]:
    return (_source_sort_key(trace.source_ref), trace.mapping_id)


def _dedupe_provenance(items: list[CourseProvenance]) -> list[CourseProvenance]:
    by_value = {item.model_dump_json(): item for item in items}
    return [by_value[key] for key in sorted(by_value)]
