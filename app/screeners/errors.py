class ScreeningAssessmentValidationError(ValueError):
    """Raised when structured screening output cannot match input candidates."""


class NoValidScreeningDecisionsError(RuntimeError):
    """Raised when non-empty input produces no valid screening decision."""

    def __init__(self, error_type: str = "UnknownError") -> None:
        self.error_type: str = error_type
        super().__init__("No valid screening decisions were produced")
