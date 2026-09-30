class RoleProfileDraftError(ValueError):
    pass


class RoleProfileDraftNotFoundError(RoleProfileDraftError):
    pass


class RoleProfileDraftAccessDeniedError(RoleProfileDraftError):
    pass


class RoleProfileDraftSourceError(RoleProfileDraftError):
    pass


class RoleProfileDraftVersionConflictError(RoleProfileDraftError):
    pass


class RoleProfileDraftStateError(RoleProfileDraftError):
    pass
