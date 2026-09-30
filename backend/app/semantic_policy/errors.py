class SemanticPolicyError(ValueError):
    """Safe, stable semantic-policy governance failure."""

    code = "semantic_policy_error"


class SemanticPolicyNotFoundError(SemanticPolicyError):
    code = "semantic_policy_not_found"


class SemanticPolicyVersionNotFoundError(SemanticPolicyError):
    code = "semantic_policy_version_not_found"


class SemanticPolicyNotActiveError(SemanticPolicyError):
    code = "semantic_policy_not_active"


class DomainPackNotFoundError(SemanticPolicyError):
    code = "domain_pack_not_found"


class DomainPackVersionNotFoundError(SemanticPolicyError):
    code = "domain_pack_version_not_found"


class DomainPackNotActiveError(SemanticPolicyError):
    code = "domain_pack_not_active"


class SemanticPolicyPackIncompatibleError(SemanticPolicyError):
    code = "semantic_policy_pack_incompatible"
