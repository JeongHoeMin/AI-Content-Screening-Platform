from __future__ import annotations

import asyncio
import io
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, List, Mapping

import pytest

from app.config import DartConfig, NaverNewsConfig, load_dart_config, load_naver_news_config
from app.config.errors import ConfigurationError
from app.models import CollectPostsRequest, CommunityType, RawDartDisclosurePost, RawNaverNewsPost
from app.models.raw_post import RawPost
from app.providers import (
    DartDisclosureNormalizer,
    DartDisclosureProvider,
    NaverNewsNormalizer,
    NaverNewsProvider,
)
from app.providers.http import BytesHttpClient, JsonHttpClient


class JsonHttpClientDouble(JsonHttpClient):
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload: Mapping[str, Any] = payload
        self.url: str = ""
        self.headers: Mapping[str, str] = {}
        self.query: Mapping[str, str] = {}
        self.timeout_seconds: float = 0.0

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        self.url = url
        self.headers = headers
        self.query = query
        self.timeout_seconds = timeout_seconds
        return self.payload


class BytesHttpClientDouble(BytesHttpClient):
    def __init__(self, payload: bytes) -> None:
        self.payload: bytes = payload
        self.url: str = ""
        self.query: Mapping[str, str] = {}

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> bytes:
        self.url = url
        self.query = query
        return self.payload


class CountingBytesHttpClientDouble(BytesHttpClientDouble):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.call_count: int = 0

    async def get(
        self,
        url: str,
        headers: Mapping[str, str],
        query: Mapping[str, str],
        timeout_seconds: float,
    ) -> bytes:
        self.call_count += 1
        return await super().get(url, headers, query, timeout_seconds)


def build_document_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("report.html", "<p>첫 공시 문단</p><p>둘째 공시 문단</p>")
    return buffer.getvalue()


def build_request(category: str = "반도체") -> CollectPostsRequest:
    return CollectPostsRequest(
        sources=[CommunityType.NAVER_NEWS],
        limit=5,
        period=timedelta(days=1),
        category=category,
    )


def test_naver_provider_uses_credential_headers_and_normalizes_html() -> None:
    client: JsonHttpClientDouble = JsonHttpClientDouble(
        {
            "items": [
                {
                    "title": "&lt;b&gt;삼성전자&lt;/b&gt; 실적",
                    "originallink": "https://publisher.example.com/news/1",
                    "link": "https://news.naver.com/article/1",
                    "description": "&lt;b&gt;반도체&lt;/b&gt; 수요가 증가했습니다.",
                    "pubDate": datetime.now(timezone.utc).strftime(
                        "%a, %d %b %Y %H:%M:%S +0000"
                    ),
                }
            ]
        }
    )
    provider: NaverNewsProvider = NaverNewsProvider(
        NaverNewsConfig(client_id="client-id", client_secret="client-secret"), client
    )

    raw_posts: List[RawPost] = asyncio.run(provider.collect(build_request()))

    assert client.url == "https://openapi.naver.com/v1/search/news.json"
    assert client.headers == {
        "X-Naver-Client-Id": "client-id",
        "X-Naver-Client-Secret": "client-secret",
    }
    assert client.query == {"query": "반도체", "display": "5", "start": "1", "sort": "date"}
    assert len(raw_posts) == 1
    assert isinstance(raw_posts[0], RawNaverNewsPost)

    result = asyncio.run(NaverNewsNormalizer().normalize(raw_posts[0]))

    assert result.post is not None
    assert result.post.title == "삼성전자 실적"
    assert result.post.content == "반도체 수요가 증가했습니다."
    assert str(result.post.url) == "https://publisher.example.com/news/1"


def test_naver_provider_skips_invalid_and_outdated_items() -> None:
    client: JsonHttpClientDouble = JsonHttpClientDouble(
        {
            "items": [
                {"title": "missing fields"},
                {
                    "title": "old article",
                    "originallink": "https://publisher.example.com/news/old",
                    "link": "https://news.naver.com/article/old",
                    "description": "old description",
                    "pubDate": "Mon, 01 Jan 2024 00:00:00 +0000",
                },
            ]
        }
    )
    provider: NaverNewsProvider = NaverNewsProvider(
        NaverNewsConfig(client_id="client-id", client_secret="client-secret"), client
    )

    raw_posts: List[RawPost] = asyncio.run(provider.collect(build_request()))

    assert raw_posts == []


def test_dart_provider_uses_requested_period_and_preserves_disclosure_metadata() -> None:
    client: JsonHttpClientDouble = JsonHttpClientDouble(
        {
            "status": "000",
            "list": [
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "stock_code": "005930",
                    "corp_cls": "Y",
                    "report_nm": "단일판매ㆍ공급계약체결(자율공시)",
                    "rcept_no": "20260730000001",
                    "flr_nm": "삼성전자",
                    "rcept_dt": "20260730",
                }
            ],
        }
    )
    document_client: BytesHttpClientDouble = BytesHttpClientDouble(build_document_zip())
    provider: DartDisclosureProvider = DartDisclosureProvider(
        DartConfig(api_key="dart-key"), client, document_client
    )
    request: CollectPostsRequest = CollectPostsRequest(
        sources=[CommunityType.DART], limit=5, period=timedelta(days=3)
    )

    raw_posts: List[RawPost] = asyncio.run(provider.collect(request))

    assert client.url == "https://opendart.fss.or.kr/api/list.json"
    assert client.query["crtfc_key"] == "dart-key"
    assert client.query["page_count"] == "5"
    assert len(raw_posts) == 1
    assert isinstance(raw_posts[0], RawDartDisclosurePost)
    assert raw_posts[0].stock_code == "005930"
    assert raw_posts[0].document_paragraphs == ("첫 공시 문단", "둘째 공시 문단")
    assert document_client.url == "https://opendart.fss.or.kr/api/document.xml"
    assert document_client.query["rcept_no"] == "20260730000001"

    result = asyncio.run(DartDisclosureNormalizer().normalize(raw_posts[0]))

    assert result.post is not None
    assert result.post.title == "단일판매ㆍ공급계약체결(자율공시)"
    assert result.post.content == (
        "삼성전자 (종목코드: 005930)의 공시입니다. "
        "공시 제목: 단일판매ㆍ공급계약체결(자율공시). 공시 접수일: 2026-07-30.\n"
        "첫 공시 문단\n둘째 공시 문단"
    )
    assert str(result.post.url).endswith("20260730000001")


