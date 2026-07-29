class CrossValidationAssessmentValidationError(ValueError):
    """Raised when structured cross-validation output violates its contract."""


class NoValidCrossValidationResultsError(RuntimeError):
    """Raised when validation targets produce no valid result."""
