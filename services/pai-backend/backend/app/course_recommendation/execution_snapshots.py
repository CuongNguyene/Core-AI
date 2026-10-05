"""Validated, immutable snapshots for resolved 01B recommendation inputs."""

from __future__ import annotations

import hashlib
import json
from typing import NoReturn

from pydantic import BaseModel, ConfigDict

from app.capability_governance.course_projection import (
    CourseProjectionWarning,
    GovernedCourseProjectionResult,
)
from app.capability_governance.identity import SourceSemanticRef
from app.capability_governance.mapping_activation import SourceSemanticPin
from app.capability_governance.mapping_resolution import BindingResolutionMode
from app.capability_governance.resolution import CapabilityDefinitionPin
from app.capability_governance.target_adapter import GovernedRecommendationTargetProjection
from app.course_catalog.schemas import CourseProfileStatus
from app.course_recommendation.engine import CourseRecommendationEngine
from app.course_recommendation.schemas import (
    CourseRecommendationCandidate,
    CourseRecommendationRequest,
    CourseRecommendationResult,
)

SNAPSHOT_SCHEMA_VERSION = "1.0"
MAX_SNAPSHOT_BYTES = 1024 * 1024


class RecommendationSnapshotInconsistent(ValueError):
    """A supplied resolved projection is internally inconsistent or ineligible."""


class ImmutableSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TargetMappingSnapshot(ImmutableSnapshot):
    facet_id: str
    source_ref: SourceSemanticRef
    mapping_id: str
    mapping_fingerprint: str
    proposal_id: str
    proposal_fingerprint: str
    review_fingerprint: str
    activation_approval_ref: str
    approver_ref: str
    mapping_scope: str
    target_definition_pin: CapabilityDefinitionPin


class TargetGovernanceSnapshot(ImmutableSnapshot):
    role_profile_id: str
    role_profile_version: str
    role_requirement_ref: str
    gap_profile_id: str
    gap_analysis_version: int
    gap_target_id: str
    gap_target_version: str
    learning_need_ref: str
    learning_need_target_ref: str
    learning_need_path_ref: str | None
    path_step_ref: str | None
    source_gap_refs: tuple[str, ...]
    canonical_capability_refs: tuple[str, ...]
    definition_pins: tuple[CapabilityDefinitionPin, ...]
    mappings: tuple[TargetMappingSnapshot, ...]
    warning_codes: tuple[str, ...]


class CourseMappingSnapshot(ImmutableSnapshot):
    source_ref: SourceSemanticRef
    source_pin: SourceSemanticPin
    mapping_id: str
    mapping_fingerprint: str
    mapping_scope: str
    definition_pin: CapabilityDefinitionPin
    resolution_mode: str


class CourseCoverageSnapshot(ImmutableSnapshot):
    course_ref: str
    capability_ref: str
    sources: tuple[CourseMappingSnapshot, ...]


class CourseGovernanceSnapshot(ImmutableSnapshot):
    course_ref: str
    profile_id: str | None
    profile_version: int | None
    profile_status: str
    canonical_capability_refs: tuple[str, ...]
    coverage: tuple[CourseCoverageSnapshot, ...]
    warnings: tuple[CourseProjectionWarning, ...]


class GovernanceSnapshot(ImmutableSnapshot):
    schema_version: str = SNAPSHOT_SCHEMA_VERSION
    target: TargetGovernanceSnapshot
    courses: tuple[CourseGovernanceSnapshot, ...]


