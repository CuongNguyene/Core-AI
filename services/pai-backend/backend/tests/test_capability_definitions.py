import pytest
from pydantic import ValidationError

from app.capability_governance.definitions import (
    CapabilityDefinition,
    CapabilityDefinitionStatus,
    CapabilityDeprecationRecord,
    deprecate_capability_definition,
)
from app.capability_governance.identity import CanonicalCapabilityRef


def _definition(
    *,
    ref: str = "capability:test_core:project_management",
    label: str = "Project Management",
    definition: str = "Plan and coordinate project delivery.",
) -> CapabilityDefinition:
    return CapabilityDefinition(
        canonical_ref=CanonicalCapabilityRef.parse(ref),
        label=label,
        definition=definition,
    )


def test_definition_retains_canonical_identity_and_keeps_label_separate() -> None:
    definition = _definition()

    assert str(definition.canonical_ref) == "capability:test_core:project_management"
    assert definition.label == "Project Management"
    assert definition.identity_key == definition.canonical_ref


@pytest.mark.parametrize("field", ["label", "definition"])
def test_definition_rejects_empty_human_readable_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        _definition(**{field: ""})


def test_definition_rejects_whitespace_only_human_readable_fields() -> None:
    with pytest.raises(ValidationError):
        _definition(label=" ")

    with pytest.raises(ValidationError):
        _definition(definition="  ")


def test_definition_lifecycle_and_replacement_are_metadata_not_redirects() -> None:
    deprecated = _definition().model_copy(
        update={
            "status": CapabilityDefinitionStatus.DEPRECATED,
            "replacement_ref": CanonicalCapabilityRef.parse(
                "capability:test_core:delivery_planning"
            ),
            "deprecation": CapabilityDeprecationRecord(
                actor_ref="actor:owner",
                reason="Definition superseded after governance review.",
            ),
        }
    )

    assert deprecated.status is CapabilityDefinitionStatus.DEPRECATED
    assert deprecated.replacement_ref is not None
    assert deprecated.canonical_ref != deprecated.replacement_ref


def test_deprecation_requires_active_definition_and_preserves_old_identity() -> None:
    definition = _definition().model_copy(update={"status": CapabilityDefinitionStatus.ACTIVE})

    deprecated = deprecate_capability_definition(
        definition,
        actor_ref="actor:owner",
        reason="Retained for historical references.",
        replacement_ref=CanonicalCapabilityRef.parse("capability:test_core:delivery_planning"),
    )

    assert deprecated.canonical_ref == definition.canonical_ref
    assert deprecated.status is CapabilityDefinitionStatus.DEPRECATED
    assert deprecated.replacement_ref != deprecated.canonical_ref
    with pytest.raises(ValueError, match="invalid_definition_transition"):
        deprecate_capability_definition(
            deprecated, actor_ref="actor:owner", reason="deprecate again"
        )


def test_definition_cannot_replace_itself() -> None:
    with pytest.raises(ValidationError):
        CapabilityDefinition(
            canonical_ref=CanonicalCapabilityRef.parse("capability:test_core:project_management"),
            label="Project Management",
            definition="Coordinate projects.",
            status=CapabilityDefinitionStatus.DEPRECATED,
            replacement_ref=CanonicalCapabilityRef.parse("capability:test_core:project_management"),
            deprecation=CapabilityDeprecationRecord(
                actor_ref="actor:owner", reason="same identity"
            ),
        )


def test_definition_requires_deprecation_metadata_only_when_deprecated() -> None:
    with pytest.raises(ValidationError):
        CapabilityDefinition(
            canonical_ref=CanonicalCapabilityRef.parse("capability:test_core:project_management"),
            label="Project Management",
            definition="Coordinate projects.",
            status=CapabilityDefinitionStatus.DEPRECATED,
        )
