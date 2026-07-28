from __future__ import annotations

from app.models.community import CommunityType


class ProviderNotFoundError(LookupError):
    """Raised when a provider is not registered for a community."""

    def __init__(self, source: CommunityType) -> None:
        self.source: CommunityType = source
        super().__init__(f"provider not found for source: {source.value}")


class NormalizerNotFoundError(LookupError):
    """Raised when a normalizer is not registered for a community."""

    def __init__(self, source: CommunityType) -> None:
        self.source: CommunityType = source
        super().__init__(f"normalizer not found for source: {source.value}")
