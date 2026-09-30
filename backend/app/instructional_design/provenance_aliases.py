"""Explicit deterministic dependency identities for provenance resolution."""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from app.instructional_design.schemas import AssessmentDependencyCandidate


def normalize_dependency_identity(value: str) -> str:
    """Normalize only Unicode form, case, and whitespace."""

    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


@dataclass(frozen=True)
class DependencyIdentity:
    """Research/config-owned canonical dependency identity and aliases."""

    dependency_ref: str
    canonical_name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class DependencyIdentityResolution:
    dependency_ref: str | None
    conflict: bool


def resolve_dependency_identity(
    value: str,
    candidates: Sequence[AssessmentDependencyCandidate],
    *,
    identities: Sequence[DependencyIdentity] = (),
) -> DependencyIdentityResolution:
    """Resolve a value against canonical names or explicitly declared aliases.

    Candidate identities without explicit metadata use their exact normalized
    capability as the canonical name. Aliases are never generated from model
    output and multiple matches fail closed.
    """

    candidate_keys = {
        normalize_dependency_identity(candidate.capability) for candidate in candidates
    }
    allowed_identities = [
        identity
        for identity in identities
        if normalize_dependency_identity(identity.canonical_name) in candidate_keys
    ]
    for candidate in candidates:
        canonical = normalize_dependency_identity(candidate.capability)
        if not any(normalize_dependency_identity(item.canonical_name) == canonical for item in allowed_identities):
            allowed_identities.append(
                DependencyIdentity(
                    dependency_ref=f"dependency_candidate:{canonical}",
                    canonical_name=canonical,
                )
            )

    normalized_value = normalize_dependency_identity(value)
    matches = [
        identity
        for identity in allowed_identities
        if normalized_value == normalize_dependency_identity(identity.canonical_name)
        or normalized_value in {normalize_dependency_identity(alias) for alias in identity.aliases}
    ]
    if len(matches) != 1:
        return DependencyIdentityResolution(
            dependency_ref=None,
            conflict=len(matches) > 1,
        )
    return DependencyIdentityResolution(
        dependency_ref=matches[0].dependency_ref,
        conflict=False,
    )