def test_dart_provider_filters_periodic_disclosures_before_fetching_the_document() -> None:
    client: JsonHttpClientDouble = JsonHttpClientDouble(
        {
            "status": "000",
            "list": [
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "stock_code": "005930",
                    "corp_cls": "Y",
                    "report_nm": "[기재정정]반기보고서",
                    "rcept_no": "20260730000001",
                    "flr_nm": "삼성전자",
                    "rcept_dt": "20260730",
                },
                {
                    "corp_code": "00164742",
                    "corp_name": "SK하이닉스",
                    "stock_code": "000660",
                    "corp_cls": "Y",
                    "report_nm": "유상증자결정",
                    "rcept_no": "20260730000002",
                    "flr_nm": "SK하이닉스",
                    "rcept_dt": "20260730",
                },
            ],
        }
    )
    document_client: CountingBytesHttpClientDouble = CountingBytesHttpClientDouble(
        build_document_zip()
    )
    provider: DartDisclosureProvider = DartDisclosureProvider(
        DartConfig(api_key="dart-key"), client, document_client
    )
    request: CollectPostsRequest = CollectPostsRequest(
        sources=[CommunityType.DART], limit=5, period=timedelta(days=3)
    )

    raw_posts: List[RawPost] = asyncio.run(provider.collect(request))

    assert len(raw_posts) == 1
    assert isinstance(raw_posts[0], RawDartDisclosurePost)
    assert raw_posts[0].report_name == "유상증자결정"
    assert document_client.call_count == 1
    assert document_client.query["rcept_no"] == "20260730000002"


def test_dart_provider_uses_request_ended_at_with_korean_calendar_projection() -> None:
    client: JsonHttpClientDouble = JsonHttpClientDouble({"status": "000", "list": []})
    provider: DartDisclosureProvider = DartDisclosureProvider(DartConfig(api_key="dart-key"), client)
    request: CollectPostsRequest = CollectPostsRequest(
        sources=[CommunityType.DART],
        limit=25,
        period=timedelta(days=1),
        ended_at=datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
    )

    raw_posts: List[RawPost] = asyncio.run(provider.collect(request))

    assert raw_posts == []
    assert client.query["bgn_de"] == "20260731"
    assert client.query["end_de"] == "20260801"


def test_dart_provider_projects_cli_kst_boundary_to_one_korean_calendar_day() -> None:
    client: JsonHttpClientDouble = JsonHttpClientDouble({"status": "000", "list": []})
    provider: DartDisclosureProvider = DartDisclosureProvider(DartConfig(api_key="dart-key"), client)
    request: CollectPostsRequest = CollectPostsRequest(
        sources=[CommunityType.DART],
        limit=25,
        period=timedelta(hours=24),
        ended_at=datetime(2026, 7, 31, 15, 0, tzinfo=timezone.utc),
    )

    raw_posts: List[RawPost] = asyncio.run(provider.collect(request))

    assert raw_posts == []
    assert client.query["bgn_de"] == "20260731"
    assert client.query["end_de"] == "20260731"


def test_dart_provider_rejects_non_success_response() -> None:
    provider: DartDisclosureProvider = DartDisclosureProvider(
        DartConfig(api_key="dart-key"), JsonHttpClientDouble({"status": "013", "message": "no data"})
    )
    request: CollectPostsRequest = CollectPostsRequest(
        sources=[CommunityType.DART], limit=5, period=timedelta(days=1)
    )

    with pytest.raises(ValueError, match="not accepted"):
        asyncio.run(provider.collect(request))


def test_dart_normalizer_exposes_document_failure_as_recoverable_error() -> None:
    raw_post = RawDartDisclosurePost(
        raw_id="20260730000001",
        fetched_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        corporation_code="00126380",
        corporation_name="삼성전자",
        report_name="반기보고서",
        receipt_number="20260730000001",
        receipt_date=datetime(2026, 7, 30, tzinfo=timezone.utc),
        disclosure_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260730000001",
        document_error_kind="not_zip_archive",
    )

    result = asyncio.run(DartDisclosureNormalizer().normalize(raw_post))

    assert result.post is None
    assert result.error is not None
    assert result.error.code == "dart_document_not_zip_archive"


def test_market_data_config_requires_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("DART_API_KEY", raising=False)

    with pytest.raises(ConfigurationError):
        load_naver_news_config()
    with pytest.raises(ConfigurationError):
        load_dart_config()


def test_market_data_config_reads_env_values_without_exposing_them(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NAVER_CLIENT_ID", "client-id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("DART_API_KEY", "dart-key")

    naver: NaverNewsConfig = load_naver_news_config()
    dart: DartConfig = load_dart_config()

    assert naver.client_id.get_secret_value() == "client-id"
    assert dart.api_key.get_secret_value() == "dart-key"
    assert "client-secret" not in repr(naver)
    assert "dart-key" not in repr(dart)
