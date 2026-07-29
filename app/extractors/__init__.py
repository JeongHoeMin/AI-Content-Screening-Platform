"""News event extraction contracts and strategies."""

from app.extractors.base import NewsEventExtractor
from app.extractors.default_parser import DefaultNewsEventParser
from app.extractors.parser import NewsEventParser

__all__ = [
    "DefaultNewsEventParser",
    "NewsEventExtractor",
    "NewsEventParser",
]
