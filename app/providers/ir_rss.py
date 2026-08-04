from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Mapping, Optional, Sequence, Tuple
from xml.etree import ElementTree

import structlog
from bs4 import BeautifulSoup

from app.config.trusted_sources import IrRssFeedConfig
from app.core.error import SkillError
from app.core.stage import SkillStage
from app.models.collect_posts import CollectPostsRequest
from app.models.community import CommunityType
from app.models.normalize import NormalizeResult
from app.models.post import Post
from app.models.raw_post import RawIrRssPost, RawPost
from app.providers.base import CommunityNormalizer, CommunityProvider
from app.providers.http import ExternalServiceError, StdlibTextHttpClient, TextHttpClient

logger = structlog.get_logger(__name__)


class IrRssProvider(CommunityProvider):
    """Collect full-text corporate IR feed entries from approved endpoints only."""

    def __init__(
        self,
        feeds: Sequence[IrRssFeedConfig],
        http_client: Optional[TextHttpClient] = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._feeds: Tuple[IrRssFeedConfig, ...] = tuple(feeds)
        self._http_client: TextHttpClient = http_client or StdlibTextHttpClient()
        self._timeout_seconds: float = timeout_seconds

    async def collect(self, request: CollectPostsRequest) -> List[RawPost]:
        results: Tuple[List[RawIrRssPost], ...] = tuple(
            await asyncio.gather(
                *(self._collect_feed(feed, request) for feed in self._feeds)
            )
        )
        return [post for posts in results for post in posts][: request.limit]

    async def _collect_feed(
        self,
        feed: IrRssFeedConfig,
        request: CollectPostsRequest,
    ) -> List[RawIrRssPost]:
        try:
            payload: str = await self._http_client.get(
                url=str(feed.url),
                headers={"Accept": "application/rss+xml, application/atom+xml, application/xml"},
                query={},
                timeout_seconds=self._timeout_seconds,
            )
            return self._parse_feed(feed, payload, request)
        except (ElementTree.ParseError, ExternalServiceError, ValueError):
            logger.warning("ir_rss_feed_unavailable", feed_id=feed.id, error_kind="feed_unavailable")
            return []

    @staticmethod
    def _parse_feed(
        feed: IrRssFeedConfig,
        payload: str,
        request: CollectPostsRequest,
    ) -> List[RawIrRssPost]:
        root: ElementTree.Element = ElementTree.fromstring(payload)
        item_nodes: List[ElementTree.Element] = list(root.findall(".//item"))
        if not item_nodes:
            item_nodes = list(root.findall(".//{*}entry"))
        cutoff: datetime = datetime.now(timezone.utc) - request.period
        posts: List[RawIrRssPost] = []
        for item in item_nodes:
            post: Optional[RawIrRssPost] = IrRssProvider._parse_item(feed, item)
            if post is not None and post.published_at.astimezone(timezone.utc) >= cutoff:
                posts.append(post)
        return posts[: request.limit]

    @staticmethod
    def _parse_item(
        feed: IrRssFeedConfig,
        item: ElementTree.Element,
    ) -> Optional[RawIrRssPost]:
        title: str = IrRssProvider._text(item, "title")
        external_id: str = IrRssProvider._text(item, "guid") or IrRssProvider._text(item, "{*}id")
        link: str = IrRssProvider._text(item, "link")
        if not link:
            link_element: Optional[ElementTree.Element] = item.find("{*}link")
            link = "" if link_element is None else str(link_element.attrib.get("href", "")).strip()
        content: str = (
            IrRssProvider._text(item, "{*}encoded")
            or IrRssProvider._text(item, "{*}content")
            or IrRssProvider._text(item, "description")
            or IrRssProvider._text(item, "{*}summary")
        )
        published_text: str = (
            IrRssProvider._text(item, "pubDate")
            or IrRssProvider._text(item, "{*}published")
            or IrRssProvider._text(item, "{*}updated")
        )
        if not external_id:
            external_id = link
        if not title or not external_id or not link or not content or not published_text:
            return None
        try:
            published_at: datetime = parsedate_to_datetime(published_text)
        except (TypeError, ValueError):
            try:
                published_at = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
            except ValueError:
                return None
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        try:
            return RawIrRssPost(
                raw_id=f"{feed.id}:{external_id}",
                fetched_at=datetime.now(timezone.utc),
                feed_id=feed.id,
                company_name=feed.company_name,
                title=title,
                content_html=content,
                published_at=published_at,
                link=link,
            )
        except ValueError:
            return None

    @staticmethod
    def _text(item: ElementTree.Element, name: str) -> str:
        value: Optional[ElementTree.Element] = item.find(name)
        if value is None and not name.startswith("{"):
            value = item.find(f"{{*}}{name}")
        return "" if value is None or value.text is None else value.text.strip()


class IrRssNormalizer(CommunityNormalizer):
    """Normalize corporate feed full text and preserve its paragraph structure."""

    async def normalize(self, raw_post: RawPost) -> NormalizeResult:
        if not isinstance(raw_post, RawIrRssPost):
            return NormalizeResult(
                error=SkillError(
                    code="invalid_raw_post_type",
                    stage=SkillStage.NORMALIZE,
                    message="Expected RawIrRssPost",
                    source=CommunityType.IR_RSS.value,
                )
            )
        paragraphs: Tuple[str, ...] = self._paragraphs(raw_post.content_html)
        if not paragraphs:
            return NormalizeResult(
                error=SkillError(
                    code="empty_full_text",
                    stage=SkillStage.NORMALIZE,
                    message="Corporate feed entry has no usable full text",
                    source=CommunityType.IR_RSS.value,
                )
            )
        return NormalizeResult(
            post=Post(
                id=raw_post.raw_id,
                source=CommunityType.IR_RSS,
                title=raw_post.title,
                content="\n".join(paragraphs),
                author=raw_post.company_name,
                created_at=raw_post.published_at,
                url=raw_post.link,
                paragraphs=paragraphs,
            )
        )

    @staticmethod
    def _paragraphs(content_html: str) -> Tuple[str, ...]:
        soup = BeautifulSoup(content_html, "html.parser")
        values: List[str] = []
        for element in soup.find_all(["p", "li", "td"]):
            value: str = " ".join(element.get_text(" ", strip=True).split())
            if value and value not in values:
                values.append(value)
        if not values:
            plain: str = " ".join(soup.get_text(" ", strip=True).split())
            if plain:
                values.append(plain)
        return tuple(values)
