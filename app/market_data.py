from __future__ import annotations

from typing import List, Tuple

from app.bootstrap import ExecutionMode, create_screening_workflow_async
from app.config import load_dart_config, load_naver_news_config, load_trusted_source_config
from app.evaluators import RuleArticleEvaluatorConfig
from app.models.article import Article, ArticleContentOrigin, ArticleParagraph
from app.models.post import Post
from app.providers import (
    DartDisclosureNormalizer,
    DartDisclosureProvider,
    IrRssNormalizer,
    IrRssProvider,
    NaverNewsNormalizer,
    NaverNewsProvider,
    NormalizerRegistry,
    ProviderRegistry,
)
from app.models.community import CommunityType
from app.skills.collect_posts import CollectPostsSkill
from app.workflows import ScreeningWorkflow

def create_market_collect_posts_skill() -> CollectPostsSkill:
    """Assemble the real-news and disclosure collection skill from environment config."""
    trusted_config = load_trusted_source_config()
    return CollectPostsSkill(
        provider_registry=ProviderRegistry(
            {
                CommunityType.NAVER_NEWS: NaverNewsProvider(load_naver_news_config()),
                CommunityType.DART: DartDisclosureProvider(load_dart_config()),
                CommunityType.IR_RSS: IrRssProvider(trusted_config.ir_rss_feeds),
            }
        ),
        normalizer_registry=NormalizerRegistry(
            {
                CommunityType.NAVER_NEWS: NaverNewsNormalizer(),
                CommunityType.DART: DartDisclosureNormalizer(),
                CommunityType.IR_RSS: IrRssNormalizer(),
            }
        ),
    )


async def create_market_screening_workflow(
    mode: ExecutionMode,
) -> ScreeningWorkflow:
    """Assemble screening for provider summaries with a documented minimum length."""
    trusted_config = load_trusted_source_config()
    return await create_screening_workflow_async(
        mode,
        RuleArticleEvaluatorConfig(
            min_body_length=trusted_config.min_body_length,
            max_body_length=trusted_config.max_body_length,
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
                analysis_eligible=post.source is not CommunityType.NAVER_NEWS,
                content_origin=(
                    ArticleContentOrigin.OFFICIAL_FULL_TEXT
                    if post.source in {CommunityType.DART, CommunityType.IR_RSS}
                    else ArticleContentOrigin.SNIPPET
                ),
                paragraphs=tuple(
                    ArticleParagraph(index=index, content=paragraph)
                    for index, paragraph in enumerate(post.paragraphs, start=1)
                ),
            )
        )
    return tuple(articles)
