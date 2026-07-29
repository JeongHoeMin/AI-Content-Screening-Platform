"""Domain models."""

from app.models.article import Article, ArticleEvaluationResult
from app.models.collect_posts import (
    CollectPostsData,
    CollectPostsMetadata,
    CollectPostsRequest,
    ProviderResultMetadata,
)
from app.models.community import CommunityType
from app.models.evaluation_response import EvaluationResponse, EvaluationResponseItem
from app.models.generate_script import (
    GeneratedScript,
    GenerateScriptData,
    GenerateScriptMetadata,
    GenerateScriptRequest,
    ScriptGenerationResult,
)
from app.models.normalize import NormalizeResult
from app.models.news_event import CompanyRelation, ExtractedCompany, NewsEvent
from app.models.news_event_response import (
    ExtractedCompanyResponseItem,
    NewsEventExtractionResponse,
    NewsEventResponseItem,
)
from app.models.post import Post
from app.models.raw_post import RawDcInsidePost, RawPost, RawRedditPost
from app.models.screen_posts import (
    PostEvaluationResult,
    ScreeningResult,
    ScreenPostsData,
    ScreenPostsMetadata,
    ScreenPostsRequest,
)
from app.models.workflow import ContentPipelineRequest, ContentPipelineResult

__all__ = [
    "Article",
    "ArticleEvaluationResult",
    "CollectPostsData",
    "CollectPostsMetadata",
    "CollectPostsRequest",
    "ContentPipelineRequest",
    "ContentPipelineResult",
    "CommunityType",
    "CompanyRelation",
    "EvaluationResponse",
    "EvaluationResponseItem",
    "ExtractedCompany",
    "ExtractedCompanyResponseItem",
    "GeneratedScript",
    "GenerateScriptData",
    "GenerateScriptMetadata",
    "GenerateScriptRequest",
    "NormalizeResult",
    "NewsEvent",
    "NewsEventExtractionResponse",
    "NewsEventResponseItem",
    "Post",
    "PostEvaluationResult",
    "ProviderResultMetadata",
    "RawDcInsidePost",
    "RawPost",
    "RawRedditPost",
    "ScreeningResult",
    "ScreenPostsData",
    "ScreenPostsMetadata",
    "ScreenPostsRequest",
    "ScriptGenerationResult",
]
