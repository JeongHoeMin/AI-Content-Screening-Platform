from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, List, Mapping, Optional

from pydantic import ValidationError
import structlog

from app.config.market_data import NaverNewsConfig
from app.models.collect_posts import CollectPostsRequest
from app.models.raw_post import RawNaverNewsPost, RawPost
from app.providers.base import CommunityProvider
from app.providers.http import JsonHttpClient, StdlibJsonHttpClient

logger = structlog.get_logger(__name__)

_NAVER_NEWS_URL: str = "https://openapi.naver.com/v1/search/news.json"


class NaverNewsProvider(CommunityProvider):
    """Collect Naver News search results without normalizing their HTML fields."""

    def __init__(
        self,
        config: NaverNewsConfig,
        http_client: Optional[JsonHttpClient] = None,
    ) -> None:
        self._config: NaverNewsConfig = config
        self._http_client: JsonHttpClient = http_client or StdlibJsonHttpClient()

    async def collect(self, request: CollectPostsRequest) -> List[RawPost]:
        query: str = request.category or "국내 증시"
        payload: Mapping[str, Any] = await self._http_client.get(
            url=_NAVER_NEWS_URL,
            headers={
                "X-Naver-Client-Id": self._config.client_id.get_secret_value(),
                "X-Naver-Client-Secret": self._config.client_secret.get_secret_value(),
            },
            query={
                "query": query,
                "display": str(min(request.limit, 100)),
                "start": "1",
                "sort": "date",
            },
            timeout_seconds=self._config.timeout_seconds,
        )
        items: object = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("Naver News response items must be a list")

        cutoff: datetime = datetime.now(timezone.utc) - request.period
        raw_posts: List[RawPost] = []
        for index, item in enumerate(items):
            raw_post: Optional[RawNaverNewsPost] = self._parse_item(item, index)
            if raw_post is None:
                continue
            published_at: datetime = raw_post.published_at.astimezone(timezone.utc)
            if published_at >= cutoff:
                raw_posts.append(raw_post)
        return raw_posts

    def _parse_item(self, item: object, index: int) -> Optional[RawNaverNewsPost]:
        if not isinstance(item, dict):
            logger.warning("naver_news_item_skipped", item_index=index, error_kind="invalid_type")
            return None
        try:
            published_at: datetime = parsedate_to_datetime(str(item["pubDate"]))
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            link: str = str(item.get("originallink") or item["link"])
            return RawNaverNewsPost(
                raw_id=link,
                fetched_at=datetime.now(timezone.utc),
                title_html=str(item["title"]),
                description_html=str(item["description"]),
                publisher_url=link,
                naver_url=str(item["link"]),
                published_at=published_at,
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            logger.warning("naver_news_item_skipped", item_index=index, error_kind="invalid_item")
            return None
