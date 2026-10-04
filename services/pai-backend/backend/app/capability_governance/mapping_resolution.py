"""Current-use and exact historical resolution for governed mappings."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.capability_governance.governed_mapping import (
    GovernedCapabilityMapping,
    GovernedMappingStatus,
    validate_governed_mapping_record,
)
from app.capability_governance.identity import SourceSemanticRef
from app.capability_governance.mapping import MappingScope, MappingType
from app.capability_governance.mapping_activation import SourceSemanticPin
from app.capability_governance.mapping_errors import MappingGovernanceError
from app.capability_governance.packs import CapabilityPackRelease
from app.capability_governance.resolution import (
    CapabilityDefinitionPin,
    resolve_for_new_binding,
    resolve_historical,
)


class BindingResolutionMode(StrEnum):
    CURRENT = "current"
    HISTORICAL = "historical"


class GovernedCapabilityBinding(BaseModel):
    """A domain-neutral result; not a recommendation or learner profile."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_ref: SourceSemanticRef
    mapping_scope: MappingScope
    mapping_id: str
    mapping_fingerprint: str
    target_definition_pin: CapabilityDefinitionPin
    resolution_mode: BindingResolutionMode


def resolve_governed_mapping_for_use(
    mapping: GovernedCapabilityMapping,
    *,
    current_source_pin: SourceSemanticPin,
    active_release_context: tuple[CapabilityPackRelease, ...],
    mapping_context: tuple[GovernedCapabilityMapping, ...] = (),
) -> GovernedCapabilityBinding:
    """Require fresh source and currently active exact target authority."""
    validate_governed_mapping_record(mapping)
    if mapping.status is GovernedMappingStatus.DEPRECATED:
        raise MappingGovernanceError("mapping_deprecated")
    if current_source_pin != mapping.source_pin:
        raise MappingGovernanceError("stale_source")

    target_pin = resolve_for_new_binding(
        mapping.target_definition_pin.capability_ref, active_release_context
    )
    if target_pin != mapping.target_definition_pin:
        raise MappingGovernanceError("target_pin_mismatch")

    for other in mapping_context:
        validate_governed_mapping_record(other)
        if (
            other.status is GovernedMappingStatus.ACTIVE
            and other.mapping_id != mapping.mapping_id
            and other.mapping_type is MappingType.EXACT
            and other.source_pin.source_ref == mapping.source_pin.source_ref
            and other.source_pin.evidence_fingerprint == mapping.source_pin.evidence_fingerprint
            and other.mapping_scope is mapping.mapping_scope
            and other.target_definition_pin.capability_ref
            != mapping.target_definition_pin.capability_ref
        ):
            raise MappingGovernanceError("mapping_conflict")

    return _binding(mapping, BindingResolutionMode.CURRENT)


def resolve_governed_mapping_historical(
    mapping: GovernedCapabilityMapping,
    *,
    historical_source_pin: SourceSemanticPin,
    release_context: tuple[CapabilityPackRelease, ...],
) -> GovernedCapabilityBinding:
    """Resolve exact historical source and target pins without redirects."""
    validate_governed_mapping_record(mapping)
    if historical_source_pin != mapping.source_pin:
        raise MappingGovernanceError("stale_source")
    resolve_historical(mapping.target_definition_pin, release_context)
    return _binding(mapping, BindingResolutionMode.HISTORICAL)


def _binding(
    mapping: GovernedCapabilityMapping,
    mode: BindingResolutionMode,
) -> GovernedCapabilityBinding:
    return GovernedCapabilityBinding(
        source_ref=mapping.source_pin.source_ref,
        mapping_scope=mapping.mapping_scope,
        mapping_id=mapping.mapping_id,
        mapping_fingerprint=mapping.mapping_fingerprint,
        target_definition_pin=mapping.target_definition_pin,
        resolution_mode=mode,
    )
