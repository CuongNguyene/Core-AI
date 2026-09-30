class CompetencyDecisionError(Exception):
    """Base error for fail-closed competency decision transitions."""


class AuthorizationDeniedError(CompetencyDecisionError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code


class CompetencyRecordNotFoundError(CompetencyDecisionError):
    pass
