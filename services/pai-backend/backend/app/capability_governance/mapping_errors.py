"""Stable domain failures for governed mapping activation and resolution."""


class MappingGovernanceError(ValueError):
    """A deterministic fail-closed result in the 3D-3B mapping boundary."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)
