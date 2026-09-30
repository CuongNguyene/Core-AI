class CourseRevisionError(Exception):
    """Base error for SME course-draft revision operations."""


class CourseRevisionNotFoundError(CourseRevisionError):
    pass


class CourseRevisionAccessDeniedError(CourseRevisionError):
    pass


class CourseRevisionConflictError(CourseRevisionError):
    pass


class CourseRevisionValidationError(CourseRevisionError):
    pass