def build_execution_snapshots(
    target_projection: GovernedRecommendationTargetProjection,
    course_projections: tuple[GovernedCourseProjectionResult, ...],
    *,
    max_results: int = 5,
) -> tuple[CourseRecommendationRequest, GovernanceSnapshot]:
    """Build the exact 01B input and minimized, auditable governance snapshot."""
    target = target_projection.recommendation_target
    canonical_refs = tuple(sorted(str(ref) for ref in target_projection.canonical_capability_refs))
    if tuple(target.target_capability_refs) != canonical_refs:
        _inconsistent("target_capability_refs_mismatch")
    if len(set(canonical_refs)) != len(canonical_refs):
        _inconsistent("duplicate_target_capability_ref")

    target_pins = _pins_by_capability(target_projection.definition_pins)
    if set(target_pins) != set(canonical_refs):
        _inconsistent("target_definition_pin_set_mismatch")
    if len(target_projection.definition_pins) != len(canonical_refs):
        _inconsistent("target_definition_pin_cardinality_mismatch")
    provenance_by_mapping = {item.mapping_id: item for item in target_projection.mapping_provenance}
    if len(provenance_by_mapping) != len(target_projection.mapping_provenance):
        _inconsistent("duplicate_target_mapping_provenance")
    binding_by_mapping = {item.mapping_id: item for item in target_projection.bindings}
    if set(binding_by_mapping) != set(provenance_by_mapping):
        _inconsistent("target_binding_provenance_mismatch")
    for mapping_id, provenance in provenance_by_mapping.items():
        binding = binding_by_mapping[mapping_id]
        canonical_ref = str(provenance.target_definition_pin.capability_ref)
        if (
            canonical_ref not in target_pins
            or target_pins.get(canonical_ref) != provenance.target_definition_pin
            or binding.source_ref != provenance.source_ref
            or binding.mapping_fingerprint != provenance.mapping_fingerprint
            or binding.mapping_scope != provenance.mapping_scope
            or binding.target_definition_pin != provenance.target_definition_pin
            or binding.resolution_mode is not BindingResolutionMode.CURRENT
        ):
            _inconsistent("target_binding_provenance_mismatch")
    requirement_refs = tuple(target.source_role_requirement_refs)
    if requirement_refs != (target_projection.role_requirement.id,):
        _inconsistent("target_role_requirement_lineage_mismatch")
    need = target_projection.learning_need
    if (
        target.source_learning_need_ref != need.id
        or target.target_ref != need.target_reference
        or tuple(target.source_gap_refs) != tuple(sorted(need.source_gap_refs))
        or tuple(target_projection.source_gap_refs) != tuple(sorted(need.source_gap_refs))
        or need.requirement_reference != target_projection.role_requirement.id
        or need.competency.id != target_projection.role_requirement.id
        or need.provenance.analysis_id != target_projection.gap_profile_id
        or need.provenance.analysis_version != target_projection.gap_analysis_version
        or need.provenance.target_id != target_projection.gap_target_id
        or need.provenance.target_version != target_projection.gap_target_version
    ):
        _inconsistent("target_learning_need_lineage_mismatch")

    request_candidates: list[CourseRecommendationCandidate] = []
    course_snapshots: list[CourseGovernanceSnapshot] = []
    target_pin_set = set(target_pins)
    seen_courses: set[str] = set()
    for projection in sorted(course_projections, key=lambda item: item.course_ref):
        profile = projection.profile_candidate
        candidate = projection.normalized_candidate
        if candidate is None:
            _inconsistent("course_candidate_missing")
        if profile is not None and profile.status.value != "active":
            _inconsistent("course_profile_not_active")
        if projection.course_ref != candidate.course_ref:
            _inconsistent("course_identity_mismatch")
        if profile is not None and candidate != profile.to_normalized_candidate():
            _inconsistent("normalized_candidate_profile_mismatch")
        if profile is not None and profile.status.value != "active":
            _inconsistent("course_profile_not_active")
        course_ref = candidate.course_ref
        if course_ref in seen_courses:
            _inconsistent("duplicate_course_ref")
        seen_courses.add(course_ref)
        coverage_by_ref = {str(item.capability_ref): item for item in projection.coverage}
        candidate_refs = {item.capability_ref for item in candidate.capabilities}
        if (
            len(coverage_by_ref) != len(projection.coverage)
            or set(coverage_by_ref) != candidate_refs
        ):
            _inconsistent("course_coverage_candidate_mismatch")
        course_pins: dict[str, CapabilityDefinitionPin] = {}
        coverage_snapshots: list[CourseCoverageSnapshot] = []
        for capability_ref in sorted(coverage_by_ref):
            coverage = coverage_by_ref[capability_ref]
            if coverage.course_ref != course_ref:
                _inconsistent("course_coverage_identity_mismatch")
            for trace in coverage.sources:
                if trace.resolution_mode is not BindingResolutionMode.CURRENT:
                    _inconsistent("course_mapping_not_current")
                pin = trace.definition_pin
                if (
                    str(pin.capability_ref) != capability_ref
                    or trace.source_pin.source_ref != trace.source_ref
                ):
                    _inconsistent("course_mapping_definition_pin_mismatch")
                prior = course_pins.setdefault(capability_ref, pin)
                if prior != pin:
                    _inconsistent("course_definition_pin_conflict")
            coverage_snapshots.append(
                CourseCoverageSnapshot(
                    course_ref=coverage.course_ref,
                    capability_ref=capability_ref,
                    sources=tuple(
                        CourseMappingSnapshot(
                            source_ref=trace.source_ref,
                            source_pin=trace.source_pin,
                            mapping_id=trace.mapping_id,
                            mapping_fingerprint=trace.mapping_fingerprint,
                            mapping_scope=trace.mapping_scope.value,
                            definition_pin=trace.definition_pin,
                            resolution_mode=trace.resolution_mode.value,
                        )
                        for trace in sorted(coverage.sources, key=lambda item: item.mapping_id)
                    ),
                )
            )
        for capability_ref in set(course_pins) & target_pin_set:
            if course_pins[capability_ref] != target_pins[capability_ref]:
                _inconsistent("canonical_definition_pin_mismatch")
        request_candidates.append(
            CourseRecommendationCandidate(
                course=candidate,
                profile_status=(
                    profile.status if profile is not None else CourseProfileStatus.ACTIVE
                ),
            )
        )
        course_snapshots.append(
            CourseGovernanceSnapshot(
                course_ref=course_ref,
                profile_id=profile.id if profile is not None else None,
                profile_version=profile.version if profile is not None else None,
                profile_status=(profile.status.value if profile is not None else "active"),
                canonical_capability_refs=tuple(sorted(candidate_refs)),
                coverage=tuple(coverage_snapshots),
                warnings=tuple(
                    item
                    for item in sorted(
                        projection.warnings,
                        key=lambda warning: (warning.source_ref.source_id, warning.code.value),
                    )
                ),
            )
        )

    target_snapshot = TargetGovernanceSnapshot(
        role_profile_id=target_projection.role_profile_id,
        role_profile_version=target_projection.role_profile_version,
        role_requirement_ref=target_projection.role_requirement.id,
        gap_profile_id=target_projection.gap_profile_id,
        gap_analysis_version=target_projection.gap_analysis_version,
        gap_target_id=target_projection.gap_target_id,
        gap_target_version=target_projection.gap_target_version,
        learning_need_ref=need.id,
        learning_need_target_ref=need.target_reference,
        learning_need_path_ref=target.source_learning_path_ref,
        path_step_ref=target.source_path_step_ref,
        source_gap_refs=tuple(sorted(target.source_gap_refs)),
        canonical_capability_refs=canonical_refs,
        definition_pins=tuple(target_pins[key] for key in canonical_refs),
        mappings=tuple(
            TargetMappingSnapshot(
                facet_id=item.facet_id,
                source_ref=item.source_ref,
                mapping_id=item.mapping_id,
                mapping_fingerprint=item.mapping_fingerprint,
                proposal_id=item.proposal_id,
                proposal_fingerprint=item.proposal_fingerprint,
                review_fingerprint=item.review_fingerprint,
                activation_approval_ref=item.activation_approval_ref,
                approver_ref=item.approver_ref,
                mapping_scope=item.mapping_scope.value,
                target_definition_pin=item.target_definition_pin,
            )
            for item in sorted(
                target_projection.mapping_provenance,
                key=lambda row: (str(row.target_definition_pin.capability_ref), row.mapping_id),
            )
        ),
        warning_codes=tuple(sorted(set(target_projection.warning_codes))),
    )
    request = CourseRecommendationRequest(
        recommendation_target=target,
        candidates=request_candidates,
        max_results=max_results,
    )
    governance = GovernanceSnapshot(target=target_snapshot, courses=tuple(course_snapshots))
    _check_size(request, governance)
    return request, governance


