class CourseAuthoringError(Exception):
    """Base error for the course authoring contract."""


class CourseAuthoringRequestNotFoundError(CourseAuthoringError):
    """Raised when an authoring request cannot be retrieved."""


class CourseAuthoringReferenceNotFoundError(CourseAuthoringError):
    """Raised when an upstream learning-design reference is unknown."""


class CourseAuthoringReferenceValidationError(CourseAuthoringError):
    """Raised when explicit upstream references are inconsistent."""


class CourseAuthoringAccessDeniedError(CourseAuthoringError):
    """Raised when the actor cannot access an upstream reference."""

