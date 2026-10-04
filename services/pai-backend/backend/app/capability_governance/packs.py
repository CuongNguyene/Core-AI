"""Exact capability pack releases, checksums, and pure lifecycle validation."""

import json
from collections.abc import Iterable
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from app.capability_governance.definitions import (
    CapabilityDefinition,
    CapabilityDefinitionStatus,
    CapabilityDeprecationRecord,
)
from app.capability_governance.errors import (
    ActivationGateError,
    ChecksumMismatchError,
    DependencyCycleError,
    DependencyNotActiveError,
    DuplicateCapabilityError,
    DuplicateReleaseError,
    InvalidLifecycleTransitionError,
    NamespaceConflictError,
)


class CapabilityPackId(RootModel[str]):
    """Stable pack identity independent of namespace and release version."""

    model_config = ConfigDict(strict=True, frozen=True)

    root: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")

    def __str__(self) -> str:
        return self.root


class CapabilityPackStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class CapabilityGovernanceDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class CapabilityPackReleaseRef(BaseModel):
    """An exact immutable pack/version/content reference."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    pack_id: CapabilityPackId
    version: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
    checksum: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")

    @field_validator("version")
    @classmethod
    def reject_moving_version_selectors(cls, value: str) -> str:
        if value.casefold() in {"latest", "current"}:
            raise ValueError("pack release references require an exact version")
        return value


class CapabilityPackDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    release_ref: CapabilityPackReleaseRef


class CapabilityGovernanceReview(BaseModel):
    """Semantic review evidence, separate from release approval and RBAC."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    review_ref: str = Field(min_length=1, max_length=256)
    reviewer_ref: str = Field(min_length=1, max_length=256)
    decision: CapabilityGovernanceDecision
    collision_review_ref: str = Field(min_length=1, max_length=256)

    @field_validator("review_ref", "reviewer_ref", "collision_review_ref")
    @classmethod
    def reject_blank_or_trimmed_values(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("review references must be non-blank and exact")
        return value


class CapabilityReleaseApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    approval_ref: str = Field(min_length=1, max_length=256)
    approver_ref: str = Field(min_length=1, max_length=256)
    decision: CapabilityGovernanceDecision

    @field_validator("approval_ref", "approver_ref")
    @classmethod
    def reject_blank_or_trimmed_values(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("approval references must be non-blank and exact")
        return value


class CapabilityPackRelease(BaseModel):
    """Frozen definition snapshot plus lifecycle and governance metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    pack_id: CapabilityPackId
    namespace_key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    version: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
    status: CapabilityPackStatus = CapabilityPackStatus.DRAFT
    definitions: tuple[CapabilityDefinition, ...] = Field(min_length=1)
    dependencies: tuple[CapabilityPackDependency, ...] = ()
    owner_ref: str = Field(min_length=1, max_length=256)
    content_checksum: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    review: CapabilityGovernanceReview | None = None
    approval: CapabilityReleaseApproval | None = None
    deprecation: CapabilityDeprecationRecord | None = None

    @field_validator("version")
    @classmethod
    def reject_moving_version_selectors(cls, value: str) -> str:
        if value.casefold() in {"latest", "current"}:
            raise ValueError("pack release versions must be exact")
        return value

    @field_validator("owner_ref")
    @classmethod
    def reject_surrounding_owner_whitespace(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("owner_ref must be non-blank and exact")
        return value

    @model_validator(mode="after")
    def validate_release_contract(self) -> "CapabilityPackRelease":
        if not self.definitions:
            raise ValueError("capability pack releases require at least one definition")

        capability_refs = [str(item.canonical_ref) for item in self.definitions]
        if len(capability_refs) != len(set(capability_refs)):
            raise ValueError("duplicate capability refs are not allowed in a release")

        if any(item.canonical_ref.namespace_key != self.namespace_key for item in self.definitions):
            raise ValueError("definition namespace must match the pack namespace")

        dependency_keys = [
            (str(item.release_ref.pack_id), item.release_ref.version) for item in self.dependencies
        ]
        if len(dependency_keys) != len(set(dependency_keys)):
            raise ValueError("duplicate dependency release is not allowed")

        if self.status is CapabilityPackStatus.DRAFT:
            if any(
                item.status is not CapabilityDefinitionStatus.DRAFT for item in self.definitions
            ):
                raise ValueError("draft releases must contain draft definitions")
        elif self.status is CapabilityPackStatus.ACTIVE:
            if self.review is None or self.approval is None:
                raise ValueError("active releases require review and approval metadata")
            if self.review.decision is not CapabilityGovernanceDecision.APPROVE:
                raise ValueError("active releases require an approved semantic review")
            if self.approval.decision is not CapabilityGovernanceDecision.APPROVE:
                raise ValueError("active releases require explicit approval")
            if self.review.reviewer_ref == self.owner_ref:
                raise ValueError("active release reviewer must be independent from owner")
            if any(item.status is CapabilityDefinitionStatus.DRAFT for item in self.definitions):
                raise ValueError("active releases cannot contain draft definitions")
        else:
            if self.deprecation is None:
                raise ValueError("deprecated releases require a deprecation record")
            if any(item.status is CapabilityDefinitionStatus.DRAFT for item in self.definitions):
                raise ValueError("deprecated releases cannot contain draft definitions")

        expected_checksum = compute_release_checksum(
            pack_id=self.pack_id,
            namespace_key=self.namespace_key,
            version=self.version,
            definitions=self.definitions,
            dependencies=self.dependencies,
        )
        if self.content_checksum != expected_checksum:
            raise ValueError("release content checksum does not match semantic payload")
        return self


def compute_release_checksum(
    *,
    pack_id: CapabilityPackId,
    namespace_key: str,
    version: str,
    definitions: Iterable[CapabilityDefinition],
    dependencies: Iterable[CapabilityPackDependency] = (),
) -> str:
    """Hash stable semantic content; lifecycle and governance are excluded."""
    definition_payload = sorted(
        (
            {
                "canonical_ref": str(item.canonical_ref),
                "label": item.label,
                "definition": item.definition,
            }
            for item in definitions
        ),
        key=lambda item: item["canonical_ref"],
    )
    dependency_payload = sorted(
        (
            {
                "pack_id": str(item.release_ref.pack_id),
                "version": item.release_ref.version,
                "checksum": item.release_ref.checksum,
            }
            for item in dependencies
        ),
        key=lambda item: (item["pack_id"], item["version"], item["checksum"]),
    )
    payload = {
        "pack_id": str(pack_id),
        "namespace_key": namespace_key,
        "version": version,
        "definitions": definition_payload,
        "dependencies": dependency_payload,
    }
    canonical_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{sha256(canonical_json.encode('utf-8')).hexdigest()}"


def build_capability_pack_release(
    *,
    pack_id: str | CapabilityPackId,
    namespace_key: str,
    version: str,
    owner_ref: str,
    definitions: Iterable[CapabilityDefinition],
    dependencies: Iterable[CapabilityPackDependency] = (),
) -> CapabilityPackRelease:
    stable_pack_id = pack_id if isinstance(pack_id, CapabilityPackId) else CapabilityPackId(pack_id)
    stable_definitions = tuple(definitions)
    stable_dependencies = tuple(dependencies)
    checksum = compute_release_checksum(
        pack_id=stable_pack_id,
        namespace_key=namespace_key,
        version=version,
        definitions=stable_definitions,
        dependencies=stable_dependencies,
    )
    return CapabilityPackRelease(
        pack_id=stable_pack_id,
        namespace_key=namespace_key,
        version=version,
        definitions=stable_definitions,
        dependencies=stable_dependencies,
        owner_ref=owner_ref,
        content_checksum=checksum,
    )


def activate_capability_pack_release(
    release: CapabilityPackRelease,
    *,
    review: CapabilityGovernanceReview | None,
    approval: CapabilityReleaseApproval | None,
    existing_releases: tuple[CapabilityPackRelease, ...] = (),
) -> CapabilityPackRelease:
    if release.status is not CapabilityPackStatus.DRAFT:
        raise InvalidLifecycleTransitionError("release_must_be_draft")
    if any(item.status is not CapabilityDefinitionStatus.DRAFT for item in release.definitions):
        raise ActivationGateError("activation_requires_draft_definitions")
    if review is None or approval is None:
        raise ActivationGateError("semantic_review_and_explicit_approval_required")
    if review.decision is not CapabilityGovernanceDecision.APPROVE:
        raise ActivationGateError("semantic_review_rejected")
    if approval.decision is not CapabilityGovernanceDecision.APPROVE:
        raise ActivationGateError("release_approval_rejected")
    if review.reviewer_ref == release.owner_ref:
        raise ActivationGateError("reviewer_must_be_independent")
    if not review.collision_review_ref:
        raise ActivationGateError("semantic_collision_review_required")

    _validate_release_graph(release, existing_releases)
    _validate_namespace_ownership(release, existing_releases)
    _validate_active_capability_collisions(release, existing_releases)
    _validate_dependency_closure(
        release,
        existing_releases,
        historical=False,
    )

    active_definitions = tuple(
        CapabilityDefinition.model_validate(
            {
                **definition.model_dump(mode="python"),
                "status": CapabilityDefinitionStatus.ACTIVE,
            }
        )
        for definition in release.definitions
    )
    return CapabilityPackRelease.model_validate(
        {
            **release.model_dump(mode="python"),
            "status": CapabilityPackStatus.ACTIVE,
            "definitions": active_definitions,
            "review": review,
            "approval": approval,
        }
    )


def deprecate_capability_pack_release(
    release: CapabilityPackRelease,
    *,
    actor_ref: str,
    reason: str,
) -> CapabilityPackRelease:
    if release.status is not CapabilityPackStatus.ACTIVE:
        raise InvalidLifecycleTransitionError("invalid_release_transition")
    return CapabilityPackRelease.model_validate(
        {
            **release.model_dump(mode="python"),
            "status": CapabilityPackStatus.DEPRECATED,
            "deprecation": CapabilityDeprecationRecord(actor_ref=actor_ref, reason=reason),
        }
    )


def validate_release_authority_context(
    releases: tuple[CapabilityPackRelease, ...],
) -> None:
    _validate_release_graph(None, releases)
    _validate_namespace_ownership(None, releases)
    _validate_active_capability_collisions(None, releases)


def validate_dependency_closure(
    release: CapabilityPackRelease,
    releases: tuple[CapabilityPackRelease, ...],
    *,
    historical: bool,
) -> None:
    _validate_release_graph(release, releases)
    _validate_dependency_closure(release, releases, historical=historical)


def _release_key(release: CapabilityPackRelease) -> tuple[str, str]:
    return str(release.pack_id), release.version


def _release_index(
    candidate: CapabilityPackRelease | None,
    releases: tuple[CapabilityPackRelease, ...],
) -> dict[tuple[str, str], CapabilityPackRelease]:
    index: dict[tuple[str, str], CapabilityPackRelease] = {}
    for item in (*releases, *((candidate,) if candidate is not None else ())):
        key = _release_key(item)
        if key in index:
            raise DuplicateReleaseError(f"duplicate pack release: {key[0]}@{key[1]}")
        index[key] = item
    return index


def _validate_release_graph(
    candidate: CapabilityPackRelease | None,
    releases: tuple[CapabilityPackRelease, ...],
) -> None:
    index = _release_index(candidate, releases)
    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()

    def visit(key: tuple[str, str]) -> None:
        if key in visiting:
            raise DependencyCycleError(f"capability pack dependency cycle at {key[0]}@{key[1]}")
        if key in visited:
            return
        visiting.add(key)
        for dependency in index[key].dependencies:
            dependency_key = (
                str(dependency.release_ref.pack_id),
                dependency.release_ref.version,
            )
            if dependency_key in index:
                visit(dependency_key)
        visiting.remove(key)
        visited.add(key)

    for key in sorted(index):
        visit(key)


def _validate_namespace_ownership(
    candidate: CapabilityPackRelease | None,
    releases: tuple[CapabilityPackRelease, ...],
) -> None:
    namespace_owners: dict[str, str] = {}
    pack_namespaces: dict[str, str] = {}
    known_releases = list(releases)
    if candidate is not None:
        known_releases.append(candidate)

    for item in known_releases:
        owner = str(item.pack_id)
        previous_owner = namespace_owners.setdefault(item.namespace_key, owner)
        if previous_owner != owner:
            raise NamespaceConflictError(
                f"namespace {item.namespace_key} is assigned to multiple pack identities"
            )
        previous_namespace = pack_namespaces.setdefault(owner, item.namespace_key)
        if previous_namespace != item.namespace_key:
            raise NamespaceConflictError(
                f"pack {owner} cannot change its namespace across releases"
            )


def _validate_active_capability_collisions(
    candidate: CapabilityPackRelease | None,
    releases: tuple[CapabilityPackRelease, ...],
) -> None:
    active_releases = [item for item in releases if item.status is CapabilityPackStatus.ACTIVE]
    if candidate is not None:
        active_releases.append(candidate)

    owners: dict[str, tuple[str, str]] = {}
    for release in active_releases:
        release_key = _release_key(release)
        for definition in release.definitions:
            capability_ref = str(definition.canonical_ref)
            previous_release = owners.setdefault(capability_ref, release_key)
            if previous_release != release_key:
                raise DuplicateCapabilityError(
                    f"canonical capability is active in multiple releases: {capability_ref}"
                )


def _validate_dependency_closure(
    release: CapabilityPackRelease,
    releases: tuple[CapabilityPackRelease, ...],
    *,
    historical: bool,
) -> None:
    index = _release_index(release, releases)
    visited: set[tuple[str, str]] = set()

    def visit(current: CapabilityPackRelease) -> None:
        for dependency in current.dependencies:
            reference = dependency.release_ref
            key = (str(reference.pack_id), reference.version)
            resolved = index.get(key)
            if resolved is None:
                raise DependencyNotActiveError(f"dependency release is missing: {key[0]}@{key[1]}")
            if resolved.content_checksum != reference.checksum:
                raise ChecksumMismatchError(f"dependency checksum mismatch: {key[0]}@{key[1]}")
            allowed = (
                {CapabilityPackStatus.ACTIVE, CapabilityPackStatus.DEPRECATED}
                if historical
                else {CapabilityPackStatus.ACTIVE}
            )
            if resolved.status not in allowed:
                raise DependencyNotActiveError(
                    f"dependency release is not eligible: {key[0]}@{key[1]}"
                )
            if key not in visited:
                visited.add(key)
                visit(resolved)

    visit(release)
