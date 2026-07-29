from __future__ import annotations

from app.models.article import Article


def normalize_mock_title(title: str) -> str:
    """Normalize mock-only title grouping by whitespace collapse and casefold."""
    return " ".join(title.split()).casefold()


def build_mock_grouping_key(article: Article) -> str:
    """Build a mock-only exact-title key, not semantic news clustering.

    Articles are related only when normalized titles are exactly equal. Punctuation,
    word order, synonyms, and other semantic similarities are intentionally kept.
    """
    return normalize_mock_title(article.title)
