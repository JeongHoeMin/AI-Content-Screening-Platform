from __future__ import annotations

from enum import Enum


class SkillStage(str, Enum):
    """Execution stages currently used by skills."""

    PROVIDER_COLLECT = "provider_collect"
    NORMALIZE = "normalize"
