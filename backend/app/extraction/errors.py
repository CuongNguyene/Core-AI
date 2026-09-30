class ExtractionProfileError(Exception):
    """Base error for extraction profile lifecycle operations."""


class ExtractionProfileVersionConflict(ExtractionProfileError):
    """Raised when the caller's expected profile version is stale."""


class ExtractionProfileStateConflict(ExtractionProfileError):
    """Raised when a requested lifecycle transition is not allowed."""
