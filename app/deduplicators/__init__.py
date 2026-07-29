"""News event duplicate detection and elimination contracts."""

from app.deduplicators.base import ArticleDeduplicator
from app.deduplicators.default import DefaultArticleDeduplicator
from app.deduplicators.rule_strategy import RuleDuplicateStrategy
from app.deduplicators.strategy import DuplicateStrategy

__all__ = [
    "ArticleDeduplicator",
    "DefaultArticleDeduplicator",
    "DuplicateStrategy",
    "RuleDuplicateStrategy",
]
