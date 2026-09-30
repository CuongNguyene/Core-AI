class AuditPersistenceError(RuntimeError):
    """Raised when a capability-analysis audit record cannot be persisted."""


class CapabilityAnalysisEligibilityError(ValueError):
    audit_action = "CAPABILITY_GAP_REJECTED_INPUT"


class ExtractionProfileNotAcceptedError(CapabilityAnalysisEligibilityError):
    audit_action = "CAPABILITY_GAP_REJECTED_CV_NOT_ACCEPTED"


class SupersededCapabilityProfileError(CapabilityAnalysisEligibilityError):
    audit_action = "CAPABILITY_GAP_REJECTED_CV_SUPERSEDED"


class CandidateProfileNotAnalyzableError(CapabilityAnalysisEligibilityError):
    code = "candidate_profile_not_analyzable"
    audit_action = "CAPABILITY_GAP_REJECTED_CV_NOT_ANALYZABLE"


class CapabilityAnalysisAccessDeniedError(CapabilityAnalysisEligibilityError):
    audit_action = "CAPABILITY_GAP_REJECTED_ACCESS"


class CurrentTargetNotUsableError(CapabilityAnalysisEligibilityError):
    audit_action = "CAPABILITY_GAP_REJECTED_CURRENT_TARGET"


class FutureTargetNotUsableError(CapabilityAnalysisEligibilityError):
    audit_action = "CAPABILITY_GAP_REJECTED_FUTURE_TARGET"


class SemanticPolicyNotConfiguredError(CapabilityAnalysisEligibilityError):
    code = "semantic_policy_not_configured"
    audit_action = "CAPABILITY_GAP_REJECTED_SEMANTIC_POLICY_NOT_CONFIGURED"


class SemanticPolicyUnavailableError(CapabilityAnalysisEligibilityError):
    code = "semantic_policy_unavailable"
    audit_action = "CAPABILITY_GAP_REJECTED_SEMANTIC_POLICY_UNAVAILABLE"


class CapabilityAnalysisIdempotencyConflictError(CapabilityAnalysisEligibilityError):
    code = "capability_analysis_idempotency_conflict"
    audit_action = "CAPABILITY_GAP_IDEMPOTENCY_CONFLICT"


class HumanAssistedReanalysisValidationError(CapabilityAnalysisEligibilityError):
    code = "human_assisted_reanalysis_invalid"
    audit_action = "CAPABILITY_GAP_REJECTED_HUMAN_ASSISTED_INPUT"


class CapabilityAnalysisProductError(CapabilityAnalysisEligibilityError):
    """Stable readiness failure for the candidate + role product adapter."""


class RoleProfileNotActiveProductError(CapabilityAnalysisProductError):
    code = "role_profile_not_active"


class CandidateProfileNotReadyProductError(CapabilityAnalysisProductError):
    code = "candidate_profile_not_ready"
