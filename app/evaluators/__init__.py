"""Post evaluator strategies."""

from app.evaluators.base import PostEvaluator
from app.evaluators.mock import MockPostEvaluator

__all__ = ["MockPostEvaluator", "PostEvaluator"]
