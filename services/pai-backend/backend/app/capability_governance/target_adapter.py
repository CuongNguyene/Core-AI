"""Fail-closed role/LearningNeed projection into COURSE-REC-01B targets."""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.capability_analysis.schemas import (
    CapabilityGapProfile,
    CapabilityGapProfileEntry,
    CapabilityGapProfileTrack,
)
from app.capability_governance.governed_mapping import GovernedCapabilityMapping
from app.capability_governance.identity import (
    CanonicalCapabilityRef,
    SourceSemanticKind,
    SourceSemanticRef,
)
from app.capability_governance.mapping import MappingScope
from app.capability_governance.mapping_activation import SourceSemanticPin
from app.capability_governance.mapping_resolution import (
    GovernedCapabilityBinding,
    resolve_governed_mapping_for_use,
)
from app.capability_governance.packs import CapabilityPackRelease
from app.capability_governance.resolution import CapabilityDefinitionPin
from app.course_recommendation.schemas import (
    RecommendationPrerequisiteContext,
    RecommendationTarget,
)
from app.learning_need_profile.schemas import (
    LearningNeedEligibility,
    LearningNeedProfile,
    LearningNeedResolution,
)
from app.matching.schemas import RoleCompetencyProfile, RoleRequirement


class TargetAdapterErrorCode:
    """Stable adapter-level rejection codes."""

    INVALID_FACET = "TARGET_FACET_INVALID"
    LINEAGE_MISMATCH = "TARGET_LINEAGE_MISMATCH"
    IDENTITY_CONFLICT = "TARGET_IDENTITY_CONTRACT_CONFLICT"
    INELIGIBLE_NEED = "TARGET_NEED_NOT_LEARNING_ELIGIBLE"
    UNRESOLVED_CAPABILITY = "TARGET_CAPABILITY_UNRESOLVED"
    MAPPING_SOURCE_MISMATCH = "TARGET_MAPPING_SOURCE_MISMATCH"
    CANONICAL_BINDING_CONFLICT = "TARGET_CANONICAL_BINDING_CONFLICT"
    TARGET_LEVEL_CONFLICT = "TARGET_LEVEL_CONFLICT"


