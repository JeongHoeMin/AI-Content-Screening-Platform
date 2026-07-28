from __future__ import annotations

from typing import Dict, Optional

from app.core.exceptions import NormalizerNotFoundError, ProviderNotFoundError
from app.models.community import CommunityType
from app.providers.base import CommunityNormalizer, CommunityProvider


class ProviderRegistry:
    """Registry mapping community types to providers."""

    def __init__(self, providers: Dict[CommunityType, CommunityProvider]) -> None:
        self._providers: Dict[CommunityType, CommunityProvider] = dict(providers)

    def get(self, source: CommunityType) -> CommunityProvider:
        provider: Optional[CommunityProvider] = self._providers.get(source)
        if provider is None:
            raise ProviderNotFoundError(source)
        return provider

    def register(self, source: CommunityType, provider: CommunityProvider) -> None:
        self._providers[source] = provider


class NormalizerRegistry:
    """Registry mapping community types to normalizers."""

    def __init__(self, normalizers: Dict[CommunityType, CommunityNormalizer]) -> None:
        self._normalizers: Dict[CommunityType, CommunityNormalizer] = dict(normalizers)

    def get(self, source: CommunityType) -> CommunityNormalizer:
        normalizer: Optional[CommunityNormalizer] = self._normalizers.get(source)
        if normalizer is None:
            raise NormalizerNotFoundError(source)
        return normalizer

    def register(self, source: CommunityType, normalizer: CommunityNormalizer) -> None:
        self._normalizers[source] = normalizer
