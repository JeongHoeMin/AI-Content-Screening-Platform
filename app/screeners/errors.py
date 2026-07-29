class ScreeningAssessmentValidationError(ValueError):
    """Raised when structured screening output cannot match input candidates."""


class NoValidScreeningDecisionsError(RuntimeError):
    """Raised when non-empty input produces no valid screening decision."""
