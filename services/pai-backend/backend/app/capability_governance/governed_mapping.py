"""Explicitly approved, exact capability mapping authority (3D-3B)."""

import json
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.capability_governance.mapping import (
    CapabilityMappingProposal,
    CapabilityMappingReview,
    MappingDecision,
    MappingScope,
    MappingType,
    validate_mapping_review_for_proposal,
)
from app.capability_governance.mapping_activation import (
    MappingActivationApproval,
    SourceSemanticPin,
    build_source_semantic_pin,
    fingerprint_mapping_review,
)
from app.capability_governance.mapping_errors import MappingGovernanceError
from app.capability_governance.packs import CapabilityPackRelease
from app.capability_governance.resolution import (
    CapabilityDefinitionPin,
    resolve_for_new_binding,
)


class GovernedMappingStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class MappingDeprecationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    actor_ref: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("actor_ref", "reason")
    @classmethod
    def reject_blank_or_surrounding_whitespace(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("deprecation values must be non-blank and exact")
        return value


class GovernedCapabilityMapping(BaseModel):
    """Immutable authority record for one reviewed exact semantic mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    mapping_id: str = Field(min_length=1, max_length=256)
    proposal_id: str = Field(min_length=1, max_length=256)
    proposal_fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    review_fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    source_pin: SourceSemanticPin
    target_definition_pin: CapabilityDefinitionPin
    mapping_type: MappingType
    mapping_scope: MappingScope
    activation_approval_ref: str = Field(min_length=1, max_length=256)
    approver_ref: str = Field(min_length=1, max_length=256)
    status: GovernedMappingStatus
    deprecation: MappingDeprecationRecord | None = None
    mapping_fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")

    @field_validator("mapping_id", "proposal_id", "activation_approval_ref", "approver_ref")
    @classmethod
    def reject_blank_or_surrounding_whitespace(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("mapping references must be non-blank and exact")
        return value

    @model_validator(mode="after")
    def validate_fingerprint_and_lifecycle(self) -> "GovernedCapabilityMapping":
        if (self.status is GovernedMappingStatus.DEPRECATED) != (self.deprecation is not None):
            raise ValueError("deprecated mappings require exactly one deprecation record")
        expected = _mapping_fingerprint(self)
        if expected != self.mapping_fingerprint:
            raise ValueError("mapping_fingerprint_mismatch")
        return self


def _mapping_fingerprint(mapping: GovernedCapabilityMapping) -> str:
    payload = {
        "mapping_id": mapping.mapping_id,
        "proposal_id": mapping.proposal_id,
        "proposal_fingerprint": mapping.proposal_fingerprint,
        "review_fingerprint": mapping.review_fingerprint,
        "source_pin": mapping.source_pin.model_dump(mode="json"),
        "target_definition_pin": mapping.target_definition_pin.model_dump(mode="json"),
        "mapping_type": mapping.mapping_type.value,
        "mapping_scope": mapping.mapping_scope.value,
        "activation_approval_ref": mapping.activation_approval_ref,
        "approver_ref": mapping.approver_ref,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(encoded.encode('utf-8')).hexdigest()}"


def activate_governed_mapping(
    *,
    mapping_id: str,
    proposal: CapabilityMappingProposal,
    review: CapabilityMappingReview,
    current_source_pin: SourceSemanticPin,
    activation_approval: MappingActivationApproval | None,
    active_release_context: tuple[CapabilityPackRelease, ...],
    existing_mappings: tuple[GovernedCapabilityMapping, ...] = (),
) -> GovernedCapabilityMapping:
    """Activate only the exact proposal/review/source/target covered by approval."""
    try:
        validate_mapping_review_for_proposal(proposal, review)
    except ValueError as exc:
        raise MappingGovernanceError("proposal_review_mismatch") from exc
    if review.decision is MappingDecision.REJECT:
        raise MappingGovernanceError("mapping_review_rejected")
    if review.decision is not MappingDecision.APPROVE:
        raise MappingGovernanceError("mapping_review_uncertain")

    actual_source_pin = build_source_semantic_pin(proposal.source_ref, proposal.evidence)
    if current_source_pin != actual_source_pin:
        raise MappingGovernanceError("stale_source")

    target_pin = resolve_for_new_binding(proposal.target_capability_ref, active_release_context)
    if target_pin.capability_ref != proposal.target_capability_ref:
        raise MappingGovernanceError("target_pin_mismatch")
    if activation_approval is None:
        raise MappingGovernanceError("activation_approval_required")

    expected_approval = (
        activation_approval.proposal_id == proposal.proposal_id
        and activation_approval.proposal_fingerprint == proposal.proposal_fingerprint
        and activation_approval.review_fingerprint == fingerprint_mapping_review(review)
        and activation_approval.source_pin == actual_source_pin
        and activation_approval.target_definition_pin == target_pin
    )
    if not expected_approval:
        raise MappingGovernanceError("activation_approval_mismatch")

    identity = {
        "mapping_id": mapping_id,
        "proposal_id": proposal.proposal_id,
        "proposal_fingerprint": proposal.proposal_fingerprint,
        "review_fingerprint": fingerprint_mapping_review(review),
        "source_pin": actual_source_pin,
        "target_definition_pin": target_pin,
        "mapping_type": proposal.mapping_type,
        "mapping_scope": proposal.mapping_scope,
        "activation_approval_ref": activation_approval.approval_ref,
        "approver_ref": activation_approval.approver_ref,
        "status": GovernedMappingStatus.ACTIVE,
        "deprecation": None,
    }
    fingerprint_payload = {
        "mapping_id": identity["mapping_id"],
        "proposal_id": identity["proposal_id"],
        "proposal_fingerprint": identity["proposal_fingerprint"],
        "review_fingerprint": identity["review_fingerprint"],
        "source_pin": actual_source_pin.model_dump(mode="json"),
        "target_definition_pin": target_pin.model_dump(mode="json"),
        "mapping_type": proposal.mapping_type.value,
        "mapping_scope": proposal.mapping_scope.value,
        "activation_approval_ref": activation_approval.approval_ref,
        "approver_ref": activation_approval.approver_ref,
    }
    encoded = json.dumps(
        fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    identity["mapping_fingerprint"] = f"sha256:{sha256(encoded.encode('utf-8')).hexdigest()}"
    candidate = GovernedCapabilityMapping.model_validate(identity)
    for existing in existing_mappings:
        if existing.status is not GovernedMappingStatus.ACTIVE:
            continue
        validate_governed_mapping_record(existing)
        if existing.mapping_id == candidate.mapping_id:
            if existing != candidate:
                raise MappingGovernanceError("mapping_id_conflict")
            return existing
        same_facet = (
            existing.source_pin.source_ref == candidate.source_pin.source_ref
            and existing.source_pin.evidence_fingerprint
            == candidate.source_pin.evidence_fingerprint
            and existing.mapping_scope is candidate.mapping_scope
            and existing.mapping_type is MappingType.EXACT
        )
        if same_facet and (
            existing.target_definition_pin.capability_ref
            != candidate.target_definition_pin.capability_ref
        ):
            raise MappingGovernanceError("mapping_conflict")
    return candidate


def deprecate_governed_mapping(
    mapping: GovernedCapabilityMapping,
    *,
    actor_ref: str,
    reason: str,
) -> GovernedCapabilityMapping:
    """Return a deprecated copy without changing its semantic authority pin."""
    validate_governed_mapping_record(mapping)
    if mapping.status is not GovernedMappingStatus.ACTIVE:
        raise MappingGovernanceError("mapping_not_active")
    return GovernedCapabilityMapping.model_validate(
        {
            **mapping.model_dump(mode="python"),
            "status": GovernedMappingStatus.DEPRECATED,
            "deprecation": MappingDeprecationRecord(actor_ref=actor_ref, reason=reason),
        }
    )


def validate_governed_mapping_record(mapping: GovernedCapabilityMapping) -> None:
    if _mapping_fingerprint(mapping) != mapping.mapping_fingerprint:
        raise MappingGovernanceError("mapping_fingerprint_mismatch")
