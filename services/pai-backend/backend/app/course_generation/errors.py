class CourseGenerationError(Exception):
    """Base error for controlled course-generation failures."""


class CourseGenerationArtifactNotFoundError(CourseGenerationError):
    """A required production instructional artifact could not be resolved."""


class CourseGenerationAlreadyInProgressError(CourseGenerationError):
    """The request already has an active generation run."""


class CourseGenerationOutputInvalidError(CourseGenerationError):
    """The generated structured output failed the production contract."""


class CourseGenerationProviderError(CourseGenerationError):
    """The model gateway or provider failed during generation."""
