"""Pure active and historical capability definition resolution."""

from pydantic import BaseModel, ConfigDict

from app.capability_governance.definitions import CapabilityDefinitionStatus
from app.capability_governance.errors import (
    CapabilityNotActiveError,
    ChecksumMismatchError,
    PackNotActiveError,
    ReleaseNotFoundError,
    UnknownCapabilityError,
    UnknownNamespaceError,
)
from app.capability_governance.identity import CanonicalCapabilityRef
from app.capability_governance.packs import (
    CapabilityPackRelease,
    CapabilityPackReleaseRef,
    CapabilityPackStatus,
    validate_dependency_closure,
    validate_release_authority_context,
)


class CapabilityDefinitionPin(BaseModel):
    """Pins a canonical capability definition to one exact immutable release."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    capability_ref: CanonicalCapabilityRef
    pack_release_ref: CapabilityPackReleaseRef


def resolve_for_new_binding(
    capability_ref: CanonicalCapabilityRef,
    active_release_context: tuple[CapabilityPackRelease, ...],
) -> CapabilityDefinitionPin:
    """Resolve only one unambiguous ACTIVE definition and its exact release."""
    namespace_releases = tuple(
        item
        for item in active_release_context
        if item.namespace_key == capability_ref.namespace_key
    )
    registered_namespace = any(
        item.namespace_key == capability_ref.namespace_key for item in active_release_context
    )
    if not registered_namespace:
        raise UnknownNamespaceError(
            f"canonical namespace is not registered: {capability_ref.namespace_key}"
        )

    validate_release_authority_context(active_release_context)
    active_namespace_releases = tuple(
        item for item in namespace_releases if item.status is CapabilityPackStatus.ACTIVE
    )
    if not active_namespace_releases:
        raise PackNotActiveError(
            f"no active pack release owns namespace {capability_ref.namespace_key}"
        )

    registered_capability = any(
        definition.canonical_ref == capability_ref
        for item in active_release_context
        for definition in item.definitions
    )
    if not registered_capability:
        raise UnknownCapabilityError(f"capability is not registered: {capability_ref}")

    matches = [
        (release, definition)
        for release in active_namespace_releases
        for definition in release.definitions
        if definition.canonical_ref == capability_ref
    ]
    if len(matches) > 1:
        raise CapabilityNotActiveError(
            f"ambiguous active capability authority for {capability_ref}"
        )
    if not matches:
        raise CapabilityNotActiveError(
            f"capability is not active for new bindings: {capability_ref}"
        )

    release, definition = matches[0]
    if definition.status is not CapabilityDefinitionStatus.ACTIVE:
        raise CapabilityNotActiveError(
            f"capability is not active for new bindings: {capability_ref}"
        )

    other_releases = tuple(
        item
        for item in active_release_context
        if (str(item.pack_id), item.version) != (str(release.pack_id), release.version)
    )
    validate_dependency_closure(release, other_releases, historical=False)
    return CapabilityDefinitionPin(
        capability_ref=capability_ref,
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=release.pack_id,
            version=release.version,
            checksum=release.content_checksum,
        ),
    )


def resolve_historical(
    definition_pin: CapabilityDefinitionPin,
    release_context: tuple[CapabilityPackRelease, ...],
) -> CapabilityDefinitionPin:
    """Resolve the exact historical definition without applying replacements."""
    reference = definition_pin.pack_release_ref
    matches = [
        item
        for item in release_context
        if str(item.pack_id) == str(reference.pack_id) and item.version == reference.version
    ]
    if not matches:
        raise ReleaseNotFoundError(
            f"pack release not found: {reference.pack_id}@{reference.version}"
        )
    if len(matches) > 1:
        raise ReleaseNotFoundError(
            f"pack release identity is ambiguous: {reference.pack_id}@{reference.version}"
        )

    release = matches[0]
    if release.content_checksum != reference.checksum:
        raise ChecksumMismatchError(
            f"pack release checksum does not match: {reference.pack_id}@{reference.version}"
        )
    if release.status is CapabilityPackStatus.DRAFT:
        raise PackNotActiveError("draft releases cannot resolve as historical authority")

    definition = next(
        (
            item
            for item in release.definitions
            if item.canonical_ref == definition_pin.capability_ref
        ),
        None,
    )
    if definition is None:
        raise UnknownCapabilityError(
            f"capability is absent from pinned release: {definition_pin.capability_ref}"
        )
    if definition.status is CapabilityDefinitionStatus.DRAFT:
        raise CapabilityNotActiveError("draft definitions cannot resolve as historical authority")

    other_releases = tuple(
        item
        for item in release_context
        if (str(item.pack_id), item.version) != (str(release.pack_id), release.version)
    )
    validate_dependency_closure(release, other_releases, historical=True)
    return definition_pin
