class PreliminaryMatchError(Exception):
    """Base error for preliminary matching eligibility failures."""


class ExtractionProfileNotAcceptedError(PreliminaryMatchError):
    """Raised when a matching input profile has not completed review."""


class RoleProfileNotActiveError(PreliminaryMatchError):
    """Raised when a requested role profile is not active."""


class SupersededInputError(PreliminaryMatchError):
    """Raised when a newer extraction profile revision exists."""


class PreliminaryMatchAccessDeniedError(PreliminaryMatchError):
    """Raised when an actor does not own the CV profile being matched."""