def request_fingerprint(
    request: CourseRecommendationRequest, governance: GovernanceSnapshot
) -> str:
    payload = {
        "algorithm_id": CourseRecommendationEngine.algorithm_id,
        "algorithm_version": CourseRecommendationEngine.algorithm_version,
        "request": request.model_dump(mode="json"),
        "governance": governance.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_execution_snapshot_size(
    request: CourseRecommendationRequest,
    result: CourseRecommendationResult,
    governance: GovernanceSnapshot,
) -> None:
    payload = {
        "request": request.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
        "governance": governance.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        _inconsistent("snapshot_size_exceeded")


def _pins_by_capability(
    pins: tuple[CapabilityDefinitionPin, ...],
) -> dict[str, CapabilityDefinitionPin]:
    result: dict[str, CapabilityDefinitionPin] = {}
    for pin in pins:
        key = str(pin.capability_ref)
        if key in result:
            _inconsistent("duplicate_target_definition_pin")
        result[key] = pin
    return result


def _check_size(request: CourseRecommendationRequest, governance: GovernanceSnapshot) -> None:
    payload = {
        "request": request.model_dump(mode="json"),
        "governance": governance.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        _inconsistent("snapshot_size_exceeded")


def _inconsistent(code: str) -> NoReturn:
    raise RecommendationSnapshotInconsistent(code)
