from __future__ import annotations

from typing import List, Protocol

from app.models.generate_script import ScriptGenerationResult
from app.models.screen_posts import ScreeningResult


class ScriptGenerator(Protocol):
    """Generates scripts from screened post candidates."""

    async def generate(self, candidates: List[ScreeningResult]) -> ScriptGenerationResult:
        """Generate scripts for a batch of candidates."""
