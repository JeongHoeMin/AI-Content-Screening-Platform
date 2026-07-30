from __future__ import annotations

from typing import List, Tuple

from app.config import load_dart_config, load_naver_news_config
from app.models.article import Article
from app.models.post import Post
from app.providers import (
    DartDisclosureNormalizer,
    DartDisclosureProvider,
    NaverNewsNormalizer,
    NaverNewsProvider,
    NormalizerRegistry,
    ProviderRegistry,
)
from app.models.community import CommunityType
from app.skills.collect_posts import CollectPostsSkill


def create_market_collect_posts_skill() -> CollectPostsSkill:
    """Assemble the real-news and disclosure collection skill from environment config."""
    return CollectPostsSkill(
        provider_registry=ProviderRegistry(
            {
                CommunityType.NAVER_NEWS: NaverNewsProvider(load_naver_news_config()),
                CommunityType.DART: DartDisclosureProvider(load_dart_config()),
            }
        ),
        normalizer_registry=NormalizerRegistry(
            {
                CommunityType.NAVER_NEWS: NaverNewsNormalizer(),
                CommunityType.DART: DartDisclosureNormalizer(),
            }
        ),
    )


def posts_to_articles(posts: List[Post]) -> Tuple[Article, ...]:
    """Project normalized posts with textual content into the immutable Article input."""
    articles: List[Article] = []
    for post in posts:
        if post.content is None or not post.content.strip():
            continue
        articles.append(
            Article(
                id=f"{post.source.value}:{post.id}",
                title=post.title,
                content=post.content,
                source=post.source.value,
                published_at=post.created_at,
                url=post.url,
            )
        )
    return tuple(articles)
