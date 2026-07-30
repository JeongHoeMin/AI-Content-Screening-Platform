"""Community providers, normalizers, and registries."""

from app.providers.base import CommunityNormalizer, CommunityProvider
from app.providers.dart import DartDisclosureProvider
from app.providers.market_normalizers import DartDisclosureNormalizer, NaverNewsNormalizer
from app.providers.mock import (
    MockDcInsideNormalizer,
    MockDcInsideProvider,
    MockRedditNormalizer,
    MockRedditProvider,
)
from app.providers.registry import NormalizerRegistry, ProviderRegistry
from app.providers.naver_news import NaverNewsProvider

__all__ = [
    "CommunityNormalizer",
    "CommunityProvider",
    "DartDisclosureNormalizer",
    "DartDisclosureProvider",
    "MockDcInsideNormalizer",
    "MockDcInsideProvider",
    "MockRedditNormalizer",
    "MockRedditProvider",
    "NaverNewsNormalizer",
    "NaverNewsProvider",
    "NormalizerRegistry",
    "ProviderRegistry",
]