class TargetAdapterError(ValueError):
    """Stable, deterministic target projection rejection."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


class RequiredTargetFacet(BaseModel):
    """One caller-declared source semantic required by a target projection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    facet_id: str = Field(min_length=1, max_length=256)
    source_pin: SourceSemanticPin

    @field_validator("facet_id")
    @classmethod
    def validate_facet_id(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("facet_id must be non-blank and exact")
        return value

    @model_validator(mode="after")
    def validate_source_kind_namespace(self) -> RequiredTargetFacet:
        ref = self.source_pin.source_ref
        expected = {
            SourceSemanticKind.ROLE_REQUIREMENT: "role_profile",
            SourceSemanticKind.LEARNING_NEED_COMPETENCY: "learning_need",
        }
        if expected.get(ref.entity_kind) != ref.source_namespace:
            raise ValueError(
                "required target facets must use the exact role/learning-need namespace"
            )
        return self


class GovernedMappingProvenance(BaseModel):
    """Exact mapping authority and review chain retained for a resolved facet."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    facet_id: str
    source_ref: SourceSemanticRef
    mapping_id: str
    mapping_fingerprint: str
    proposal_id: str
    proposal_fingerprint: str
    review_fingerprint: str
    activation_approval_ref: str
    approver_ref: str
    mapping_scope: MappingScope
    target_definition_pin: CapabilityDefinitionPin


class GovernedRecommendationTargetProjection(BaseModel):
    """Existing 01B target plus source identity and governance provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    recommendation_target: RecommendationTarget
    canonical_capability_refs: tuple[CanonicalCapabilityRef, ...]
    bindings: tuple[GovernedCapabilityBinding, ...]
    definition_pins: tuple[CapabilityDefinitionPin, ...]
    mapping_provenance: tuple[GovernedMappingProvenance, ...]
    role_profile_id: str
    role_profile_version: str
    role_requirement: RoleRequirement
    gap_profile_id: str
    gap_analysis_version: int
    gap_target_id: str
    gap_target_version: str
    gap_entries: tuple[CapabilityGapProfileEntry, ...]
    source_gap_refs: tuple[str, ...]
    learning_need: LearningNeedProfile
    usage_mode: str
    warning_codes: tuple[str, ...]


def project_governed_recommendation_target(
    *,
    role_profile: RoleCompetencyProfile,
    gap_profile: CapabilityGapProfile,
    learning_need: LearningNeedProfile,
    required_facets: tuple[RequiredTargetFacet, ...],
    governed_mappings: tuple[GovernedCapabilityMapping, ...],
    active_release_context: tuple[CapabilityPackRelease, ...],
    source_learning_path_ref: str | None = None,
    source_path_step_ref: str | None = None,
    prerequisite_context: RecommendationPrerequisiteContext | None = None,
) -> GovernedRecommendationTargetProjection:
    """Validate exact role/need lineage and resolve each required current mapping."""
    requirement = _requirement(role_profile, learning_need)
    track, target_version = _select_track(role_profile, gap_profile, learning_need)
    gap_entries = _validate_need_lineage(
        requirement, gap_profile, track, target_version, learning_need
    )
    if (
        learning_need.learning_eligibility is not LearningNeedEligibility.READY_FOR_LEARNING
        or learning_need.resolution_type is not LearningNeedResolution.LEARNING
    ):
        raise TargetAdapterError(
            TargetAdapterErrorCode.INELIGIBLE_NEED,
            "existing LearningNeed policy does not classify this need as learning eligible",
        )
    if not required_facets:
        raise TargetAdapterError(TargetAdapterErrorCode.UNRESOLVED_CAPABILITY)

    resolved: list[
        tuple[RequiredTargetFacet, GovernedCapabilityMapping, GovernedCapabilityBinding]
    ] = []
    for facet in required_facets:
        _validate_facet_source(facet, role_profile, requirement, learning_need)
        candidates = [
            item
            for item in governed_mappings
            if item.source_pin.source_ref == facet.source_pin.source_ref
        ]
        mismatched_pins = [item for item in candidates if item.source_pin != facet.source_pin]
        if mismatched_pins:
            # A same-identity stale record is relevant, not an unrelated context mapping.
            stale_candidate = sorted(
                mismatched_pins,
                key=lambda item: (item.mapping_id, item.mapping_fingerprint),
            )[0]
            resolve_governed_mapping_for_use(
                stale_candidate,
                current_source_pin=facet.source_pin,
                active_release_context=active_release_context,
            )
        exact = sorted(
            (item for item in candidates if item.source_pin == facet.source_pin),
            key=lambda item: item.mapping_id,
        )
        if not exact:
            if candidates:
                # Ask the canonical resolver to report stale/deprecated/authority state.
                resolve_governed_mapping_for_use(
                    sorted(candidates, key=lambda item: item.mapping_id)[0],
                    current_source_pin=facet.source_pin,
                    active_release_context=active_release_context,
                )
            raise TargetAdapterError(
                TargetAdapterErrorCode.UNRESOLVED_CAPABILITY,
                f"no governed mapping for required facet {facet.facet_id}",
            )
        for mapping in exact:
            binding = resolve_governed_mapping_for_use(
                mapping,
                current_source_pin=facet.source_pin,
                active_release_context=active_release_context,
                mapping_context=tuple(exact),
            )
            resolved.append((facet, mapping, binding))

    canonical_by_facet: dict[str, set[str]] = defaultdict(set)
    pins_by_canonical: dict[str, set[CapabilityDefinitionPin]] = defaultdict(set)
    for facet, mapping, _ in resolved:
        canonical = str(mapping.target_definition_pin.capability_ref)
        canonical_by_facet[facet.facet_id].add(canonical)
        pins_by_canonical[canonical].add(mapping.target_definition_pin)
    if any(len(values) > 1 for values in canonical_by_facet.values()):
        raise TargetAdapterError(TargetAdapterErrorCode.CANONICAL_BINDING_CONFLICT)
    if any(len(values) > 1 for values in pins_by_canonical.values()):
        raise TargetAdapterError(
            TargetAdapterErrorCode.CANONICAL_BINDING_CONFLICT,
            "one canonical capability resolved to inconsistent definition pins",
        )

    need_level = learning_need.target_state.level
    role_level = requirement.target_level
    if need_level is not None and role_level is not None and need_level != role_level:
        raise TargetAdapterError(TargetAdapterErrorCode.TARGET_LEVEL_CONFLICT)
    refs = tuple(CanonicalCapabilityRef.parse(value) for value in sorted(pins_by_canonical))
    target = RecommendationTarget(
        target_ref=learning_need.target_reference,
        target_capability_refs=[str(item) for item in refs],
        target_level=need_level if need_level is not None else role_level,
        source_learning_need_ref=learning_need.id,
        source_learning_path_ref=source_learning_path_ref,
        source_path_step_ref=source_path_step_ref,
        source_gap_refs=sorted(learning_need.source_gap_refs),
        source_role_requirement_refs=[requirement.id],
        prerequisite_context=prerequisite_context or RecommendationPrerequisiteContext(),
    )

    ordered = sorted(
        resolved,
        key=lambda row: (
            str(row[1].target_definition_pin.capability_ref),
            row[1].mapping_id,
            row[0].facet_id,
        ),
    )
    provenance = tuple(
        GovernedMappingProvenance(
            facet_id=facet.facet_id,
            source_ref=mapping.source_pin.source_ref,
            mapping_id=mapping.mapping_id,
            mapping_fingerprint=mapping.mapping_fingerprint,
            proposal_id=mapping.proposal_id,
            proposal_fingerprint=mapping.proposal_fingerprint,
            review_fingerprint=mapping.review_fingerprint,
            activation_approval_ref=mapping.activation_approval_ref,
            approver_ref=mapping.approver_ref,
            mapping_scope=mapping.mapping_scope,
            target_definition_pin=mapping.target_definition_pin,
        )
        for facet, mapping, _ in ordered
    )
    definition_pins = tuple(pins_by_canonical[key].pop() for key in sorted(pins_by_canonical))
    return GovernedRecommendationTargetProjection(
        recommendation_target=target,
        canonical_capability_refs=refs,
        bindings=tuple(binding for _, _, binding in ordered),
        definition_pins=definition_pins,
        mapping_provenance=provenance,
        role_profile_id=role_profile.id,
        role_profile_version=role_profile.version,
        role_requirement=requirement,
        gap_profile_id=gap_profile.id,
        gap_analysis_version=gap_profile.analysis_version,
        gap_target_id=track.target_id,
        gap_target_version=target_version,
        gap_entries=gap_entries,
        source_gap_refs=tuple(sorted(learning_need.source_gap_refs)),
        learning_need=learning_need,
        usage_mode=learning_need.usage_mode,
        warning_codes=tuple(sorted(set(track.warning_codes + learning_need.warning_codes))),
    )


def _requirement(role_profile: RoleCompetencyProfile, need: LearningNeedProfile) -> RoleRequirement:
    matches = [item for item in role_profile.requirements if item.id == need.competency.id]
    if len(matches) != 1:
        raise TargetAdapterError(
            TargetAdapterErrorCode.LINEAGE_MISMATCH,
            "requirement identity is missing or ambiguous",
        )
    if need.requirement_reference != matches[0].id:
        raise TargetAdapterError(
            TargetAdapterErrorCode.LINEAGE_MISMATCH,
            "LearningNeed requirement reference is missing or differs",
        )
    return matches[0]


def _select_track(
    role_profile: RoleCompetencyProfile,
    gap_profile: CapabilityGapProfile,
    need: LearningNeedProfile,
) -> tuple[CapabilityGapProfileTrack, str]:
    tracks = [(gap_profile.current_role, gap_profile.current_target_version)]
    if gap_profile.future_role is not None and gap_profile.future_target_version is not None:
        tracks.append((gap_profile.future_role, gap_profile.future_target_version))
    matches = [
        (track, version)
        for track, version in tracks
        if track.target_id == role_profile.id == need.provenance.target_id
        and version == role_profile.version == need.provenance.target_version
    ]
    if len(matches) != 1:
        raise TargetAdapterError(
            TargetAdapterErrorCode.IDENTITY_CONFLICT,
            "role profile and LearningNeed do not pin exactly one gap target track",
        )
    track, version = matches[0]
    if need.target_reference != f"{track.target_id}@{version}":
        raise TargetAdapterError(
            TargetAdapterErrorCode.LINEAGE_MISMATCH, "target reference is not the selected track"
        )
    return track, version


def _validate_need_lineage(
    requirement: RoleRequirement,
    gap_profile: CapabilityGapProfile,
    track: CapabilityGapProfileTrack,
    target_version: str,
    need: LearningNeedProfile,
) -> tuple[CapabilityGapProfileEntry, ...]:
    if (
        need.provenance.analysis_id != gap_profile.id
        or need.provenance.analysis_version != gap_profile.analysis_version
        or need.provenance.source_profile_id != gap_profile.cv_profile_id
        or need.provenance.source_profile_version != gap_profile.cv_profile_version
    ):
        raise TargetAdapterError(
            TargetAdapterErrorCode.LINEAGE_MISMATCH, "analysis provenance differs"
        )
    entries = tuple(item for item in track.entries if item.requirement_id == requirement.id)
    if len(entries) != 1:
        raise TargetAdapterError(
            TargetAdapterErrorCode.LINEAGE_MISMATCH,
            "requirement is absent or ambiguous in selected gap track",
        )
    source_gap_ids = {item.gap_id for item in entries if item.gap_id is not None}
    if not need.source_gap_refs or not set(need.source_gap_refs).issubset(source_gap_ids):
        raise TargetAdapterError(
            TargetAdapterErrorCode.LINEAGE_MISMATCH,
            "LearningNeed source gaps do not belong to requirement",
        )
    if len(need.source_gap_refs) != len(set(need.source_gap_refs)):
        raise TargetAdapterError(
            TargetAdapterErrorCode.LINEAGE_MISMATCH,
            "LearningNeed source gap refs contain duplicates",
        )
    for gap_ref in need.source_gap_refs:
        matching = [item for item in track.entries if item.gap_id == gap_ref]
        if len(matching) != 1 or matching[0].requirement_id != requirement.id:
            raise TargetAdapterError(
                TargetAdapterErrorCode.LINEAGE_MISMATCH,
                "source gap is not uniquely linked to requirement",
            )
    if (
        need.provenance.target_id != track.target_id
        or need.provenance.target_version != target_version
    ):
        raise TargetAdapterError(
            TargetAdapterErrorCode.LINEAGE_MISMATCH, "target provenance differs"
        )
    return entries


def _validate_facet_source(
    facet: RequiredTargetFacet,
    role_profile: RoleCompetencyProfile,
    requirement: RoleRequirement,
    need: LearningNeedProfile,
) -> None:
    ref = facet.source_pin.source_ref
    if ref.entity_kind is SourceSemanticKind.ROLE_REQUIREMENT:
        valid = (
            ref.source_namespace == "role_profile"
            and ref.source_id == requirement.id
            and ref.source_version == role_profile.version
        )
    elif ref.entity_kind is SourceSemanticKind.LEARNING_NEED_COMPETENCY:
        # LearningNeedProfile has no independent version field: preserve the supplied pin.
        valid = ref.source_namespace == "learning_need" and ref.source_id == need.competency.id
    else:
        valid = False
    if not valid:
        raise TargetAdapterError(
            TargetAdapterErrorCode.INVALID_FACET,
            f"source identity does not match required facet {facet.facet_id}",
        )
