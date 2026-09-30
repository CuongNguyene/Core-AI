class LearningPathError(Exception):
    """Base error for learning-path eligibility and blueprint operations."""


class LearningPathValidationError(LearningPathError):
    pass


class LearningPathNotFoundError(LearningPathValidationError):
    pass


class LearningPathNotDraftError(LearningPathValidationError):
    pass


class LearningPathNotReadyForReviewError(LearningPathValidationError):
    pass


class LearningPathReviewRequiredError(LearningPathValidationError):
    pass


class LearningPathStaleError(LearningPathValidationError):
    pass


class LearningPathVersionConflictError(LearningPathValidationError):
    pass


class LearningPathAlreadySupersededError(LearningPathValidationError):
    pass
