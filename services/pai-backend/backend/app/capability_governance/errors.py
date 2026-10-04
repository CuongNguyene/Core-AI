"""Stable failures raised by capability definition governance."""


class CapabilityGovernanceError(ValueError):
    code = "capability_governance_error"


class UnknownNamespaceError(CapabilityGovernanceError):
    code = "unknown_namespace"


class UnknownCapabilityError(CapabilityGovernanceError):
    code = "unknown_capability"


class PackNotActiveError(CapabilityGovernanceError):
    code = "pack_not_active"


class CapabilityNotActiveError(CapabilityGovernanceError):
    code = "capability_not_active"


class ReleaseNotFoundError(CapabilityGovernanceError):
    code = "release_not_found"


class ChecksumMismatchError(CapabilityGovernanceError):
    code = "checksum_mismatch"


class DependencyNotActiveError(CapabilityGovernanceError):
    code = "dependency_not_active"


class DependencyCycleError(CapabilityGovernanceError):
    code = "dependency_cycle"


class NamespaceConflictError(CapabilityGovernanceError):
    code = "namespace_conflict"


class DuplicateCapabilityError(CapabilityGovernanceError):
    code = "duplicate_capability"


class DuplicateReleaseError(CapabilityGovernanceError):
    code = "duplicate_release"


class ActivationGateError(CapabilityGovernanceError):
    code = "activation_gate_failed"


class InvalidLifecycleTransitionError(CapabilityGovernanceError):
    code = "invalid_lifecycle_transition"
