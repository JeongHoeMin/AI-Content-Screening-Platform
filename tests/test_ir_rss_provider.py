from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Mapping

from app.config.trusted_sources import IrRssFeedConfig
from app.models.collect_posts import CollectPostsRequest
from app.models.community import CommunityType
from app.models.raw_post import RawIrRssPost, RawPost
from app.providers.http import TextHttpClient
from app.providers.ir_rss import IrRssNormalizer, IrRssProvider


class TextHttpClientDouble(TextHttpClient):
    def __init__(self, payloads: Mapping[str, str]) -> None:
        self._payloads: Mapping[str, str] = payloads

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> str:
        return self._payloads[url]


def test_ir_rss_provider_collects_guid_and_full_content() -> None:
    feed_url: str = "https://ir.example.com/rss.xml"
    provider = IrRssProvider(
        feeds=(
            IrRssFeedConfig(
                id="example-ir",
                url=feed_url,
                company_name="예시전자",
            ),
        ),
        http_client=TextHttpClientDouble(
            {
                feed_url: """<?xml version=\"1.0\"?>
                <rss version=\"2.0\"><channel><item>
                <guid>release-2026-08-04</guid><title>실적 발표</title>
                <link>https://ir.example.com/releases/1</link>
                <pubDate>Mon, 04 Aug 2026 09:00:00 +0000</pubDate>
                <description><![CDATA[<p>첫 번째 전체 문단입니다.</p><p>두 번째 문단입니다.</p>]]></description>
                </item></channel></rss>"""
            }
        ),
    )
    request = CollectPostsRequest(
        sources=[CommunityType.IR_RSS],
        limit=10,
        period=timedelta(days=1),
    )

    raw_posts: list[RawPost] = asyncio.run(provider.collect(request))

    assert len(raw_posts) == 1
    assert isinstance(raw_posts[0], RawIrRssPost)
    assert raw_posts[0].raw_id == "example-ir:release-2026-08-04"
    assert raw_posts[0].feed_id == "example-ir"

    normalized = asyncio.run(IrRssNormalizer().normalize(raw_posts[0]))

    assert normalized.post is not None
    assert normalized.post.content == "첫 번째 전체 문단입니다.\n두 번째 문단입니다."
    assert normalized.post.paragraphs == ("첫 번째 전체 문단입니다.", "두 번째 문단입니다.")


def test_ir_rss_provider_collects_atom_entry_with_link_href() -> None:
    feed_url: str = "https://ir.example.com/atom.xml"
    provider = IrRssProvider(
        feeds=(IrRssFeedConfig(id="example-atom", url=feed_url),),
        http_client=TextHttpClientDouble(
            {
                feed_url: """<feed xmlns=\"http://www.w3.org/2005/Atom\">
                <entry><id>atom-release-1</id><title>분기 실적</title>
                <link href=\"https://ir.example.com/releases/atom-1\"/>
                <updated>2026-08-04T09:00:00Z</updated>
                <content type=\"html\"><![CDATA[<p>Atom 전문 문단입니다.</p>]]></content>
                </entry></feed>"""
            }
        ),
    )
    request = CollectPostsRequest(
        sources=[CommunityType.IR_RSS],
        limit=10,
        period=timedelta(days=1),
    )

    raw_posts = asyncio.run(provider.collect(request))

    assert len(raw_posts) == 1
    assert raw_posts[0].raw_id == "example-atom:atom-release-1"
