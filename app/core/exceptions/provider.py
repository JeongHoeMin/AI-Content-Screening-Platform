from __future__ import annotations

from app.core.exceptions.skill import SkillExecutionError


class AllProvidersFailedError(SkillExecutionError):
    """Raised when no provider can return collectable data."""

    def __init__(self) -> None:
        super().__init__("all providers failed to collect posts")
